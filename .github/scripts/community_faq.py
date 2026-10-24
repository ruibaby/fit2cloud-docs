#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多产品社区常见问题自动生成脚本（Rspress / fit2cloud-docs）

产品范围由文件里的 PRODUCTS 表驱动，默认 jumpserver（保持历史行为不变）：
    jumpserver / dataease / maxkb / 1panel / sqlbot / cordys

数据流:
    芝麻会话（社区小助手名下该产品的交流群）
      -> 最近 N 天的「客户提问 → 部门同事解答」问答对
      -> 大模型把近义问题归组，挑出**可复用（别人也会问）且有明确答案**的问题
      -> 再按官方文档原文或官方人员答复成稿（读了正文后才裁决「文档是否已能直接回答」）
      -> 校验引用路径真实存在（模糊纠错后仍找不到只当没有文档依据）、问题未与页面已有条目重复
      -> 追加到 content/<product>/<version>/zh/faq/community_faq.mdx 对应小节

窗口说明:
    days 默认 8 天（今天含在内，即 today-7 … today）。
    取 8 而不取 7，是为了补回上一次运行漏掉的那半天：定时任务在周一 09:30 运行，
    当天 09:30 之后的消息在运行时还不存在，而「7 天」窗口又恰好从上次运行的那一天开始，
    于是上周一 09:30–23:59 这一段两次运行都覆盖不到；窗口多留一天即闭合。
    相邻两周因此有约一天重叠，重叠带来的重复问题由页面标题去重拦截。

用法:
    python .github/scripts/community_faq.py --list                  # 列出已启用产品
    python .github/scripts/community_faq.py --matrix                # 输出产品名 JSON（供 workflow matrix）
    python .github/scripts/community_faq.py --product dataease --days 8 --skip-llm
    python .github/scripts/community_faq.py --product dataease --days 8    # 预览（默认不写回）
    python .github/scripts/community_faq.py --product maxkb --days 8 --apply --max-items 3
    python .github/scripts/community_faq.py --pairs-json pairs.json --product cordys

环境变量:
    ZHIMA_BASE_URL             芝麻会话管理端地址（无尾斜杠），如 http://host:8002
    ZHIMA_ACCOUNT/PASSWORD     管理端登录账密（用来自动换 token）
    ZHIMA_SCOPE_STAFF_USERID   社区小助手 userid，默认 SheQuXiaoZhuShou
    ZHIMA_DEPT_STAFF           官方人员名单 JSON，如 [{"name":"张三"},{"name":"李四","aliases":["小李"]}]
                               仅用于**标记**「这是官方人员的答复」（高信任来源），**不做过滤**：
                               名单外同事的答复仍会保留，只是标记为「普通同事答复」（低信任），
                               两级来源都交给第二轮按分级标准审核。未设置时全部按普通同事处理
    LLM_BASE_URL               模型网关（OpenAI 兼容）。默认 https://qianfan.baidubce.com/v2，
    LLM_API_KEY                模型 Key（百度千帆用 IAM/API Key 形式的 Bearer Token）
                               由 workflow 从 secrets.LLM_API_KEY 注入，不要写进仓库文件
    LLM_MODEL                  模型名，默认 deepseek-v4.1-flash；置空则列出网关可用模型
    LLM_DISABLE_REASONING      非 0 即关闭推理型模型的思维链，默认开启（见脚本内常量注释）
    PRODUCT_KEYWORD            群名过滤关键词**覆盖项**：只对 jumpserver 生效（历史兼容）；
                               其它产品的关键词一律取自 PRODUCTS 表。传 --product 时，
                               若 PRODUCT_KEYWORD 与该产品的默认关键词不同，则仍以环境变量为准

退出码: 0=完成, 1=取数失败, 2=配置/参数错误, 3=无合格新条目（不需要提 PR）,
        4=大模型环节失败（网关不可达 / 鉴权失败 / 模型无返回）,
        5=MDX 安全护栏拦截（生成内容无法通过 MDX 编译，页面未写入）

关于退出码 1 / 3 / 4 / 5 的区别（重要）:
    3 只用于「确实取到了数据、只是没有合格的新条目」，此时 workflow 视为成功且不提 PR。
    1 专指**取数**环节：登录失败、接口异常、一条消息都没取到——若被当成「无新增」，
      接口整体挂掉时会伪装成绿色成功、静默跳过一整周，没人会发现。
    4 专指**大模型**环节：LLM_BASE_URL 不可达、LLM_API_KEY 无效、模型无返回。
      必须单独成码，否则报错文案会指向取数、把排查方向带偏
      （2026-09-23 实测：取数 321 条全部成功，仅模型网关跨境超时，却被报成「取数失败」）。
    5 专指**MDX 安全护栏**：模型写出的内容经转义后仍无法通过 MDX 编译（例如新出现的
      危险写法），页面**保持原样不写入**、由人工介入。宁可本周无新增，也不能让坏内容
      进 main 把整站发布搞挂（2026-10-10 事故：裸尖括号 `<参数>` 导致 build 失败）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NODE_MODULES = REPO_ROOT / "node_modules"
# 本文件只有标准库依赖，但模块级会读取 package.json 判定 MDX 校验可用性
PACKAGE_JSON = REPO_ROOT / "package.json"

# ---------------------------------------------------------------- 产品配置
#
# 一个产品一条记录，脚本与 workflow 都由它驱动（对齐 gen_changelog_multi.py 的做法）：
#   docs            文档目录名（相对仓库根）
#   faq_rel         FAQ 页面在文档目录下的相对路径
#   name            展示给模型的完整产品名（进提示词，影响措辞）
#   keyword         群名过滤关键词（小写比对）
#   exclude         群名里命中任一子串就排除（大小写不敏感）
#                    —— 1Panel 的「1Panel VIP 交流群8」也被 '1panel' 命中，须按此剔除
#   version_scope   提示词里的版本口径；空串表示该产品没有「只收某个大版本」的约束
#   enabled         是否纳入自动流程（--list / --matrix 只输出启用的）
#   branch          该产品的固定分支名（每个产品独立，互不覆盖）
#   min_md          Preflight 的稀疏检出防呆阈值（该产品文档目录下期望的 md 数量下限）
#
# ⚠️ version_scope 需人工确认：它决定模型「哪些版本的提问该收」，写错会静默漏收或误收。
#    取值依据是各产品当前文档版本（见 content/<product>/<version>/zh/changelog.mdx 最新版本标题）。
PRODUCTS: dict[str, dict] = {
    "jumpserver": {
        "docs": "content/jumpserver/v5/zh",
        "faq_rel": "faq/community_faq.mdx",
        "name": "JumpServer（飞致云开源堡垒机）",
        # 兼容旧行为：未传 --product 时的默认产品就是它，关键词回落到 PRODUCT_KEYWORD
        "keyword": "jumpserver",
        "exclude": [],
        "version_scope": "V5",
        "owner": "fanzhoui",
        "enabled": True,
        "branch": "chore/weekly-community-faq",
        "min_md": 50,
    },
    "dataease": {
        "docs": "content/dataease/v3/zh",
        "faq_rel": "faq/community_faq.mdx",
        "name": "DataEase（飞致云开源 BI 工具）",
        "keyword": "dataease",
        "exclude": [],
        "version_scope": "v3",
        "owner": "Fit111",
        "enabled": True,
        "branch": "chore/weekly-community-faq-dataease",
        "min_md": 50,
    },
    "maxkb": {
        "docs": "content/maxkb/v2/zh",
        "faq_rel": "faq/community_faq.mdx",
        "name": "MaxKB（飞致云开源大模型知识库问答系统）",
        "keyword": "maxkb",
        "exclude": [],
        "version_scope": "v2",
        "owner": "shouzhiyuxian",
        "enabled": True,
        "branch": "chore/weekly-community-faq-maxkb",
        "min_md": 50,
    },
    "1panel": {
        "docs": "content/1panel/v2/zh",
        "faq_rel": "faq/community_faq.mdx",
        "name": "1Panel（飞致云开源 Linux 运维管理面板）",
        "keyword": "1panel",
        # 「1Panel VIP 交流群8/7/9」不是普通用户交流群，剔除
        "exclude": ["vip"],
        "version_scope": "v2",
        "owner": "gitplayer4",
        "enabled": True,
        "branch": "chore/weekly-community-faq-1panel",
        "min_md": 50,
    },
    "sqlbot": {
        "docs": "content/sqlbot/v1/zh",
        "faq_rel": "faq/community_faq.mdx",
        "name": "SQLBot（飞致云开源智能问数系统）",
        "keyword": "sqlbot",
        "exclude": [],
        "version_scope": "v1",
        "owner": "yangjie-sister",
        "enabled": True,
        "branch": "chore/weekly-community-faq-sqlbot",
        "min_md": 30,
    },
    "cordys": {
        "docs": "content/cordys/v1/zh",
        "faq_rel": "faq/community_faq.mdx",
        "name": "Cordys CRM（飞致云开源 AI CRM）",
        "keyword": "cordys",
        "exclude": [],
        "version_scope": "v1",
        "owner": "yangjie-sister",
        "enabled": True,
        "branch": "chore/weekly-community-faq-cordys",
        "min_md": 30,
    },
}

DEFAULT_PRODUCT = "jumpserver"

# ---------------------------------------------------------------- 社区值班人轮换
# 「社区常见问题」PR 的双复核规则：产品负责人（PRODUCTS[key]["owner"]，各产品固定）
# + 当周社区值班人，两人 Approve 后任意一人可合并。
#
# 轮换本来是四人一轮回（付伟博 / 杨洁 / 邵文杰 / 王光禄），但**存在换班特例**
# （第七轮付伟博与第十轮王光禄互换），因此这里写成「周起点日期 -> 账号」的显式表，
# 不做取模推算 —— 取模遇到换班必然算错，而错挂 reviewer 会静默漏掉一次复核。
#
# 键 = 该轮所在周的**周一**日期（ISO），值 = 该周社区值班人的 GitHub 账号。
# 定时任务在周一 03:00（北京时间）运行，取运行当天所在周（周一~周日）查表。
# 表未覆盖的周（例如约满到期后新增的周）→ oncall_for() 返回空串，
# PR 只挂产品负责人，并在 body 与 Actions 摘要里显式提示「本周值班人未配置」，
# 绝不猜测值班人。
ONCALL_ROTA: dict[str, str] = {
    "2026-10-05": "shouzhiyuxian",   # 第六轮 付伟博
    "2026-10-12": "shouzhiyuxian",   # 第七轮 付伟博（原第十轮，与王光禄换班）
    "2026-10-19": "yangjie-sister",  # 第八轮 杨洁
    "2026-10-26": "fanzhoui",        # 第九轮 邵文杰
    "2026-11-02": "Fit111",          # 第十轮 王光禄（原第七轮，与付伟博换班）
}

# 账号 -> 姓名，仅供 PR body / 日志展示（不参与调度）
ONCALL_NAMES: dict[str, str] = {
    "shouzhiyuxian": "付伟博",
    "yangjie-sister": "杨洁",
    "fanzhoui": "邵文杰",
    "Fit111": "王光禄",
    "gitplayer4": "阮皓",
}


def oncall_for(day=None) -> str:
    """返回 day（默认今天）所在周的社区值班人账号；表未覆盖时返回空串。

    day 可以是 datetime.date；传入 None 时用 date.today()（依赖 TZ=Asia/Shanghai）。
    该函数只看「周一对齐」的日期键，避免跨时区/跨天误差：先算本周周一，再查表。
    """
    import datetime as _dt
    if day is None:
        day = _dt.date.today()
    monday = day - _dt.timedelta(days=day.weekday())
    val = ONCALL_ROTA.get(monday.isoformat(), "")
    if not val:
        log("[community_faq] 本周（{0} 起）未在 ONCALL_ROTA 中配置社区值班人，"
            "PR 将只挂产品负责人".format(monday.isoformat()))
    return val


def owners_for(conf: dict, day=None) -> tuple[str, str]:
    """返回 (产品负责人账号, 当周值班人账号)；两者可能相同（此时调用方去重）。"""
    owner = str(conf.get("owner") or "").strip()
    oncall = oncall_for(day)
    return owner, oncall


# 由 resolve_product() 在 main() 里按 --product 重绑；模块级先给默认值，
# 目的是让所有既有函数（read_page / doc_index / rel_link / compose_entry ...）
# 保持原样——它们直接引用这两个全局名，不需要改成收参数。
DOCS_ROOT = REPO_ROOT / PRODUCTS[DEFAULT_PRODUCT]["docs"]
FAQ_PAGE = DOCS_ROOT / PRODUCTS[DEFAULT_PRODUCT]["faq_rel"]

# 当前生效的产品配置（main() 里随 --product 更新），供提示词与群过滤使用
ACTIVE: dict = dict(PRODUCTS[DEFAULT_PRODUCT], key=DEFAULT_PRODUCT)


def resolve_product(name: str) -> dict:
    """按产品 key 取配置；未知名或已停用一律报参数错误（退出码 2）。"""
    key = (name or "").strip().lower()
    if not key:
        key = DEFAULT_PRODUCT
    conf = PRODUCTS.get(key)
    if not conf:
        raise fail(2, "未知产品 {0!r}，可用：{1}".format(
            key, "、".join(k for k, v in PRODUCTS.items() if v.get("enabled", True))))
    if not conf.get("enabled", True):
        raise fail(2, "产品 {0!r} 已在 PRODUCTS 里停用".format(key))
    return dict(conf, key=key)


def use_product(name: str) -> dict:
    """切换当前产品：重绑 DOCS_ROOT / FAQ_PAGE / ACTIVE 三个模块级变量。

    用 global 重绑而不是把配置对象层层传参：脚本里 16 处都直接读这两个全局名，
    传参要动 6 个函数签名（read_page/doc_index/rel_link/compose_entry/...），
    改动面大、回归风险高；而本脚本是单次运行的单进程脚本，不存在并发切换。
    """
    global DOCS_ROOT, FAQ_PAGE, ACTIVE
    conf = resolve_product(name)
    ACTIVE = conf
    DOCS_ROOT = REPO_ROOT / conf["docs"]
    FAQ_PAGE = DOCS_ROOT / conf["faq_rel"]
    log("[community_faq] 产品 {0} / 文档目录 {1} / FAQ 页面 {2}".format(
        conf["key"], conf["docs"], FAQ_PAGE.relative_to(REPO_ROOT).as_posix()))
    return conf


# ---------------------------------------------------------------- 常量

MSG_PAGE_SIZE = 50
MSG_MAX_PAGES = 20
MSG_WORKERS = 8
HTTP_TIMEOUT = 60
HTTP_RETRIES = 2          # 网络类瞬时错误的重试次数（4xx 不重试）
HTTP_RETRY_BACKOFF = 3    # 重试间隔基数（秒），按次数线性退避

SESSION_PATH_RE = re.compile(r"/storage/session/\S+")
EMOJI_RE = re.compile(r"\[(链接|图片|表情|呲牙|微笑|强|捂脸|破涕为笑|裂开)\]")
CITATION_PLACEHOLDER = "{{PATH}}"

# 群聊机械噪声，仅用于清洗「喂给模型的清单文本」，不改动原始问答对数据
DASH_RUN_RE = re.compile(r"(?:\s*[-—]\s*){3,}")            # 引用块残留的 - - - - 分隔线
QUOTE_NAME_RE = re.compile(r"「[^：:「」\n]{1,20}：\s*")     # 「某某：xxx」里的人名前缀
AT_MENTION_RE = re.compile(r"@[A-Za-z0-9_\u4e00-\u9fa5]+(?:\s+[A-Za-z][A-Za-z0-9_-]*)?")
EMPTY_QUOTE_RE = re.compile(r"「\s*」")

MEDIA_TYPES = frozenset(
    {"image", "emotion", "link", "voice", "video", "file", "weapp", "card", "sphfeed", "news"}
)
QUESTION_MARKERS = (
    "吗", "么", "怎", "哪", "何", "能否", "可否", "行吗", "怎么", "如何",
    "为啥", "为什么", "帮我", "请问", "？", "?", "@",
    "是否", "有没有", "能不能", "可不可以", "行不行", "多少", "多久", "几个",
)
CLOSING_EXACT = frozenset(
    {"好的", "好", "好哒", "好的谢谢", "好的谢谢你", "好的谢谢您", "谢谢", "谢谢你",
     "谢谢您", "感谢", "多谢", "ok", "okay", "收到", "嗯", "哦",
     "好呢", "嗯嗯", "欧克", "okk", "知道了", "明白", "明白了", "没事了",
     "好啦", "好了", "搞定", "已解决", "没问题了", "可以了", "行了", "不用了"}
)

# 无问句特征的消息，至少要这么多「有效字符」（normalize 后，忽略标点与空白）
# 才算开启一个新的提问块。目的：让「好的 / 收到 / 稍等」这类寒暄不要切断上一个问答块。
# 标记型问句不受此限；无标记的长陈述句仍会开启新块，因此不会漏掉「没写问号的真问题」。
QUESTION_MIN_CHARS = 8

# 自动应答机器人（欢迎语 / 客服助理），不计为「同事解答」
BOT_USERIDS = frozenset({"130132198901303490", "wbVkCUDAAAt_oq-BtwsvQ2ImoABXjiuw"})

# 默认模型：百度千帆 v2（OpenAI 兼容）上的 deepseek-v4.1-flash。
# ⚠️ workflow 的 env 里已把同一对「网关 + 模型名」写死，env 优先于这里的默认值；
# 换模型时两处都要改（见文件头「模型相关配置」）。
DEFAULT_LLM_MODEL = "deepseek-v4.1-flash"

# 默认网关：必须与 DEFAULT_LLM_MODEL 在同一处维护，避免「模型换了、默认地址没换」
DEFAULT_LLM_BASE_URL = "https://qianfan.baidubce.com/v2"


# 是否关闭推理型模型的思维链（payload 里发 thinking={"type": "disabled"}），默认关。
# 为什么默认关：reasoning token **计入 max_tokens**，而本任务三次调用都是「按固定格式吐 JSON」，
# 思维链毫无收益却挤占正文预算。实测（deepseek-v4.1-flash，max_tokens=600，同一提问）：
#   不关思考 → completion_tokens 600，其中 reasoning 582，finish_reason=length，正文只剩残句；
#   关掉思考 → completion_tokens 38，finish_reason=stop，正文完整。
# ⚠️ 换用不支持该字段的模型会返回 HTTP 400，届时把 LLM_DISABLE_REASONING 设为 0（报错里也写了）。
def llm_disable_reasoning() -> bool:
    return cfg("LLM_DISABLE_REASONING", "1") not in ("0", "false", "False")

# 采样种子：按 OpenAI 协议透传给网关。
# ⚠️ 不要把可复现性寄托在这个参数上：2026-10-15 实测百度千帆 v2 会**静默忽略** seed
# （同一个 seed 连发两次，返回的正文仍逐字不同），且同一份请求体还会随机返回空结果
# `{"items":[]}`。真正保证「同一批候选里选出同一批条目」的是脚本侧的
# rank_candidates() 按 score 排序，以及 screen_questions() 对空结果的重试。
LLM_SEED = 20261015

# 第一轮选题的空结果重试次数。网关会在**完全相同的请求**上随机返回 `{"items":[]}`，
# 而空数组是合法 JSON、解析不报错，直接采信会把「本期无货」这个错误结论写进报告。
PASS1_ATTEMPTS = 3

# 一个 PR 里条目总数的上限（续接的条目也占名额）。超过就会被截断，目的是让每次
# 评审的量可控；续接多的时候会相应地少选新的，极端情况下本轮一条新的都不加。
MAX_ITEMS_CEILING = 5

# 模型自选条数的下限，仅用于 prompt 引导。**不强制凑够**：模型判断只有 2 条够格时
# 就给 2 条，脚本照实上报（宁缺毋滥），不会硬塞劣质条目来满足下限。
MIN_ITEMS = 3

# 模糊/不确定表述：提示词已明令禁止，这里做机械兜底，命中只记警告、不阻断
VAGUE_PHRASES = ("可能", "大概", "也许", "或许", "似乎", "估计", "不确定",
                 "建议试试", "应该可以", "应该是", "好像是", "听说")

# 第二轮喂给模型的官方文档原文上限（字符）。一旦发生截断，结论就有可能落在
# 被截掉的部分之后——这是机械校验查不出来的准确性上限，必须在报告里标出来供人工核对。
DOC_CHARS_PER_FILE = 5000
DOC_CHARS_TOTAL = 14000


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def cfg(name: str, default: str = "") -> str:
    """读环境变量：未设置、或设为空串时，都回落到 default。

    GitHub Actions 里 `VAR: ${{ vars.X }}` 在 X 未配置时会注入空串，
    若按「仅未设置才用默认值」处理，默认模型/默认地址就会失效。
    """
    return str(os.environ.get(name) or default).strip()


def fail(code: int, msg: str) -> SystemExit:
    log(f"[community_faq] ERROR: {msg}")
    return SystemExit(code)


# ---------------------------------------------------------------- HTTP

def http_json(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    body: dict | None = None,
    headers: dict | None = None,
    timeout: int = HTTP_TIMEOUT,
) -> dict:
    if params:
        pairs: list[tuple[str, str]] = []
        for k, v in params.items():
            if v is None:
                continue
            pairs.append((k, str(v)))
        url = f"{url}?{urllib.parse.urlencode(pairs)}"

    data = None
    hdrs = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    hdrs.update(headers or {})

    last_err: Exception | None = None
    for attempt in range(HTTP_RETRIES + 1):
        if attempt:
            wait = HTTP_RETRY_BACKOFF * attempt
            log(f"[community_faq] 第 {attempt} 次重试（{wait}s 后）: {method} {url}")
            time.sleep(wait)
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as err:
            detail = ""
            try:
                detail = err.read().decode("utf-8", "replace")[:400]
            except Exception:
                pass
            last_err = RuntimeError(f"HTTP {err.code} {url} :: {detail}")
            if err.code < 500 and err.code != 429:
                raise last_err from err  # 4xx 是确定性错误，重试没有意义
            continue
        except urllib.error.URLError as err:
            last_err = RuntimeError(f"网络不可达 {url} :: {err.reason}")
            continue
        except TimeoutError as err:
            last_err = RuntimeError(f"请求超时 {url} :: {err}")
            continue

        try:
            return json.loads(raw)
        except json.JSONDecodeError as err:
            # 网关偶发返回半截响应，重试通常能恢复
            last_err = RuntimeError(f"响应不是 JSON: {url} :: {raw[:200]}")
            continue

    raise last_err or RuntimeError(f"请求失败 {method} {url}")


# ---------------------------------------------------------------- 芝麻会话取数

def zhima_base() -> str:
    url = cfg("ZHIMA_BASE_URL").rstrip("/")
    if not url:
        raise fail(2, "缺少 ZHIMA_BASE_URL")
    return url


def zhima_login() -> str:
    """账密换 token。管理端 login 接口字段是 username，不是 account。

    ⚠️ 拿到的 token 必须走 ``Authorization: Bearer <token>``（见 zhima_headers）。
    裸 token 会被判 ``401 登录过期`` —— 登录明明是成功的，报错却指向登录，
    2026-09-23 踩过这个坑（误以为是账号密码问题）。
    """
    account = cfg("ZHIMA_ACCOUNT")
    password = cfg("ZHIMA_PASSWORD")
    if not account or not password:
        raise fail(2, "缺少 ZHIMA_ACCOUNT / ZHIMA_PASSWORD")
    res = http_json(
        "POST",
        f"{zhima_base()}/api/auth/password/login",
        body={"username": account, "password": password},
    )
    if res.get("status") != "success":
        raise fail(1, f"芝麻会话登录失败: {res.get('error_message') or res}")
    token = (res.get("data") or {}).get("token")
    if not token:
        raise fail(1, f"登录响应无 token: {str(res)[:200]}")
    return str(token)


def zhima_headers(token: str) -> dict[str, str]:
    """芝麻接口统一的鉴权头。

    ⚠️ 必须带 ``Bearer `` 前缀：login 返回的 token 是裸 JWT（自身不含 Bearer），
    少这个前缀会被服务端判 ``401 登录过期``。
    """
    return {"Authorization": f"Bearer {token}"}


def zhima_groups(token: str) -> list[dict]:
    """拉社区小助手名下全部群（未过滤）。"""
    staff = cfg("ZHIMA_SCOPE_STAFF_USERID", "SheQuXiaoZhuShou")
    out: list[dict] = []
    page = 1
    total = 0
    while page <= 20:
        res = http_json(
            "GET",
            f"{zhima_base()}/api/chats/by/staff/room/conversation/list",
            params={"staff_userid": staff, "page": page, "size": 50},
            headers=zhima_headers(token),
        )
        if res.get("status") != "success":
            raise fail(1, f"拉取群列表失败: {res.get('error_message') or res}")
        data = res.get("data") or {}
        items = data.get("items") or []
        for item in items:
            if not isinstance(item, dict):
                continue
            chat_id = item.get("chat_id") or item.get("to")
            if not chat_id:
                continue
            name = str(item.get("remark_name") or item.get("name") or "")
            out.append({"chat_id": str(chat_id), "name": name})
        total = int(data.get("total") or 0)
        if not items or (total and len(out) >= total) or len(items) < 50:
            break
        page += 1
    log(f"[community_faq] 范围群 {len(out)} 个（total={total}）")
    return out


def group_label(name: str, keyword: str) -> str:
    """把群名清洗成短标签，用于日志与「来源」字段。

    原实现只写死剥掉字面量 "JumpServer "，换成别的产品就完全不起作用（标签仍是
    「DataEase 交流群 5」这种带产品名与前缀的长串，日志里挤成一团）。这里按
    「剥离产品关键词 → 去掉空白与分隔符 → 去掉结尾的编号」的顺序generic 清洗：
        JumpServer 交流群 5        -> 交流群 5   -> 交流群 5 -> 交流群 5（编号保留）
        DataEase 交流群            -> 交流群
        1Panel VIP 交流群8         -> VIP 交流群8
        JumpServer 学习班交流群     -> 学习班交流群
    """
    label = name
    # 按关键词整串剥离（大小写不敏感），关键词可能出现在开头或中间
    idx = label.lower().find(keyword.lower())
    if idx >= 0:
        label = label[:idx] + label[idx + len(keyword):]
    label = label.strip(" -_·|/、").strip()
    label = re.sub(r"\s+", " ", label)
    return label or "交流群"


def product_groups(groups: list[dict], keyword: str) -> list[dict]:
    """按关键词挑出该产品的交流群，剔除排除项，并清洗出短标签。

    排除项来自 PRODUCTS[key]['exclude']：1Panel 的「1Panel VIP 交流群8」同样命中
    '1panel'，但那是付费客户群而非普通交流群，混进来会污染选题口径。
    """
    kw = (keyword or "").lower()
    if not kw:
        raise fail(2, "群名过滤关键词为空，无法定位交流群")
    excludes = [str(x).lower() for x in (ACTIVE.get("exclude") or []) if str(x).strip()]
    kept: list[dict] = []
    skipped: list[str] = []
    for g in groups:
        low = g["name"].lower()
        if kw not in low:
            continue
        if any(x in low for x in excludes):
            skipped.append(g["name"])
            continue
        g["label"] = group_label(g["name"], kw)
        kept.append(g)
    log("[community_faq] 命中关键词 {0!r} 的群 {1} 个".format(keyword, len(kept)))
    if skipped:
        log("[community_faq] 已排除 {0} 个群（命中 {1}）：{2}".format(
            len(skipped), "/".join(excludes), "、".join(skipped)))
    return kept


def zhima_staff_directory(token: str) -> list[dict]:
    out: list[dict] = []
    page = 1
    while page <= 40:
        res = http_json(
            "GET",
            f"{zhima_base()}/api/staff/list",
            params={"page": page, "limit": 50},
            headers=zhima_headers(token),
        )
        if res.get("status") != "success":
            raise fail(1, f"拉取员工目录失败: {res.get('error_message') or res}")
        data = res.get("data") or {}
        items = data.get("items") or []
        out.extend(x for x in items if isinstance(x, dict))
        total = int(data.get("total") or 0)
        if not items or (total and len(out) >= total) or len(items) < 50:
            break
        page += 1
    return out


def staff_roster(token: str) -> tuple[set[str], dict[str, str]]:
    """返回 (官方人员 userid 集合, userid→姓名 映射)。

    ZHIMA_DEPT_STAFF 只用于**标记**「官方人员」（高信任来源），**不做过滤**：
    名单外同事的答复仍会保留，只是标记为「普通同事答复」（低信任）。

    姓名映射始终尝试拉取（报告与提示词里要标注「是谁答的」）；目录接口抖动时
    只记警告、不中断整周任务 —— 名单与姓名退化为空，问答对照常生成。
    """
    raw = cfg("ZHIMA_DEPT_STAFF")
    wanted: list[tuple[str, list[str]]] = []
    if raw:
        try:
            spec = json.loads(raw)
        except json.JSONDecodeError as err:
            raise fail(2, f"ZHIMA_DEPT_STAFF 不是合法 JSON: {err}") from err
        if isinstance(spec, dict):
            spec = spec.get("staff") or []
        if not isinstance(spec, list):
            raise fail(2, "ZHIMA_DEPT_STAFF 应为 [{\"name\": \"...\"}, ...]")
        for row in spec:
            if isinstance(row, str) and row.strip():
                wanted.append((row.strip(), []))
            elif isinstance(row, dict) and str(row.get("name") or "").strip():
                aliases = [str(a).strip() for a in (row.get("aliases") or []) if str(a).strip()]
                wanted.append((str(row["name"]).strip(), aliases))
        if not wanted:
            raise fail(2, "ZHIMA_DEPT_STAFF 里没有有效姓名")

    try:
        directory = zhima_staff_directory(token)
    except SystemExit:
        raise
    except Exception as err:  # 目录接口抖动不应让整周任务失败（姓名/标记退化为空即可）
        log(f"[community_faq] 拉取员工目录失败，解答人姓名与官方标记将为空: {err}")
        directory = []

    by_name: dict[str, str] = {}
    names: dict[str, str] = {}
    for rec in directory:
        uid = str(rec.get("userid") or "")
        if not uid:
            continue
        name = str(rec.get("name") or "").strip()
        names[uid] = name or "同事"
        if name and name not in by_name:
            by_name[name] = uid

    ids: set[str] = set()
    missed: list[str] = []
    for name, aliases in wanted:
        uid = by_name.get(name) or next((by_name[a] for a in aliases if a in by_name), None)
        if uid:
            ids.add(uid)
        else:
            missed.append(name)
    if wanted:
        log(f"[community_faq] 官方人员名单命中 {len(ids)}/{len(wanted)} 人" + (f"，未匹配: {missed}" if missed else ""))
    return ids, names


def fetch_day_messages(token: str, chat_id: str, day: str) -> list[dict]:
    rows: list[dict] = []
    page = 1
    while page <= MSG_MAX_PAGES:
        res = http_json(
            "GET",
            f"{zhima_base()}/api/chats/by/group/message/list",
            params={
                "group_chat_id": chat_id,
                "page": page,
                "size": MSG_PAGE_SIZE,
                "msg_start_time": f"{day} 00:00:00",
                "msg_end_time": f"{day} 23:59:59",
            },
            headers=zhima_headers(token),
        )
        if res.get("status") != "success":
            # 抛给上层统一统计失败次数。这里若只是 log + break，
            # 「接口整体不可用」会被伪装成「本周群里没有消息」，静默跳过一整周。
            raise RuntimeError(
                "拉取消息失败 group={0} day={1}: {2}".format(
                    chat_id, day, res.get("error_message") or str(res)[:200])
            )
        data = res.get("data") or {}
        items = data.get("items") or []
        rows.extend(x for x in items if isinstance(x, dict))
        total = int(data.get("total") or 0)
        if not items or (total and len(rows) >= total) or len(items) < MSG_PAGE_SIZE:
            break
        page += 1
    return rows


# ---------------------------------------------------------------- 问答对提取

def msg_text(msg: dict) -> str:
    raw = msg.get("raw_content")
    if isinstance(raw, dict):
        for key in ("content", "title", "description"):
            val = raw.get(key)
            if val:
                return str(val)
    return str(msg.get("msg_content") or "")


def clean_text(text: str) -> str:
    s = SESSION_PATH_RE.sub("", str(text or ""))
    s = EMOJI_RE.sub("", s)
    s = re.sub(r"-{5,}", " ", s)
    return re.sub(r"[ \t]+", " ", s).strip()


def normalize_text(text: str) -> str:
    s = EMOJI_RE.sub("", str(text or ""))
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"[，。,.!！、/｜|～~\s]+", "", s)
    return s.strip().lower()


def role_of(msg: dict):
    r = msg.get("from_role")
    if isinstance(r, dict):
        r = r.get("value")
    try:
        return int(r)
    except (TypeError, ValueError):
        return None


def is_question(msg: dict) -> bool:
    """判断这条消息是否「开启一个新的提问块」。

    收窄了原先「只要不是道别语就算提问」的口径：没有问句特征时，要求内容有
    足够长度（QUESTION_MIN_CHARS）才开启新块，避免「好的 / 收到 / 稍等」这类寒暄
    把上一个问答块切断。注意收窄**不会丢内容**——提问块一旦已开启，后续客户消息
    仍会被并入该块（见 extract_pairs 的 role == 1 分支）。
    """
    text = msg_text(msg)
    if any(mark in text for mark in QUESTION_MARKERS):
        return True
    n = normalize_text(text)
    if not n or n in CLOSING_EXACT:
        return False
    return len(n) >= QUESTION_MIN_CHARS


def is_noise(text: str) -> bool:
    return len(normalize_text(text)) < 6


def strip_trailing_chatter(text: str) -> str:
    """剥掉提问块尾部粘连的寒暄词（「…能升级吗 好的 收到」→「…能升级吗」）。

    多轮问答里客户的确认语会并进上一个提问块（见 extract_pairs），不清理会污染
    喂给模型的清单文本。只剥尾部、且要求剥完还剩内容，避免把纯寒暄块剥成空串。
    """
    parts = [p for p in str(text or "").split(" ") if p]
    while len(parts) > 1 and normalize_text(parts[-1]) in CLOSING_EXACT:
        parts.pop()
    return " ".join(parts).strip()


def is_staff(msg: dict) -> bool:
    """我方员工角色且不在机器人黑名单。官方名单只用于**标记**，不参与过滤。"""
    return str(msg.get("from") or "") not in BOT_USERIDS


def extract_pairs(msgs: list[dict], official: set[str], names: dict[str, str],
                  group: str, day: str) -> list[dict]:
    """按时间序把「客户提问块 → 同事解答块」配对。

    official 是官方人员 userid 集合，**只用于给问答对打标记**（official=True/False），
    不再据此丢弃名单外同事的回复 —— 名单外同事的答复同样是「员工已答」的证据，
    只是信任级别更低，交由第二轮按分级来源标准审核（猜测/只给排查方向会被放弃）。
    """
    timed = sorted(
        ((str(m.get("msg_time") or ""), m) for m in msgs if m.get("msg_time")),
        key=lambda x: x[0],
    )
    pairs: list[dict] = []
    q_buf: list[str] = []
    q_ts = ""
    a_buf: list[str] = []
    a_ids: list[str] = []      # 本次解答块的发言人 userid（去重、保持出现顺序）
    a_names: list[str] = []    # 与 a_ids 一一对应的显示名

    def flush() -> None:
        nonlocal q_buf, a_buf, q_ts, a_ids, a_names
        q_text = strip_trailing_chatter(clean_text(" ".join(q_buf)))
        a_text = clean_text(" ".join(a_buf))
        if q_text and not is_noise(q_text) and a_text:
            pairs.append({
                "date": day,
                "group": group,
                "time": q_ts[11:16],
                "question": q_text[:600],
                "answer": a_text[:1200],
                "answerer": "、".join(a_names) or "",
                "answerer_ids": a_ids,
                "official": any(i in official for i in a_ids),
            })
        q_buf, a_buf, q_ts, a_ids, a_names = [], [], "", [], []

    for ts, msg in timed:
        role = role_of(msg)
        text = clean_text(msg_text(msg))
        if role == 1:  # 客户
            if is_question(msg) or not q_buf:
                if a_buf:
                    flush()
                if not q_buf:
                    q_ts = ts
            if text:
                q_buf.append(text)
        elif role == 2 and is_staff(msg):  # 我方同事
            if q_buf or a_buf:
                a_buf.append(text)
                sender = str(msg.get("from") or "")
                if sender and sender not in a_ids:
                    a_ids.append(sender)
                    a_names.append(names.get(sender) or "同事")
    flush()
    return pairs


def collect_pairs(days: int, keyword: str) -> tuple[list[dict], list[dict], dict]:
    """取数并配对。

    返回值第三个元素是取数完整性统计（attempts/failures/rows）——调用方据此区分
    「接口挂了」和「群里确实没消息」，避免把取数失败当成「本周无新增」。
    """
    token = zhima_login()
    groups = product_groups(zhima_groups(token), keyword)
    if not groups:
        raise fail(1, "没有匹配到任何交流群，请检查关键词 {0!r}（PRODUCTS 表或 PRODUCT_KEYWORD）".format(keyword))
    official, names = staff_roster(token)
    if official:
        log("[community_faq] 官方人员 {0} 人：其答复标记为高信任来源，名单外同事的答复仍保留（低信任来源）".format(len(official)))
    else:
        log("[community_faq] 未配置或未匹配 ZHIMA_DEPT_STAFF，所有员工答复一律按「普通同事答复」处理")

    today = date.today()
    day_list = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    log("[community_faq] 数据窗口 {0} … {1}（{2} 天）".format(day_list[0], day_list[-1], len(day_list)))

    stats = {"attempts": 0, "failures": 0, "rows": 0}
    all_pairs: list[dict] = []
    by_day: list[dict] = []
    for day in day_list:
        day_pairs: list[dict] = []
        with ThreadPoolExecutor(max_workers=MSG_WORKERS) as pool:
            futs = {pool.submit(fetch_day_messages, token, g["chat_id"], day): g for g in groups}
            for fut in as_completed(futs):
                g = futs[fut]
                stats["attempts"] += 1
                try:
                    rows = fut.result()
                except Exception as err:  # 单群失败不影响整体，但计入 failures
                    stats["failures"] += 1
                    log(f"[community_faq] 群 {g['label']} {day} 拉取异常: {err}")
                    continue
                stats["rows"] += len(rows)
                day_pairs.extend(extract_pairs(rows, official, names, g["label"], day))
        log(f"[community_faq] {day} 问答对 {len(day_pairs)} 条")
        by_day.append({"date": day, "pairs": len(day_pairs)})
        all_pairs.extend(day_pairs)

    log("[community_faq] 取数统计：请求 {attempts} 次、失败 {failures} 次、消息 {rows} 条".format(**stats))
    return all_pairs, by_day, stats


# ---------------------------------------------------------------- 提问清单

DIGEST_MAX_ITEMS = 300
DIGEST_QUESTION_CHARS = 100


def scrub_question(text: str) -> str:
    """压掉群聊机械噪声：引用块里的发言人前缀、残留分隔线、@提及。

    只作用于喂给模型的清单文本，不改动原始问答对数据。
    """
    s = str(text or "")
    s = DASH_RUN_RE.sub(" ", s)
    s = QUOTE_NAME_RE.sub("「", s)
    s = AT_MENTION_RE.sub("", s)
    s = EMPTY_QUOTE_RE.sub(" ", s)
    s = re.sub(r"「\s+", "「", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def build_question_digest(pairs: list[dict]) -> str:
    """把提问压成「编号 + 日期 + 群 + 问题」清单。

    按问题文本排序，让近义问题在清单里相邻，便于模型归组；编号是 pairs 的下标。
    """
    if len(pairs) > DIGEST_MAX_ITEMS:
        log("[community_faq] 问答对 {0} 条超过上限，清单只取前 {1} 条".format(len(pairs), DIGEST_MAX_ITEMS))
    rows: list[tuple[str, str]] = []
    for idx, pair in enumerate(pairs[:DIGEST_MAX_ITEMS]):
        q = scrub_question(pair["question"])[:DIGEST_QUESTION_CHARS]
        flag = "[官方已答] " if pair.get("official") else ""
        rows.append((normalize_text(q), "[{0}] {1} {2} | {3}{4}".format(
            idx, pair["date"], pair["group"], flag, q)))
    rows.sort()
    digest = "\n".join(line for _, line in rows)
    log("[community_faq] 第一轮模型输入：提问清单 {0} 行 / {1} 字符".format(len(rows), len(digest)))
    return digest


def valid_question_ids(item: dict, total: int) -> list[int]:
    """校验模型给出的问题编号：越界、非数字一律丢弃。"""
    out: list[int] = []
    for raw in item.get("question_ids") or []:
        try:
            idx = int(raw)
        except (TypeError, ValueError):
            continue
        if 0 <= idx < total and idx not in out:
            out.append(idx)
    return out


def digest_limit(total: int) -> int:
    """模型实际能看到的编号上限。

    清单只发前 DIGEST_MAX_ITEMS 条，编号校验必须与清单一致，
    否则 300 以上的编号会「校验通过、但模型根本没在清单里见过」。
    """
    return min(total, DIGEST_MAX_ITEMS)


# ---------------------------------------------------------------- 页面读写

def read_page() -> str:
    if not FAQ_PAGE.is_file():
        raise fail(2, f"页面不存在: {FAQ_PAGE}")
    return FAQ_PAGE.read_text(encoding="utf-8")


def page_sections(text: str) -> tuple[list[dict], int]:
    """解析页面 H2 小节，返回 ([{no,title,line_start,line_end,minors}], 最大编号)。"""
    lines = text.splitlines()
    heads: list[tuple[int, int, str]] = []
    for i, line in enumerate(lines):
        m = re.match(r"^##\s+(\d+)\s+(.+?)\s*$", line)
        if m:
            heads.append((i, int(m.group(1)), m.group(2)))
    sections: list[dict] = []
    for idx, (line_no, num, title) in enumerate(heads):
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        minors: list[int] = []
        for j in range(line_no + 1, end):
            m = re.match(r"^###\s+(\d+)\.(\d+)\b", lines[j])
            if m:
                minors.append(int(m.group(2)))
        sections.append({"no": num, "title": title, "line_start": line_no,
                         "line_end": end, "minors": minors})
    return sections, max((s["no"] for s in sections), default=0)


def existing_entry_keys(text: str) -> set[str]:
    """页面已有条目的「标题 + 问题描述」清单，编号前缀已剥离。

    机械判重用的 key（精确比对 + bigram 近似比对都基于它）。标题去掉了「1.3 」这类
    编号，避免编号噪声；同时把「**问题**」那行也纳进来——同义问法经常只差在问题描述里
    （例如新问题与既有条目的**问题**行同义）。
    """
    keys: set[str] = set()
    for line in text.splitlines():
        m = re.match(r"^###\s+\d+\.\d+\s+(.+?)\s*$", line)
        if m:
            keys.add(normalize_text(m.group(1))[:40])
        m = re.match(r"^\*\*问题\*\*[：:]\s*(.+?)\s*$", line)
        if m:
            keys.add(normalize_text(m.group(1))[:40])
    return {k for k in keys if k}


def existing_entries_digest(text: str, max_items: int = 120) -> str:
    """页面已有条目的「编号 标题 ｜ 问题：描述」清单（喂给模型判重用）。

    只给标题时，换了说法的同义问法容易漏判——例如新问题「升级后提示 Lion 组件离线
    如何处理」与旧标题「升级到 v5 后发现没有 lion 组件？」字面几乎不重合，但两者指的
    是同一件事。带上「**问题**」那行后，语义重复更容易被模型识破。
    """
    out: list[str] = []
    cur = ""
    for line in text.splitlines():
        m = re.match(r"^###\s+(\d+\.\d+)\s+(.+?)\s*$", line)
        if m:
            if cur:
                out.append(cur)
            cur = "{0} {1}".format(m.group(1), m.group(2)[:60])
            continue
        m = re.match(r"^\*\*问题\*\*[：:]\s*(.+?)\s*$", line)
        if m and cur and "｜" not in cur:
            cur = "{0} ｜ 问题：{1}".format(cur, m.group(1)[:80])
    if cur:
        out.append(cur)
    return "\n".join(out[:max_items])


NEAR_DUP_THRESHOLD = 0.7


def _bigrams(text: str) -> set[str]:
    """标题去重用的字符 bigram 集合。

    比中文单字粒度大：单字会引入大量口水字（如提示/如何/处理），把「A 组件离线」
    与「B 组件离线」错判成重复；bigram 保留「Lion」「组件」这类词形，噪声更低。
    """
    s = normalize_text(text)
    if not s:
        return set()
    if len(s) < 2:
        return {s}
    return {s[i:i + 2] for i in range(len(s) - 1)}


def near_duplicate(title: str, keys: set[str], threshold: float = NEAR_DUP_THRESHOLD) -> str | None:
    """标题近似重复检测（字符 bigram 的 Dice 系数），命中则返回最像的已有标题。

    精确比对只能抓「一字不差」的标题，换个说法问同一件事就漏了；这里做一层近似兜底。
    标题太短（bigram < 5，约 6 字以内）时不判断，避免误伤短标题。
    """
    a = _bigrams(title)
    if len(a) < 5:
        return None
    best, best_score = None, 0.0
    for k in keys:
        b = _bigrams(k)
        if not b:
            continue
        score = 2 * len(a & b) / (len(a) + len(b))
        if score > best_score:
            best, best_score = k, score
    return best if best_score >= threshold else None


def resolve_doc_path(raw: str, index: list[str]) -> str:
    """把模型给出的文档路径纠正为索引里真实存在的路径（精确 -> 逐步放宽）。

    模型经常把目录拼错（例如把 workbench/my_assets/file_transfer.md 写成
    web_terminal/file_transfer.md）。若严格要求 `raw in index`，一条有价值的问题会因为
    一个拼错路径被整条判死，所以这里做模糊纠正。
    确实找不到时返回空字符串——**只表示本条没有文档依据，不表示条目作废**
    （依据可以来自群内答复）。
    """
    p = (raw or "").strip().strip("\"'").split("#", 1)[0].split("?", 1)[0].strip()
    if not p:
        return ""
    low = p.lower()
    # 前缀剥离必须按**当前产品**的文档目录名来：写死 "jumpserver-docs/" 时，
    # dataease 的模型输出若带上 "dataease-docs/" 前缀就剥不掉，路径直接匹配失败。
    for pref in ("docs/", ACTIVE["docs"].lower() + "/", ACTIVE["key"] + "/", "/"):
        if low.startswith(pref):
            p, low = p[len(pref):], low[len(pref):]
    p = p.lstrip("./")
    if p in index:
        return p

    def norm(s: str) -> str:
        # 忽略大小写与 - _ . / 差异："workbench/my-assets.md" 与 "workbench/my_assets.md" 视为同一篇
        return re.sub(r"[-_/.]", "", s).lower()

    np = norm(p)
    if np:
        hits = [c for c in index if norm(c) == np]
        if len(hits) == 1:
            return hits[0]

    name = p.rsplit("/", 1)[-1]
    same = [c for c in index if c.rsplit("/", 1)[-1] == name]
    if len(same) == 1:
        return same[0]
    if len(same) > 1:
        # 多个同名文件：选父目录片段命中最多的（模型常只写错中间一层目录）
        parents = [s for s in p.split("/")[:-1] if s]
        scored = sorted(same, key=lambda c: -sum(1 for s in parents if s in c.split("/")))
        if parents and sum(1 for s in parents if s in scored[0].split("/")):
            return scored[0]

    if "/" in p:
        suffix = [c for c in index if c.endswith("/" + p)]
        if len(suffix) == 1:
            return suffix[0]
    if np:
        fuzzy = [c for c in index if np in norm(c)]
        if len(fuzzy) == 1:
            return fuzzy[0]
    return ""


def doc_index() -> list[str]:
    out: list[str] = []
    for path in sorted(DOCS_ROOT.rglob("*")):
        if path.suffix not in (".md", ".mdx"):
            continue
        rel = path.relative_to(DOCS_ROOT).as_posix()
        if rel.startswith("faq/"):
            continue
        out.append(rel)
    return out


def rel_link(doc_path: str) -> str:
    """把文档相对路径转成 FAQ 页面可用的相对链接。

    非法路径（空、带协议、绝对路径、含 ..）一律返回空串——宁可少一个链接，
    也不要在页面里生成指向不存在文档的裸链接（会 404）。
    """
    p = (doc_path or "").strip()
    if not p or "://" in p or p.startswith("/") or ".." in p.split("/"):
        return ""
    root = DOCS_ROOT.resolve()
    target = (root / p).resolve()
    if str(target) != str(root) and not str(target).startswith(str(root) + os.sep):
        return ""
    return os.path.relpath(target, FAQ_PAGE.parent).replace(os.sep, "/")


# ---------------------------------------------------------------- 大模型

def llm_endpoint() -> tuple[str, str, str]:
    base = cfg("LLM_BASE_URL", DEFAULT_LLM_BASE_URL).rstrip("/")
    key = cfg("LLM_API_KEY")
    model = cfg("LLM_MODEL", DEFAULT_LLM_MODEL)
    if not key:
        raise fail(2, "缺少 LLM_API_KEY")
    return base, key, model


def llm_models(base: str, key: str) -> list[str]:
    res = http_json("GET", f"{base}/models", headers={"Authorization": f"Bearer {key}"})
    data = res.get("data") if isinstance(res, dict) else None
    if isinstance(data, list):
        return [str(x.get("id")) for x in data if isinstance(x, dict) and x.get("id")]
    return []


def llm_chat(messages: list[dict], *, temperature: float = 0.2, max_tokens: int = 4096) -> str:
    base, key, model = llm_endpoint()
    if not model:
        try:
            available = llm_models(base, key)
        except Exception as err:
            raise fail(4, f"无法确定模型名，且列模型失败（多为网关不可达）: {err}") from err
        raise fail(2, f"缺少 LLM_MODEL，网关可用模型: {', '.join(available) or '(空)'}")
    payload = {"model": model, "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens,
               # 采样种子按协议透传。注意千帆 v2 实测会忽略它（见 LLM_SEED 注释），
               # 别指望靠它复现；真正决定入选集合的是 rank_candidates() 的脚本侧排序。
               "seed": LLM_SEED}
    if llm_disable_reasoning():
        # 关掉推理型模型的思维链：deepseek-v4.1-flash 等会先输出 reasoning_content，
        # 而 reasoning token **同样计入 max_tokens** —— 预算被「思考」吃掉后 content 就成了空串/残句。
        # 本任务三次调用都是「按固定格式吐 JSON」，不需要思维链；关掉后 Token 全用于正文、响应更快。
        payload["thinking"] = {"type": "disabled"}
    try:
        res = http_json("POST", f"{base}/chat/completions", body=payload,
                        headers={"Authorization": f"Bearer {key}"}, timeout=180)
    except RuntimeError as err:
        if llm_disable_reasoning() and "400" in str(err):
            raise fail(4, "模型网关拒绝了 thinking={'type':'disabled'}（HTTP 400）：该模型不支持关闭"
                          "思维链。请把 LLM_DISABLE_REASONING 设为 0 后重试，或改用支持关闭的非推理"
                          "模型。模型={0} / 网关={1}".format(model, base)) from err
        raise fail(4, "模型调用失败（网关 {0}）: {1}".format(base, err)) from err
    choices = res.get("choices") or []
    if not choices:
        raise fail(4, f"模型无返回: {str(res)[:300]}")
    choice = choices[0] or {}
    message = choice.get("message") or {}
    content = str(message.get("content") or "")
    # 兜底：正常情况下思维链已被 thinking=disabled 关掉，不会走到这里。
    # 保留是为了 LLM_DISABLE_REASONING 被置 False、或静默降级的老网关仍返回推理内容时，
    # 能明确报出「预算被思考吃掉」而不是让调用方拿空串去 json_block() 后误报「模型不会输出 JSON」。
    if not content and choice.get("finish_reason") == "length":
        raise fail(4, "模型输出被 max_tokens 截断（reasoning_content 占满了预算，content 为空）："
                      "请调大 max_tokens 后重试，或确认 LLM_DISABLE_REASONING 未被设为 0。模型={0}"
                      .format(model))
    return content


def json_block(text: str):
    """从模型输出里抠出 JSON（容忍 ```json 包裹与前后废话）。"""
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidate = fenced.group(1) if fenced else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"模型输出没有 JSON: {text[:200]}")
    return json.loads(candidate[start:end + 1])


def version_rule() -> str:
    """把当前产品的版本口径写成一句提示词约束（无版本口径时返回空串）。

    ⚠️ 原实现把「只收 JumpServer V5 相关…未标注版本一律按 V5 处理」写死在提示词里，
    换成别的产品会让模型按错误的大版本口径筛问题（DataEase 的 v3 提问会被当成
    「旧版本特性」漏收）。这里的文案随 PRODUCTS[key]['version_scope'] 生成。
    """
    scope = str(ACTIVE.get("version_scope") or "").strip()
    if not scope:
        return ("  - 不限大版本：群聊里各版本的提问都可收；只有明确属于**已停止维护的旧版本**"
                "（且当前主线已不适用）的问题才不选。\n")
    return (
        "  - 只收 {0} 相关。群聊多数不写版本，**未标注版本的一律按当前主线 {0} 处理**，\n"
        "    不要因「没写版本」就排除；只有明确指向旧版本特性（明说「老版本/升级前」、\n"
        "    或该特性在当前主线已废弃）才不选。\n"
    ).format(scope)


def product_prompt_vars() -> dict:
    """提示词模板变量：产品名 + 产品 key + 该产品的版本口径约束。"""
    return {
        "product": ACTIVE["name"],
        "product_key": ACTIVE["key"],
        "version_rule": version_rule(),
    }


PASS1_SYSTEM = """你是 {product} 官方文档的维护者。
下面给你社区交流群最近一周的全部提问清单（形如 `[编号] 日期 群 | 问题`）。
任务：先把语义相同的问题归为同一主题，再判断每个主题**是否值得沉淀进官方「社区常见问题」页**。

■ 第一原则（最重要）：
  FAQ 不是社区问题的简单搬运，也不是官方文档的二次摘要。
  **相关文档 ≠ 有 FAQ 价值；能回答 ≠ 值得沉淀。**
  这一页是「社区常见问题」：只沉淀**别人也会遇到、且有明确答案**的问题。
  判断标准就两条：① **可复用**——换个人、换个群、过一阵子，是不是还会有人问同一件事；
  ② **有答案**——群里或官方资料里有一个**说得清**的结论。
  满足这两条就收，**不要求问题有多深**（常见的配置、限制、踩坑都算）；
  但一次性个案、没结论、纯寒暄这三类，即使有答案也不要。
  判断依据是「可复用 + 有答案」，**不是出现频率**。
  （「官方文档里已经写得很清楚」的问题不在这里淘汰——你这里看不到文档正文，
    先照收，由后面读了正文的环节裁决。）

■ 对每个主题，先归类，再决定是否收录（四类）：
  A. 常见问题（**收录**）：换个人也会问、且有明确答案。两类都属于 A：
     - 知识型：为什么升级后行为变了 / 某功能在哪个版本调整或废弃 / 某组件是否被合并替换 /
       老配置升级后是否还适用 / 支持哪些数据库或环境 / 某功能有什么限制或使用前提 /
       某参数有哪些明确限制 / 看似正确其实还需额外配置、改参数必须重启、
       操作顺序有明确要求等常见误区。
     - 常见使用与配置咨询：反复有人问、且群里有明确答复的配置类问题
       （如某功能要开哪个开关才生效、某处必须改哪个参数）。
       **不要求是疑难**，只要对后来的人有参考价值就收。
  B. 一次性个案（**不收录**）：只对提问者本人 / 他自己那套环境成立的问题——
     「我这边报了这个错（见截图）」、「我们的环境是……」、「帮我看看我这台机器」，
     无法抽象成别人也会遇到的问题。
  C. 故障排查（**有明确结论才收录**）：如「LDAP 测试连接成功但导入用户失败，为什么」。
     只有当官方资料（文档或官方人员答复）能明确说明「现象 → 原因 → 处理方式」时才收录；
     若只有「用户遇到问题 + 同事猜测原因」，**不能把猜测包装成确定答案**，不选。
  D. 未解决 / 无结论（**不收录**）：答复只是猜测、「你试试」、「先排查下」；疑似 Bug 但无官方确认；
     纯寒暄或已解决的确认语（「好的」「收到了」）。

■ 明确排除（命中任一即不选）：
  - 一次性特殊环境问题（某客户特殊网络/代理/防火墙、某台机器浏览器异常等），
    除非能抽象成产品级、普遍存在的问题；
  - 没有明确结论、只能靠猜测或「视情况而定」的问题；
  - 纯寒暄、纯确认语；
  - 与「已有条目」重复或语义相同（含换说法的同义问法）——问的是同一件事就跳过。

■ 决策链（逐条走，任一关键条件不满足就倾向不选）：
  换个人、换个群，是不是也会问同一件事？（不会 → 属一次性个案，淘汰）
  → 群里或官方资料里，有没有一个**说得清**的答案？（只有猜测 / 排查方向 / 没结论 → 淘汰）
  → 是不是只有提问者自己的环境才成立的现象？（是 → 淘汰）
  → 与「已有条目」是否重复？（重复 → 淘汰）
  → 全部满足才选。「文档里有没有写」不在这一环判断。

■ 判例（照此尺度判断）：
  - 「关闭 Web 终端控制台后如何返回？」→ 问的人多、答案也明确，**这里可以选**；
    不要因为「看起来像 UI 操作」就淘汰——它收不收，交给后面读了文档正文的环节决定。
  - 「LDAP 测试成功但导入用户报 500」→ 群里或官方资料明确说了原因 → **选**；
    若只有同事猜「可能要先同步用户」而无任何确认 → **不选**（不能把猜测当结论）。
  - 「我们内网环境部署时连不上外网」→ 一次性环境个案 → **淘汰**。

■ 其它硬性约束：
{version_rule}  - 出现次数是参考而非门槛：有复用价值的主题哪怕只出现 1 次也可选；凑数、无复用价值的高频问题不要选。
    question_ids 里编号个数即出现次数，如实填。
  - 事实来源优先级（判断能否核实时遵循）：官方文档 > 官方 FAQ > 官方人员明确答复 > 普通同事答复
    > 用户描述 > 你自身知识。doc_paths 尽量给出官方文档依据；确实找不到可留空数组，
    但**不要为了凑依据硬塞不相关文档**。
  - 注意：官方文档里**没有**相关内容，不能作为排除理由——社区里「文档没写、但官方人员已明确答复」
    的问题恰恰最该沉淀，也是本页相对手册最大的价值。提问带 `[官方已答]` 时优先考虑收录。

■ 输出要求：
1. question_ids 只能用清单里**原样出现过**的编号，不得编造；语义相同才算一组。
2. 选 **{min_items} 到 {max_items} 条**，每条都要给 score（0-100 整数）。**条数由你按质量判断**：
   够格的主题多就选满 {max_items} 条，只有 {min_items} 条够格就只给 {min_items} 条——
   不要为了凑数把「勉强沾边」的塞进来，也不要为了保守把明明够格的压下去。
   排序由脚本按 score 做，你**只需把 score 打准**，不必操心数组顺序；
   确实一条都不值得沉淀时返回空数组（脚本会照实上报，不会硬凑）。
3. doc_paths 尽量从给定文档索引里挑**原样存在**的相对路径，一条优先给一个依据；
   **不确定的路径宁可留空数组，也不要编造**（留空不影响收录，见下面的来源分级）。
4. section 填现有小节标题原文；确实不属于任何现有小节时才填 new_section。
5. kind 填 A/B/C/D 之一（上面四类）。
6. confidence 标「结论是否明确」（high/low）：只有官方资料里能读出
   「现象 → 原因 → 处理方式」的完整链条时才填 high；
   只是有人给了个说法、但没被确认，或你自己也拿不准，填 low。
   **两个取值都要敢用**：绝大多数社区常见问题在官方文档里都能找到完整链条，此时必须填
   high——全部填 low 等于把一半候选直接判死（A 类 confidence=low 会被丢弃），
   反而违背「宁缺毋滥」的初衷。只有真的只有猜测性说法时才填 low。
7. value 用一句话说清「为什么值得沉淀成社区常见问题」（可复用在哪：别人会怎么再问一遍；
   以及答案的确定性来自哪里），不要写「因为出现 N 次」或「文档里有相关内容」。

■ score 打分口径（先按这两条给分，再按参考维度微调）：
  可复用性（换个人、换个群、过一阵子是否还会问）占大头，答案确定性其次。
  参考区间：70-100 = 强可复用且结论明确，本期优先收录；
           40-69  = 有价值但偏窄或结论一般；
           0-39   = 勉强沾边、更像个案或没结论。
  同一批候选之间要有区分度：不要给所有条目都打 80 分，那等于没排序。

只输出 JSON，不要任何解释文字。格式：
{{"items":[{{"question_ids":[12,88],"title":"短标题（疑问句，20 字以内）","question":"一句话问题描述",
"section":"现有小节标题或null","new_section":"新小节标题或null","kind":"A","confidence":"high",
"score":85,"doc_paths":["installation/xxx.md"],"value":"可复用在哪 + 答案来自哪里"}}]}}"""

PASS2_SYSTEM = """你是 {product} 官方文档的撰写者。
任务：基于给定的官方文档原文与群内答复，写一条「社区常见问题」条目，直接进官方文档。
要求事实准确、表述简洁，不追求长篇——把问题说清楚就够了。

■ 你的任务是**回答这一个具体问题**，不是总结整篇文档。
  只提取「能回答当前问题」的必要事实，其余文档内容一律不写。

■ 结论可以来自两个地方（按优先级）：
  1. **官方文档原文**：最可靠，优先用它。
  2. **官方人员在群里的明确答复**（下方标注为「官方人员答复」）：当官方文档确实没有写清楚时，
     这是可用的第二依据，**不再只是线索**。「文档缺失 + 官方已明确答复」正是最值得沉淀的一类。
  普通同事（标注为「普通同事答复」）的回复也可参考，但只在表述确定、能形成明确结论时才采纳。

■ 固定结构（编号由程序生成，你不要写编号；正文只有下面两部分）：
  **问题**：一句话描述用户问题
  **处理方式**：一句话明确结论 + 必要事实/参数/命令
  篇幅通常 1~4 行，能一句话说清就绝不扩写。参照「页面既有条目范例」的措辞与详略。

■ 硬性要求（违反任一条即放弃生成）：
  1. 只回答当前问题，不回答用户没问的问题，不为「看起来完整」而扩写或介绍整个功能。
  2. 只使用给定依据（官方文档原文 / 群内答复）能证明的事实；涉及**版本号、参数、命令、路径、配置项**
     必须逐字来自依据文本，不得改写或自造。
  3. **不根据常识自行推导根因**，不把猜测当作结论，
     不把普通操作步骤包装成故障解决方案。
  4. **严禁「用户问为什么报错、你找不到原因就转而介绍该功能怎么用」**——这是最不可接受的错误。
  5. 严禁出现「可能/大概/不确定/建议试试/请以…为准/视…而定/具体…请参见」等模糊或甩锅表述。
  6. **不得把任何一方的猜测当作结论**。判断一条答复能不能当作依据，看它是否给出了**明确结论**：
     有「现象 → 原因 / 处理方式」的确定表述（如「这个参数改了必须重启才生效」）才算结论；
     只是「可能是…」「你试试…」「先排查下…」「不确定，等确认」这类猜测、建议、只给排查方向的，
     一律不能当事实依据。
  7. **官方人员答复放宽一档**：下方「官方人员答复」只要给出了**可执行的处置**（即使表述简短、
     不完整）就可采纳；而「普通同事答复」必须达到「明确结论」标准才能采纳——达不到就别用它推导，
     宁可放弃生成。
  8. **禁止用你自身知识补充**依据里没有的内容（自身知识只能用来组织语句，不能当事实来源）。
  9. **正文必须能被 MDX 安全编译**：不要写尖括号占位符，例如写「参数」而不是「<参数>」；
     文档里的真实尖括号写法（如 `<域名>`）必须包在反引号里写成 `` `<域名>` ``，或放进代码块。
     不要写 `<br>`、`<https://…>` 这类裸 HTML 标签或裸链接。

■ 依据分级（硬性）：官方文档原文 > 官方人员明确答复 > 普通同事明确答复 > 用户描述 > 你自身知识。

■ 放弃生成（宁缺毋滥）：以下任一情况，把 body 输出为空字符串，表示这条不该自动入库：
  - 官方文档与员工答复**都**没有明确结论，或只给了你无法确认的间接信息；
  - 只能靠猜测、常识推导或「视情况而定」才能回答；
  - 答复只是猜测/建议尝试/只给排查方向，拿不出确定结论；
  - 下方「官方文档原文」标注了「已截断」，而你要用的结论可能落在被截掉的部分；
  - **官方文档原文已经能直接、完整地回答这个问题**（用户照着文档做就能解决）——
    这类属常规使用问题，官方手册已经覆盖，再进 FAQ 只是重复手册，请把 body 输出为空字符串；
  - **与页面已有条目讲的是同一件事**：若下方「页面已有条目」清单里已经有表达了同一问题
    （只是换了说法、指同一现象/同一结论）的条目，不要重复入库，请把 body 输出为空字符串；
  - 你只能给出「该功能怎么操作」这类答非所问的内容，而无法给出问题真正要的原因/限制/结论。

■ 其它：
  - question 用用户口吻描述现象（不照抄群聊原话）。
  - **不要在 body 里写"请参阅/详见/参见…文档"之类的引导句**——引导链接只放 see_also 字段。
  - see_also 可选，全条最多一句收尾引导（如"详细步骤请参阅[升级指南]({placeholder})"），
    用 {placeholder} 作链接地址占位符，不要自写相对路径；没有值得引导的文档就留空字符串。
  - 正文用简体中文；仅当文档原文本身含命令/配置示例时才用代码块，不要为排版堆步骤编号列表。

只输出 JSON，不要任何解释文字。格式：
{{"title":"短标题（疑问句，20 字以内）","question":"一句话问题描述",
"body":"处理方式正文（markdown；依据不足时留空字符串）",
"see_also":"可选的一句收尾引导，含 {placeholder} 链接占位符；不需要时留空字符串",
"doc_path":"最终依据的单个文档相对路径"}}"""

# ---------------------------------------------------------------- 选题与成稿

# 结论不明确就丢弃的 kind：A(常见问题) 要求结论明确；C(故障排查) 的 prompt 已明确
# 「有明确结论才收录」，故 C 只有 confidence=high 才放行——之前只按字母 kind 判断，
# 导致「同事猜测原因」的 C 类也能入库。
KIND_NEEDS_HIGH = frozenset({"A", "C"})


def _to_score(raw) -> int:
    """把模型给的 score 收敛成 0-100 整数；缺失/非法给一个保守中位分，保证仍可排序。"""
    try:
        val = int(float(str(raw).strip()))
    except (TypeError, ValueError):
        return 50
    return max(0, min(100, val))


def _to_confidence(raw) -> str:
    return "high" if str(raw or "").strip().lower() == "high" else "low"


def _as_int_ids(raw) -> list[int]:
    """把模型给的 question_ids 收敛成整型集合，便于与落地条目按「同一批问答对」比对。"""
    out: list[int] = []
    for x in raw or []:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def rank_candidates(candidates: list[dict]) -> list[dict]:
    """把模型初选按「分数降序」重排，并剔除结论不明确的 A/C。

    排序刻意放在脚本里做，而不是信模型数组的先后顺序：prompt 让模型同时干
    「打分」和「排序」两件事时，order 是它顺手给的、不可复现（见 LLM_SEED 说明）。
    交给脚本按数值排，才能审计「为什么这条进了、那条没进」。

    confidence 护栏带「全灭保护」：实测该模型会把 confidence 一律填成 low（40+ 次
    采样里 100% 是 low），若照搬规则会把整批候选判死、退化成「本周无货」。
    因此只有当批里还存在 high 候选时才用 confidence 淘汰，否则视为模型没按字段
    作答、退回按 kind 判断，避免一个不可靠字段接管整个流程。

    返回的候选会补上 score / confidence 两个整型化字段供报告展示。
    """
    scored: list[dict] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        item = dict(item)
        item["score"] = _to_score(item.get("score"))
        item["confidence"] = _to_confidence(item.get("confidence"))
        scored.append(item)
    any_high = any(x["confidence"] == "high" for x in scored)
    if not any_high and scored:
        log("[community_faq] 注意：候选里没有任何 confidence=high，"
            "本轮不做 confidence 淘汰（该字段疑似未被模型正确填充）")
    for item in scored:
        kind = str(item.get("kind") or "").strip().upper()
        if any_high and kind in KIND_NEEDS_HIGH and item["confidence"] != "high":
            # 打 0 分让它沉底，reason 里说明是护栏拦的而非模型判断
            item["score"] = 0
            item["rejected_by"] = "confidence=low"
    # 分数相同的用标题兜底，避免依赖输入顺序（保证排序结果完全确定）
    scored.sort(key=lambda x: (-x["score"], normalize_text(str(x.get("title") or ""))))
    return scored


def screen_questions(pairs: list[dict], page: str, index: list[str],
                     max_items: int, min_items: int = MIN_ITEMS) -> list[dict]:
    """第一轮：模型归组并按「长期复用价值」挑选值得沉淀的问题，同时给出文档依据。

    max_items 是**允许模型自己决定的条数上限**，min_items 是给模型的引导下限。条数交给
    模型判断（够格的多就多选），脚本不再写死「取前 3」，只在超上限时按 score 截断。
    """
    digest = build_question_digest(pairs)
    if not digest:
        return []
    sections, _ = page_sections(page)
    section_titles = ["{0} {1}".format(s["no"], s["title"]) for s in sections]
    existing = existing_entries_digest(page)
    user = (
        "## 现有小节（section 字段只能填这些标题原文）\n" + "\n".join(section_titles) + "\n\n"
        "## 页面已有条目（收录时避免与这些语义重复，含换了说法的同义问法；已附问题描述便于按语义判断）\n"
        + (existing if existing else "（页面暂无条目）") + "\n\n"
        "## 官方文档索引（doc_paths 只能从这里挑）\n" + "\n".join(index) + "\n\n"
        "## 最近提问清单\n" + digest
    )
    messages = [
        {"role": "system", "content": PASS1_SYSTEM.format(
            max_items=max_items, min_items=min(min_items, max_items),
            **product_prompt_vars())},
        {"role": "user", "content": user},
    ]
    # 千帆 v2 上 deepseek-v4.1-flash 对**完全相同的请求**会随机返回 `{"items":[]}`
    # （实测 8 次里有 4 次），而 seed 参数被网关静默忽略、无从复现。空数组是合法 JSON、
    # 解析不报错，直接采信就会把「本期没有值得沉淀的主题」这个错误结论写进报告，
    # 线上因此出现过两次跑出零交集结果。这里只对「空结果」重试，非空结果一律采信，
    # 避免把模型真正的「本期无货」判断重试掉。
    last_err = ""
    for attempt in range(1, PASS1_ATTEMPTS + 1):
        raw = llm_chat(messages, temperature=0.1, max_tokens=4000)
        try:
            payload = json_block(raw)
        except (ValueError, json.JSONDecodeError) as err:
            last_err = str(err)
            log("[community_faq] 第一轮筛选输出无法解析（第 {0}/{1} 次）：{2}".format(
                attempt, PASS1_ATTEMPTS, err))
            continue
        items = payload.get("items")
        candidates = [x for x in items if isinstance(x, dict)] if isinstance(items, list) else []
        if candidates:
            if attempt > 1:
                log("[community_faq] 第一轮筛选第 {0} 次拿到 {1} 个候选".format(
                    attempt, len(candidates)))
            return rank_candidates(candidates)
        log("[community_faq] 第一轮筛选返回空候选（第 {0}/{1} 次），重试".format(
            attempt, PASS1_ATTEMPTS))
    if last_err:
        log("[community_faq] 第一轮筛选连续 {0} 次无法解析，按无候选处理".format(PASS1_ATTEMPTS))
    else:
        log("[community_faq] 第一轮筛选连续 {0} 次返回空候选，按无候选处理".format(PASS1_ATTEMPTS))
    return []


def compose_entry(item: dict, pairs: list[dict], index: list[str]) -> dict | None:
    """第二轮：用官方文档原文 + 群内答复生成条目。

    依据来源二选一即可：有可用的文档原文，或有所在群内的答复（官方人员答复信任度更高）。
    文档路径先经 resolve_doc_path 模糊纠错；纠正不出来只当「没有文档依据」，
    **不作为丢弃条目的理由**。
    宁缺毋滥：两者都给不出明确结论、或模型判定依据不足（body 置空）时，直接返回 None 跳过。
    """
    raw_paths = [str(p) for p in (item.get("doc_paths") or [])]
    cited: list[str] = []
    fixed: list[str] = []      # 被自动纠正的路径（原样 -> 真实）
    dropped: list[str] = []    # 索引里确实找不到的路径（只忽略引用，不影响收录）
    for raw in raw_paths:
        got = resolve_doc_path(raw, index)
        if not got:
            dropped.append(raw)
            continue
        if got not in cited:
            cited.append(got)
        if got != raw.strip():
            fixed.append("{0} -> {1}".format(raw, got))
    if fixed:
        log("[community_faq] 自动纠正文档路径 {0} <- {1}".format("；".join(fixed), item.get("title")))
    if dropped:
        log("[community_faq] 索引里找不到这些引用，已忽略（条目仍可基于群内答复成稿）{0} <- {1}"
            .format(dropped, item.get("title")))

    ids = valid_question_ids(item, digest_limit(len(pairs)))
    source_questions = [scrub_question(pairs[i]["question"]) for i in ids[:3]] or [str(item.get("question") or "")]
    source_answers = [pairs[i]["answer"] for i in ids[:3]]
    official_answers = [pairs[i]["answer"] for i in ids[:3] if pairs[i].get("official")]
    answerers = "、".join(dict.fromkeys(pairs[i].get("answerer") or "" for i in ids[:3] if pairs[i].get("answerer")))

    blocks: list[str] = []
    total = 0
    truncated: list[str] = []   # 单篇超长被截断的文档
    omitted: list[str] = []     # 因总字符上限没喂进去的文档
    for rel in cited[:3]:
        text = (DOCS_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        if len(text) > DOC_CHARS_PER_FILE:
            text = text[:DOC_CHARS_PER_FILE] + "\n...(已截断)"
            truncated.append(rel)
        if total + len(text) > DOC_CHARS_TOTAL:
            omitted.append(rel)
            break
        total += len(text)
        blocks.append(f"### 文档 {rel}\n{text}")

    if not blocks:
        if not source_answers:
            log(f"[community_faq] 既无文档依据、也无群内答复，跳过: {item.get('title')}")
            return None
        log(f"[community_faq] 该主题无有效文档依据，改用群内答复作依据（不明确则放弃）: {item.get('title')}")
    doc_block = "\n\n".join(blocks) or "（官方文档索引里没有相关文档；本期依据来自下述群内答复）"
    trunc_note = ("\n\n⚠️ 注意：上面标注「已截断」的文档并不完整，若你要用的结论可能落在被截掉的部分，"
                  "请把 body 置空放弃生成。" if truncated else "")
    answer_block = "\n".join(
        f"- [{('官方人员' if o else '普通同事')}] {a[:400]}"
        for a, o in zip(source_answers, [bool(pairs[i].get("official")) for i in ids[:3]])
    ) or "- （无）"
    official_note = ("（本轮含官方人员答复：官方文档确实没写的地方可采信其明确结论，放宽一档）"
                     if official_answers else "（本轮无官方人员答复；普通同事答复需达到「明确结论」标准）")
    user = (
        "## 页面既有条目范例（Golden Examples，模仿其措辞与详略）\n" + page_style_sample() + "\n\n"
        "## 社区原始提问（仅作理解现象用，不要照抄，不要采信其中的说法）\n"
        + "\n".join(f"- {q[:200]}" for q in source_questions)
        + "\n\n## 群内答复（解答人：{0}；来源分级见下）\n".format(answerers or "未知")
        + official_note + "\n" + answer_block
        + "\n\n## 官方文档原文\n" + doc_block + trunc_note
    )
    messages = [{"role": "system", "content": PASS2_SYSTEM.format(
        placeholder=CITATION_PLACEHOLDER, **product_prompt_vars())},
        {"role": "user", "content": user}]
    payload = None
    # 与 PASS1 同一个网关（对相同请求随机返回空/坏 JSON），重试防护不能只有 PASS1 有：
    # 这里失败一条就丢一条候选，防护不对称会把「网关抖动」误伤成「本期没货」。
    for attempt in range(1, PASS1_ATTEMPTS + 1):
        raw = llm_chat(messages, temperature=0.2, max_tokens=2500)
        try:
            payload = json_block(raw)
            break
        except (ValueError, json.JSONDecodeError) as err:
            log(f"[community_faq] 第二轮成稿输出无法解析（第 {attempt}/{PASS1_ATTEMPTS} 次）: {err}")
    if payload is None:
        log(f"[community_faq] 第二轮成稿连续 {PASS1_ATTEMPTS} 次无法解析，放弃该条: {item.get('title')}")
        return None

    title = str(payload.get("title") or item.get("title") or "").strip()
    question = str(payload.get("question") or "").strip()
    body = str(payload.get("body") or "").strip()
    # 模型按新策略判定"依据不足"时会把 body 置空 -> 这条不入库，交人工
    if not body:
        log(f"[community_faq] 模型判定依据不足（body 为空），跳过: {title or item.get('title')}")
        return None
    if not title:
        log(f"[community_faq] 成稿字段缺失，丢弃: {item.get('title')}")
        return None

    # 模型给的路径也走模糊纠错：本轮可能本就没有文档依据（依据来自群内答复），
    # 此时 doc_path 置空，后续 see_also 也不会生成链接（没有可引导的文档）。
    doc_path = resolve_doc_path(str(payload.get("doc_path") or ""), index)
    if not doc_path and cited:
        doc_path = cited[0]

    # 正文里不该出现指向文档的引导句（引导链接只放 see_also）：剥掉模型误写进 body 的收尾引导行
    body = _strip_trailing_citation(body)
    # 剥完可能只剩空壳（正文本就是纯引用、无实质回答）：按空正文丢弃
    if not body:
        log(f"[community_faq] 剥除引用后正文为空，跳过: {title or item.get('title')}")
        return None

    see_also = str(payload.get("see_also") or "").strip()
    link = rel_link(doc_path) if doc_path else ""
    if not link:
        # 没有可引导的文档（本轮无文档依据，或路径不合法）：去掉 see_also，
        # 避免生成指向空路径的裸链接或 `[文字]()`
        if see_also:
            log(f"[community_faq] 无可用文档链接，已去掉 see_also: {title}")
        see_also = ""
    else:
        if CITATION_PLACEHOLDER in see_also:
            # 模型已给出含占位符的链接，直接替换地址
            see_also = see_also.replace(CITATION_PLACEHOLDER, link)
        elif see_also:
            # 模型只给了引导语没带链接：把链接补在句末，避免出现裸占位符或重复链接
            see_also = f"{see_also.rstrip('。 ')}（[{link}]({link})）"

    final_question = question or title
    vague = sorted({w for w in VAGUE_PHRASES if w in body or w in final_question})
    if vague:
        log("[community_faq] 质量警告：{0} 含模糊表述 {1}".format(title, "、".join(vague)))

    warnings: list[str] = []
    if vague:
        warnings.append("正文含模糊表述：{0}（提示词已禁止）".format("、".join(vague)))
    if not blocks:
        src = "官方人员" if official_answers else "普通同事"
        warnings.append("本条**无官方文档依据**，依据来自群内答复（{0}{1}），请人工核对"
                        .format(src, "：" + answerers if answerers else ""))
        log("[community_faq] 质量提示：{0} 无文档依据，依据来自{1}答复".format(title, src))
    if truncated or omitted:
        detail = []
        if truncated:
            detail.append("被截断 {0}".format("、".join(truncated)))
        if omitted:
            detail.append("未喂入 {0}".format("、".join(omitted)))
        warnings.append("依据文档超出长度上限（{0}），结论有落在未喂入部分之后的风险，请人工核对"
                        .format("；".join(detail)))
        log("[community_faq] 质量警告：{0} 依据文档超长（{1}）".format(title, "；".join(detail)))

    return {
        "section": item.get("section"),
        "new_section": item.get("new_section"),
        "title": title,
        "question": final_question,
        "body": body,
        "see_also": see_also,
        "doc_path": doc_path,
        "question_ids": ids,
        "count": len(ids),
        "sources": ["{0} {1}".format(pairs[i]["date"], pairs[i]["group"]) for i in ids[:3]],
        "answerers": answerers,
        "official": bool(official_answers),
        "evidence": "官方文档" if blocks else ("官方人员答复" if official_answers else "普通同事答复"),
        "reason": str(item.get("value") or item.get("reason") or "").strip(),
        "score": item.get("score", 0),
        "confidence": item.get("confidence", "low"),
        "truncated": truncated,
        "omitted": omitted,
        "warnings": warnings,
    }


def page_style_sample(max_examples: int = 8) -> str:
    """取页面里已有的若干条条目作为措辞范例（Golden Examples），覆盖不同类型，避免风格漂移。

    页面条目少时全给；多时按小节分散取样，尽量覆盖不同主题。附带固定结构说明，
    明确「问题 + 处理方式」两段式、编号由程序生成、正文 1~4 行。
    """
    try:
        text = read_page()
    except BaseException:  # 页面读取失败（SystemExit）等一律降级：缺范例不致失败
        return "（页面暂无条目）"
    blocks = re.findall(r"^###\s+\d+\.\d+.*?(?=^###\s|^##\s|\Z)", text, re.S | re.M)
    if not blocks:
        return text.strip()[:600]
    # 去 git 冲突标记行（否则范例会把冲突标记当正文喂给模型）：冲突期宁可跳过本批条目。
    # 同时按「处理方式」那行去掉模型可能潜写的「- 阅读方式」前缀，避免范例被污染。
    blocks = [b for b in blocks if not re.search(r"^(<{7}|={7}|>{7})", b, re.M)]
    cleaned: list[str] = []
    for b in blocks:
        keep: list[str] = []
        for ln in b.splitlines():
            if re.match(r"^\*\*处理方式\*\*\s*[：:]\s*-", ln):
                continue
            keep.append(ln)
        cleaned.append("\n".join(keep))
    blocks = cleaned
    # 按所属小节分组后轮转取样，保证覆盖不同类型而非集中在同一小节
    grouped: dict[str, list[str]] = {}
    for b in blocks:
        key = b.split("\n", 1)[0].split(".", 1)[0].strip()  # 用「### N」的小节号粗分组
        grouped.setdefault(key, []).append(b.strip()[:700])
    picked: list[str] = []
    buckets = list(grouped.values())
    i = 0
    while len(picked) < max_examples and any(buckets):
        b = buckets[i % len(buckets)]
        if b:
            picked.append(b.pop(0))
        i += 1
    header = (
        "【页面固定结构】每条只有两段，编号由程序生成、你不要写编号：\n"
        "### N.N 标题（疑问句）\n"
        "**问题**：一句话描述用户问题\n"
        "**处理方式**：\n"
        "一句话明确结论 + 必要事实/参数/命令（通常 1~4 行，能一句话说清就别扩写）\n\n"
        "【Golden Examples：模仿以下真实条目的措辞与详略，不要自创风格】\n"
    )
    return header + "\n\n---\n\n".join(picked)


# ---------------------------------------------------------------- 写回页面

# 模型偶尔把"请参阅 XXX 文档"这类收尾引导句写进 body（本该只放 see_also），
# 会与 _render_entry 追加的 see_also 重复，甚至出现连续多句/裸链接。逐行从末尾剥掉。
_CITATION_LINE_RE = re.compile(
    r"^(?:详细|完整|更多|具体)?[^。\n]{0,40}?"
    r"(?:请参阅|详见|参见|见|参考)\s*\[[^\]]*\]\([^)]*\)\s*[。.]?$"
)
_BARE_LINK_LINE_RE = re.compile(r"^\s*\[[^\]]*\]\([^)]*\)\s*[。.]?\s*$")
_TRAILING_BARE_LINK_RE = re.compile(r"\s*\[[^\]]*\]\([^)]*\)\s*[。.]?\s*$")
_TRAILING_LEADIN_RE = re.compile(
    r"\s*(?:详细|完整|更多|具体)?[^。\n]{0,40}?"
    r"(?:请参阅|详见|参见|参考|见)\s*[，,：:。]?\s*$"
)
# 剥掉链接后，行尾可能剩「详见官方文档」「具体配置步骤请参阅」这类以引用动词开头/收尾的
# 悬空短语（动词在前、名词在后）。匹配「(修饰语)?(详见|参见|...) + 少量名词」直到行末。
_DANGLING_LEADIN_RE = re.compile(
    r"\s*(?:详细|完整|更多|具体)?[^（）()\n]{0,20}?"
    r"(?:请参阅|详见|参见|参考|见)\s*(?:官方)?(?:文档|说明|教程|手册|链接|页面)?\s*$"
)
# 行尾的「（详见/参见…[链接]…。）」或「详见…[链接]。」引用尾——必须以引用动词引导，
# 避免误伤正文里正常的括号链接。
_INLINE_CITATION_TAIL_RE = re.compile(
    r"\s*[（(]?\s*(?:详细|完整|更多|具体)?[^（）()\n]{0,24}?"
    r"(?:请参阅|详见|参见|参考|见)\s*[，,：:]?\s*"
    r"\[[^\]]*\]\([^)]*\)\s*[）)]?\s*[。.]?\s*$"
)


def _clean_line_citations(line: str) -> str:
    """对单行从右反复剥：末尾裸链接 → 「详见…[链接]」引用尾 → 悬空引导词，直到稳定。"""
    prev = None
    cur = line.rstrip()
    while cur != prev:
        prev = cur
        cur = _TRAILING_BARE_LINK_RE.sub("", cur).rstrip()
        cur = _INLINE_CITATION_TAIL_RE.sub("", cur).rstrip()
        cur = _DANGLING_LEADIN_RE.sub("", cur).rstrip()
        cur = _TRAILING_LEADIN_RE.sub("", cur).rstrip()
    return cur


def _strip_trailing_citation(body: str) -> str:
    """去掉正文里指向文档的引导句/裸链接，避免与 see_also 重复。"""
    lines = [_clean_line_citations(ln) for ln in body.rstrip().splitlines()]
    # 从末尾删掉被剥空的行或整行都是引用/裸链接的行
    while lines:
        last = lines[-1].strip()
        if last == "" or _CITATION_LINE_RE.match(last) or _BARE_LINK_LINE_RE.match(last):
            lines.pop()
            continue
        break
    stripped = "\n".join(lines).rstrip()
    # 剥完后若只剩「答：」这类空壳（正文本就是纯引用、无实质内容），返回空串，
    # 交给上层按空正文丢弃。
    if re.sub(r"^[\s>*\-]*答[：:]\s*", "", stripped).strip() == "":
        return ""
    # 只有确实剥掉了内容且还剩正文时才采用，防止把整段误删
    return stripped if stripped else body.rstrip()


# prompt 里「页面固定结构」那段范例把 `**处理方式**：` 展示成独占一行，
# 模型会误以为 body 字段也要自带该标签而重复输出一次。_render_entry 自己会补标签，
# 这里先剥掉开头那个，否则页面上会出现连续两行 `**处理方式**：`（2026-10-15 PR #200 实测）。
# 只剥**起始处**：正文中间若真写了这个标签，那是模型有意的分段，不该动。
_BODY_LABEL_RE = re.compile(r"^\s*\*\*\s*处理方式\s*\*\*\s*[：:]?\s*")


def _strip_body_label(body: str) -> str:
    """剥掉 body 开头模型误加的 `**处理方式**：` 标签。"""
    if not body:
        return body
    # 标签后原本跟着换行时会留下空行，一并去掉（渲染时空行会原样带出去）
    return _BODY_LABEL_RE.sub("", body).lstrip("\n")


def _render_entry(no: int, minor: int, entry: dict) -> list[str]:
    lines = [f"### {no}.{minor} {entry['title']}", "", f"**问题**：{entry['question']}", "",
             "**处理方式**：", ""]
    lines += _strip_body_label(entry["body"]).splitlines()
    lines.append("")
    if entry.get("see_also"):
        lines += [entry["see_also"], ""]
    return lines


def _match_section(sections: list[dict], raw_title: str) -> dict | None:
    key = normalize_text(raw_title or "")
    if not key:
        return None
    for s in sections:
        if normalize_text(s["title"]) == key:
            return s
    for s in sections:
        sk = normalize_text(s["title"])
        if sk and (sk in key or key in sk):
            return s
    return None


def insert_entries(page_text: str, entries: list[dict]) -> tuple[str, list[dict]]:
    """把条目追加到对应小节末尾。返回 (新页面文本, 实际落位说明)。"""
    if not entries:
        return page_text, []

    sections, max_no = page_sections(page_text)
    lines = page_text.splitlines()
    placed: list[dict] = []
    grouped: list[tuple[dict, list[dict]]] = []
    for entry in entries:
        sec = _match_section(sections, entry.get("section") or "")
        if sec is None:
            continue
        for existing, bucket in grouped:
            if existing is sec:
                bucket.append(entry)
                break
        else:
            grouped.append((sec, [entry]))

    # 按行号从后往前插入，避免前面的插入使后面的行号失效
    for sec, bucket in sorted(grouped, key=lambda x: -x[0]["line_end"]):
        pos = sec["line_end"]
        while pos > sec["line_start"] + 1 and lines[pos - 1].strip() == "":
            pos -= 1
        minor = max(sec["minors"], default=0)
        block: list[str] = []
        for entry in bucket:
            minor += 1
            block += _render_entry(sec["no"], minor, entry)
            placed.append({"entry": entry, "section": "{0} {1}".format(sec["no"], sec["title"]), "no": "{0}.{1}".format(sec["no"], minor)})
        lines[pos:pos] = [""] + block

    # 模型判定不属于任何现有小节时，在末尾新建小节
    new_bucket: list[dict] = []
    for entry in entries:
        if entry.get("section") and _match_section(sections, entry["section"]) is not None:
            continue
        if entry.get("new_section"):
            new_bucket.append(entry)
    new_groups: list[tuple[str, list[dict]]] = []
    for entry in new_bucket:
        title = str(entry["new_section"]).strip()
        for name, bucket in new_groups:
            if normalize_text(name) == normalize_text(title):
                bucket.append(entry)
                break
        else:
            new_groups.append((title, [entry]))
    while lines and lines[-1].strip() == "":
        lines.pop()
    for title, bucket in new_groups:
        max_no += 1
        lines += ["", f"## {max_no} {title}", ""]
        for idx, entry in enumerate(bucket, start=1):
            lines += _render_entry(max_no, idx, entry)
            placed.append({"entry": entry, "section": f"{max_no} {title}", "no": f"{max_no}.{idx}"})

    # 收敛多余空行（模型正文可能带出连续空行），保持与页面既有排版一致
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).rstrip("\n") + "\n"
    if len(placed) < len(entries):
        log("[community_faq] 警告：{0} 条既未匹配现有小节、也未给出新小节标题，已跳过".format(len(entries) - len(placed)))
    return text, placed


# ---------------------------------------------------------------- 跨期续接

def entry_from_block(block: str) -> dict | None:
    """把页面上一条 `### N.N` 条目块还原成 entry dict（跨期续接用）。

    只认页面固定结构（标题 / **问题** / **处理方式**）；缺任一必要字段就返回 None。
    末尾的引导句（see_also）与正文分开，避免重复渲染。
    """
    lines = (block or "").rstrip().splitlines()
    if not lines:
        return None
    m = re.match(r"^###\s+\d+\.\d+\s+(.+?)\s*$", lines[0])
    if not m:
        return None
    title = m.group(1).strip()
    question, body_start = "", 0
    for idx in range(1, len(lines)):
        mm = re.match(r"^\*\*问题\*\*[：:]\s*(.+?)\s*$", lines[idx])
        if mm:
            question = mm.group(1).strip()
            body_start = idx + 1
            break
    i = body_start
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    # 页面里 `**处理方式**` 存在两种写法：独占一行，或行内直接跟正文。
    # 两种都要吃掉这个标记——否则 insert_entries 再渲染一次会变成两行 `**处理方式**：`。
    if i < len(lines):
        mm = re.match(r"^\*\*处理方式\*\*\s*[：:]?\s*(.*)$", lines[i])
        if mm:
            rest = mm.group(1).strip()
            if rest:
                lines[i] = rest
            else:
                del lines[i]
    body_lines: list[str] = []
    see_also = ""
    for idx in range(i, len(lines)):
        if re.match(r"^\s*(?:详细|完整|更多|具体)?[^。\n]{0,40}?"
                    r"(?:请参阅|详见|参见|参考|见)\s*\[[^\]]*\]\([^)]*\)", lines[idx]):
            see_also = lines[idx].strip()
            break
        body_lines.append(lines[idx])
    body = "\n".join(body_lines).rstrip()
    if not title or not question or not body:
        return None
    return {
        "section": "", "new_section": None, "title": title, "question": question,
        "body": body, "see_also": see_also, "doc_path": "", "question_ids": [],
        "count": 0, "sources": [], "answerers": "", "official": False,
        "evidence": "上期未合并条目", "reason": "上期已入选但尚未合并，本期续接",
        "truncated": [], "omitted": [], "warnings": [], "reused": True,
    }


def entries_from_page(text: str) -> list[dict]:
    """把一份页面的所有条目块解析成 entry dict，并带上所属小节标题。"""
    sections, _ = page_sections(text)
    lines = text.splitlines()
    out: list[dict] = []
    for sec in sections:
        seg = "\n".join(lines[sec["line_start"] + 1:sec["line_end"]])
        for m in re.finditer(r"^###\s+\d+\.\d+\s+.*?(?=^###\s+\d+\.\d+\s|\Z)", seg, re.S | re.M):
            entry = entry_from_block(m.group(0))
            if entry:
                entry["section"] = "{0} {1}".format(sec["no"], sec["title"])
                out.append(entry)
    return out


REUSE_DEDUP_SYSTEM = """你是 {product} 官方文档的编辑，正在做「入库前查重」。

下面给你两组条目：
- 【待入库条目】：上一期已入选、但因 PR 尚未合并而需要顺延到本期的条目；
- 【页面已有条目】：当前页面里已经存在的条目（含标题与问题描述）。

请逐条判断每个【待入库条目】与【页面已有条目】讲的是不是**同一件事**：
同一个现象的同一套结论就算同一件事，即使措辞、视角、标题完全不同（例如「升级到 v5 后发现
没有 lion 组件」与「升级后提示 Lion 组件离线如何处理」说的是同一件事：lion 已并入 koko、
残留的 lion 应删除）。反之，问的是不同现象、或结论不同（需要不同处理动作）就算不同的事。

只输出 JSON，不要任何解释文字。格式：
{"items":[{"title":"原样复制待入库条目的标题","duplicate":true或false,
"duplicate_of":"若重复，填页面已有条目的标题；否则留空字符串"}]}
要求：待入库条目**必须逐条给出判断**，条数与输入一致，标题原样复制。"""


def is_llm_configured() -> bool:
    """能否调用大模型（缺 key 时静默降级为机械判重，不抛异常）。"""
    return bool(cfg("LLM_API_KEY"))


def _parse_dedup_reply(raw: str, titles: list[str]) -> dict[str, str]:
    """从模型输出里取出 {待入库标题 -> 重复于哪条(空串=不重复)}。"""
    payload = json_block(raw)
    items = payload.get("items")
    if not isinstance(items, list):
        return {}
    want = {normalize_text(t)[:40]: t for t in titles}
    out: dict[str, str] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        key = normalize_text(str(it.get("title") or ""))[:40]
        if key not in want:
            continue
        dup = str(it.get("duplicate") or "").strip().lower() in ("true", "1", "yes", "是")
        out[want[key]] = str(it.get("duplicate_of") or "").strip() if dup else ""
    return out


def _llm_dedup_chunks(page: str, titles: list[str], chunk: int = 8) -> dict[str, str]:
    """分批把待入库条目的标题交给模型判重，返回 {标题 -> 重复于哪条(空串=不重复)}。

    为什么要走模型：机械 bigram 判重在「换了说法的同义问法」上完全失效——实测
    「升级后提示 Lion 组件离线如何处理」（待入库）与「升级到 v5 后发现没有 lion 组件？」
    （页面已有）只共享 3 个 bigram，相似度约 0.34，远低于阈值，但它们结论完全一致，
    入库就是重复条目（2026-10-12 用户投诉的就是这一条）。
    """ 
    existing = existing_entries_digest(page)
    if not existing:
        return {}
    verdict: dict[str, str] = {}
    for start in range(0, len(titles), chunk):
        batch = titles[start:start + chunk]
        user = ("## 待入库条目（上一期已入选，尚未合并）\n"
                + "\n".join("- {0}".format(t) for t in batch)
                + "\n\n## 页面已有条目\n" + existing)
        messages = [{"role": "system", "content": REUSE_DEDUP_SYSTEM.format(**product_prompt_vars())},
                    {"role": "user", "content": user}]
        try:
            raw = llm_chat(messages, temperature=0.0, max_tokens=2000)
            verdict.update(_parse_dedup_reply(raw, batch))
        except SystemExit:
            raise
        except Exception as err:      # 网关随机抖动：重试一次再降级
            log("[community_faq] 续接条目语义判重第 1 次失败，重试: {0}".format(err))
            try:
                raw = llm_chat(messages, temperature=0.0, max_tokens=2000)
                verdict.update(_parse_dedup_reply(raw, batch))
            except SystemExit:
                raise
            except Exception as err2:
                # 仍失败则保守放行，交由人工在 PR 里核对
                log("[community_faq] 续接条目语义判重连续失败（放行待人工核对）: {0}".format(err2))
    return verdict


def reuse_entries_from_page(path: Path, page: str) -> tuple[list[dict], list[dict]]:
    """上期固定分支页面里、当前页面还没有的条目。

    ⚠️ 这是 2026-10-12 事故的修复点。旧实现用 `git checkout FETCH_HEAD -- <页面>` 把上期分支的
    **整份文件**盖到最新 main 上，于是 main 上的人工修改（前端标题、正文订正）被静默回退；
    三方合并（git merge-file）也救不了 —— 旧分支是「世代相传的陈旧快照」，其 parent→branch
    的差异里混着回退内容，合并会把回退一并重放。
    现在只做「条目级续接」：只取上期多出来的 `### N.N` 条目块，按当前页面判重后追加，
    页面其余部分（含 front matter）完全以 main 为准。

    判重分两层：① 机械——标题 / **问题** 行的精确与 bigram 近似比对（快、零依赖）；
    ② 语义——配上「已并入页面、但不回退任何内容」的语义判重。
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as err:
        log("[community_faq] 读取上期候选页失败（忽略）: {0}".format(err))
        return [], []

    def probe_of(entry: dict) -> str:
        return normalize_text(str(entry.get("title") or ""))[:40]

    # 机械判重：标题与问题描述一起比，任一命中即视为已并入页面
    keys = existing_entry_keys(page)
    kept: list[dict] = []
    dropped: list[dict] = []
    for entry in entries_from_page(text):
        title = str(entry.get("title") or "")
        question = str(entry.get("question") or "")
        dup = ""
        for probe_src in (title, question):
            probe = normalize_text(probe_src)[:40]
            if probe and probe in keys:
                dup = "标题/问题与页面已有条目相同"
                break
            hit = near_duplicate(probe_src, keys)
            if hit:
                dup = "与页面已有条目近似（最像：{0}）".format(hit)
                break
        if dup:
            dropped.append({"title": title, "reason": "上期条目已并入页面，不再重复追加（{0}）".format(dup)})
            continue
        # 与 existing_entry_keys 一致：标题 + 问题描述双 key，防「问法不同、同一件事」漏网
        keys.add(probe_of(entry))
        q_probe = normalize_text(question)[:40]
        if q_probe:
            keys.add(q_probe)
        kept.append(entry)

    # 语义判重：机械比对抓不住「换说法的同一件事」
    if kept and is_llm_configured():
        try:
            verdict = _llm_dedup_chunks(page, [e["title"] for e in kept])
        except SystemExit:
            verdict = {}
        survivors: list[dict] = []
        for entry in kept:
            hit = verdict.get(entry["title"])
            if hit:
                dropped.append({"title": entry["title"],
                                "reason": "语义重复于页面已有条目「{0}」，不再重复追加".format(hit)})
                continue
            survivors.append(entry)
        kept = survivors
    return kept, dropped


def load_pending_reuse(path: str, keys: set[str]) -> tuple[list[dict], list[dict]]:
    """读取上期「待续接清单」（被名额截断的条目，JSON 数组），返回 (可续接, 已丢弃)。

    ⚠️ 固定分支每轮从 main 重建，被截断的条目**不会**留在分支页面上 —— 旧实现
    「留在固定分支上下轮再续接」的说法是错的，截断即永久丢失（2026-10-15 复核确认）。
    这份清单由脚本自己写、随固定分支提交，是截断条目唯一的存续通道。
    """
    if not path:
        return [], []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        log("[community_faq] 读取待续接清单失败（按无待续接处理）: {0}".format(err))
        return [], []
    if not isinstance(data, list):
        log("[community_faq] 待续接清单格式异常（应为 JSON 数组），忽略")
        return [], []
    kept: list[dict] = []
    dropped: list[dict] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or "")
        question = str(entry.get("question") or "")
        body = str(entry.get("body") or "").strip()
        if not title or not question or not body:
            dropped.append({"title": title or "（无标题）",
                            "reason": "待续接条目字段缺失（title/question/body），已丢弃"})
            continue
        dup = False
        for probe_src in (title, question):
            probe = normalize_text(probe_src)[:40]
            if probe and probe in keys:
                dup = True
                break
        if dup:
            dropped.append({"title": title, "reason": "待续接条目已并入当前页面，不再续接"})
            continue
        entry.setdefault("evidence", "上期待续接（曾被名额截断）")
        entry.setdefault("reason", "上期因名额截断顺延，本期优先续接")
        entry["reused"] = True
        keys.add(normalize_text(title)[:40])
        keys.add(normalize_text(question)[:40])
        kept.append(entry)
    if kept:
        log("[community_faq] 从待续接清单载入 {0} 条（已等待至少一轮，本轮优先续接）".format(len(kept)))
    return kept, dropped


def write_pending_out(path: str, entries: list[dict]) -> None:
    """把本轮被名额截断的条目写成待续接清单（随固定分支提交，下轮 load_pending_reuse 优先续接）。"""
    # 保留成稿所需的全部字段 + 报告要用的元数据（count/sources/...），下轮续接进
    # insert_entries/write_report 时字段齐全；missing 字段报告侧都有 .get() 兜底
    keep = ("section", "new_section", "title", "question", "body",
            "see_also", "doc_path", "evidence", "reason",
            "count", "sources", "answerers", "official",
            "score", "confidence", "warnings")
    slim = [{k: e.get(k) for k in keep if e.get(k)} for e in entries]
    Path(path).write_text(json.dumps(slim, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8")
    log("[community_faq] 待续接清单已写出：{0}（{1} 条）".format(path, len(slim)))


# ---------------------------------------------------------------- 报告

def fetch_summary(stats: dict | None) -> str:
    """取数完整性的一句话摘要（写进报告，供人工确认本期数据是否完整）。"""
    if not stats:
        return "未取数（使用本地问答对）"
    if not stats.get("failures"):
        return "全部成功（请求 {0} 次，消息 {1} 条）".format(stats.get("attempts", 0), stats.get("rows", 0))
    return "存在失败请求（请求 {0} 次、失败 {1} 次、消息 {2} 条）".format(
        stats.get("attempts", 0), stats.get("failures", 0), stats.get("rows", 0))


def funnel_stats(stats: dict | None, pairs: list[dict], candidates: list[dict],
                 placed: int, skipped: int) -> dict:
    """漏斗数据：消息 → 问答对 → 模型初选 → 入库，附初选结果的分类计数。

    这条链每一环都会掉数据，掉在哪一环决定了要改哪一步。没有它，报告只看得出
    「入库 0 条」，看不出是群里本来就没问题、被初选淘汰、还是成稿环节全被否掉。
    """
    kinds = {"A": 0, "B": 0, "C": 0, "D": 0, "?": 0}
    for item in candidates:
        if not isinstance(item, dict):
            continue
        k = str(item.get("kind") or "").strip().upper()
        kinds[k if k in ("A", "B", "C", "D") else "?"] += 1
    return {
        "messages": (stats or {}).get("rows"),
        "pairs": len(pairs),
        "candidates": len(candidates),
        "placed": placed,
        "skipped": skipped,
        "kinds": kinds,
    }


def write_report(path: str, *, pairs: list[dict], placed: list[dict],
                 skipped: list[dict], by_day: list[dict], days: int, applied: bool,
                 fetch_note: str = "", note: str = "", funnel: dict | None = None,
                 candidates: list[dict] | None = None,
                 cap: int = MAX_ITEMS_CEILING, reused_n: int = 0) -> None:
    per_day = ", ".join("{0}={1}".format(d["date"], d["pairs"]) for d in by_day)
    warn_total = sum(len(r["entry"].get("warnings") or []) for r in placed)
    lines = [
        "# 社区常见问题 · 本期自动生成报告",
        "",
    ]
    if note:
        lines += ["> {0}".format(note), ""]
    lines += [
        "- 数据窗口：最近 {0} 天（含今天）".format(days),
        "- 问答对：{0} 条（按天：{1}）".format(len(pairs), per_day),
        "- 取数完整性：{0}".format(fetch_note or "未记录"),
    ]
    if funnel:
        kinds = funnel.get("kinds") or {}
        msg_n = funnel.get("messages")
        lines.append(
            "- 漏斗：消息 {0} 条 → 问答对 {1} 条 → 模型初选 {2} 个"
            "（A {3} / B {4} / C {5} / D {6} / 缺分类 {7}）→ 入库 {8} 条，未采纳 {9} 条".format(
                "-" if msg_n is None else msg_n, funnel.get("pairs", 0), funnel.get("candidates", 0),
                kinds.get("A", 0), kinds.get("B", 0), kinds.get("C", 0), kinds.get("D", 0),
                kinds.get("?", 0), funnel.get("placed", 0), funnel.get("skipped", 0)))
    else:
        lines.append("- 候选主题：{0} 个（入库 {1}，未采纳 {2}）".format(
            len(placed) + len(skipped), len(placed), len(skipped)))
    lines += [
        "- 本次新增：{0} 条（{1}）".format(len(placed), "已写回页面" if applied else "仅预览，未写回"),
        "- 名额占用：{0}/{1} 条（上期续接 {2} + 本期新增 {3}；`max_items` 上限 {4}）".format(
            len(placed), cap, reused_n, max(0, len(placed) - reused_n), cap),
        "- 质量检查：{0}".format("无警告" if not warn_total else "{0} 条警告（见下方 ⚠️）".format(warn_total)),
        "",
    ]
    if placed:
        lines += ["## 新增条目", ""]
        for row in placed:
            e = row["entry"]
            doc_shown = "`{0}`".format(e["doc_path"]) if e.get("doc_path") else "（无，依据来自群内答复）"
            evidence = e.get("evidence") or "官方文档"
            answerer_line = "- 解答人：{0}{1}".format(
                e.get("answerers") or "未知",
                "（官方人员）" if e.get("official") else "（普通同事）",
            ) if evidence != "官方文档" else "- 解答人：-"
            block = [
                f"### {row['no']} {e['title']}",
                f"- 小节：{row['section']}",
                f"- 依据类型：{evidence}",
                f"- 依据文档：{doc_shown}",
                answerer_line,
                f"- 社区出现次数：{e.get('count', '-')}",
                f"- 来源：{'；'.join(e.get('sources') or []) or '-'}",
                f"- 入选理由：{e['reason'] or '-'}",
                f"- 评分：{e.get('score', '-')}（confidence={e.get('confidence', '-')}）",
            ]
            block += [f"- ⚠️ {w}" for w in (e.get("warnings") or [])]
            block.append("")
            lines += block
    if candidates:
        lines += ["## 本期候选排序（脚本按 score 降序取用）", ""]
        lines += ["| # | score | kind | confidence | 标题 | 结果 |",
                  "|---|---|---|---|---|---|"]
        placed_titles = {normalize_text(str(r["entry"].get("title") or "")) for r in placed}
        # PASS2 会重写标题（「文档分块后标题内容检索不出来怎么办？」→「标题内容检索不出来怎么办？」），
        # 只按标题比对会把已收录的候选误判成「未轮到」。question_ids 指向同一批社区问答对、
        # 不会被改写，故优先按它匹配，标题只作兜底。
        placed_ids = {frozenset(r["entry"].get("question_ids") or []) for r in placed}
        placed_ids.discard(frozenset())
        skipped_reason = {normalize_text(str(r.get("title") or "")): r.get("reason")
                          for r in skipped}
        for i, item in enumerate(candidates, 1):
            key = normalize_text(str(item.get("title") or ""))
            ids = frozenset(_as_int_ids(item.get("question_ids")))
            if (ids and ids in placed_ids) or key in placed_titles:
                outcome = "✅ 收录"
            elif item.get("rejected_by"):
                outcome = "🚫 结论不明确"
            else:
                outcome = skipped_reason.get(key) or "未轮到（已满 {0} 条）".format(len(placed))
            lines.append("| {0} | {1} | {2} | {3} | {4} | {5} |".format(
                i, item.get("score", "-"), str(item.get("kind") or "?").upper(),
                item.get("confidence", "-"), item.get("title") or "-", outcome))
        lines.append("")
    if skipped:
        lines += ["## 未采纳的候选", ""]
        for row in skipped:
            lines += [f"- {row.get('title') or '(无标题)'} —— {row.get('reason')}", ""]
    Path(path).write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def set_action_output(changed: bool, count: int, report: str) -> None:
    out = cfg("GITHUB_OUTPUT")
    if not out:
        return
    try:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"changed={'true' if changed else 'false'}\n")
            fh.write(f"count={count}\n")
            fh.write(f"report={report}\n")
    except OSError as err:
        log(f"[community_faq] 写 GITHUB_OUTPUT 失败: {err}")


# ---------------------------------------------------------------- MDX 安全护栏
# 背景（2026-10-10 线上事故）：模型生成的正文里出现裸尖括号占位符「在<参数>中配置」,
# Docusaurus 的 MDX 会把它当 JSX 标签解析，报
#   Expected a closing tag for `<参数>` before the end of `paragraph`
# 导致 npm run build 退出码 1、整站发布失败。而这条坏内容是在合入 main 之后、
# 发布时才被发现的。下面的护栏在「写回页面」之前拦住这类词法炸弹。

MDX_COMPILE_JS = (
    "const fs=require('fs');"
    "const{compile}=require('@mdx-js/mdx');"
    "compile(fs.readFileSync(process.argv[1],'utf8'),{jsx:false})"
    ".then(()=>{console.log('MDX_OK');})"
    ".catch(e=>{console.error(e.message.split('\\n')[0]);process.exit(1);});"
)

# 危险模式（纯标准库正则），用于在拿不到 node/@mdx-js 时兜底。
# 注意：**不能**用它在整页上做「有则拒绝」的全量判断 —— 本仓库大量使用合法 JSX
# （`<div style={{…}}>`、`</div>` 等），全量扫描在 198 个文件里会命中 160 个，
# 全部是误报，用它闸门会每周把自动化自己拦住。所以只做**增量**检测
# （见 new_mdx_dangers）：拿「新页面」减「原页面」，只关心本次新引入的危险。
# 已实测（@mdx-js/mdx 编译验证）以下写法安全、不会命中这些模式：
#   - 反引号内 ` <参数> `            -> 安全
#   - 围栏代码块内的 <访问地址>       -> 安全
#   - 比较运算 a < b、x < 10、| 参数 < 阈值 |  -> 安全
#   - 花括号里是纯标识符/中英文字（{参数}、{host}）-> 安全
_MDX_DANGER_PATTERNS = (
    ("裸尖括号标签（<参数>、<param>、<参数 >）",
     re.compile(r"<[A-Za-z\u4e00-\u9fa5][A-Za-z0-9_.\u4e00-\u9fa5 -]*>")),
    ("裸尖括号紧跟数字（x <3 个）",
     re.compile(r"<\d")),
    ("连续尖括号 / 箭头（<<、<-）",
     re.compile(r"<<|<-")),
    ("裸自动链接（<https://…>，应写 [文本](url)）",
     re.compile(r"<[A-Za-z][A-Za-z0-9+.-]*://")),
)


def _mask_code_spans(text: str) -> str:
    """把围栏代码块与行内代码里的字符替换成占位符，使危险模式扫描不会误伤。

    只改字符、不改长度与换行结构，便于按行号回溯定位。
    """
    out: list[str] = []
    in_fence = False
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            out.append("".join("\u0000" if ch not in "\r\n" else ch for ch in line))
            continue
        if in_fence:
            out.append("".join("\u0000" if ch not in "\r\n" else ch for ch in line))
            continue
        # 行内代码：按反引号成对替换（支持 `` 与 ` 两种）
        masked = re.sub(r"`+[^`\n]*`+", lambda m: "\u0000" * len(m.group(0)), line)
        out.append(masked)
    return "".join(out)


def scan_mdx_danger(text: str) -> list[str]:
    """返回危险模式的「行号: 问题描述: 片段」列表（屏蔽代码块/行内代码后扫描）。"""
    findings: list[str] = []
    masked = _mask_code_spans(text)
    raw_lines = text.splitlines()
    for idx, line in enumerate(masked.splitlines(), start=1):
        for label, pattern in _MDX_DANGER_PATTERNS:
            hit = pattern.search(line)
            if hit:
                raw = raw_lines[idx - 1] if idx - 1 < len(raw_lines) else ""
                findings.append("{0}: {1}: {2}".format(idx, label, raw.strip()[:120]))
    return findings


def new_mdx_dangers(new_text: str, old_text: str) -> list[str]:
    """增量危险检测：只报告新页面**比原页面多出来**的危险模式。

    为什么不能用绝对判断：仓库现有文档本就大量含合法 JSX（`<div style={{…}}>`、`</div>`），
    绝对扫描会把他们全判成危险 → 误拦。改成「按模式计数相减」，存量合法写法自动抵消，
    只有本次新增的危险才会被报出来（典型危险条目只引入 1~2 处，而存量是成百上千处）。
    仅用于无 node/@mdx-js 的兜底路径；有编译器时以真实编译结果为准。
    """
    def counts(text: str) -> dict[str, int]:
        masked = _mask_code_spans(text)
        out: dict[str, int] = {}
        for label, pattern in _MDX_DANGER_PATTERNS:
            hits = pattern.findall(masked)
            out[label] = sum(len(h) if isinstance(h, tuple) else 1 for h in hits)
        return out

    new_counts, old_counts = counts(new_text), counts(old_text)
    findings: list[str] = []
    for label, pattern in _MDX_DANGER_PATTERNS:
        delta = new_counts.get(label, 0) - old_counts.get(label, 0)
        if delta <= 0:
            continue
        raw_lines = new_text.splitlines()
        masked_lines = _mask_code_spans(new_text).splitlines()
        shown = 0
        for idx, line in enumerate(masked_lines, start=1):
            if not pattern.search(line):
                continue
            raw = raw_lines[idx - 1] if idx - 1 < len(raw_lines) else ""
            findings.append("{0}: 新增 {1} 处「{2}」: {3}".format(idx, delta, label, raw.strip()[:120]))
            shown += 1
            if shown >= delta:
                break
    return findings


# 可读的转义替身（避免正文被 MDX 当 JSX / 表达式解析，渲染后仍显示原文）
_ESCAPE_MAP = {"<": "&lt;", "{": "&#123;"}


def sanitize_mdx_text(text: str) -> tuple[str, list[str]]:
    """把裸尖括号/花括号转义为 HTML 实体，返回 (清洗后文本, 变更说明)。

    只处理落在代码块 / 行内代码之外的字符；已实测这类字符是 MDX 构建失败的唯一来源,
    转义后渲染结果与原文显示一致（内容不丢）。
    """
    if not text:
        return text, []
    notes: list[str] = []
    masked = _mask_code_spans(text)
    out: list[str] = []
    changed = 0
    for idx, ch in enumerate(text):
        if ch in _ESCAPE_MAP and masked[idx] == ch:
            out.append(_ESCAPE_MAP[ch])
            changed += 1
        else:
            out.append(ch)
    if changed:
        notes.append("转义了 {0} 个裸尖括号/花括号（防止 MDX 当成 JSX 标签解析）".format(changed))
    return "".join(out), notes


def sanitize_entry(entry: dict) -> dict:
    """对条目里所有会落入页面的文本字段做 MDX 转义。

    覆盖 title（进 `### 编号 标题` 标题行）、new_section（进 `## 编号 标题` 标题行）、
    question、body、see_also —— 任一漏掉都会以另一种方式触发构建失败。
    """
    notes: list[str] = []
    for field in ("title", "new_section", "question", "body", "see_also"):
        value = entry.get(field)
        if isinstance(value, str) and value:
            cleaned, sub = sanitize_mdx_text(value)
            entry[field] = cleaned
            notes += ["{0}：{1}".format(field, s) for s in sub]
    if notes:
        entry.setdefault("warnings", []).extend(notes)
    return entry


def mdx_compile_check(text: str, label: str = "community_faq",
                      baseline: str | None = None) -> tuple[bool, str]:
    """用 @mdx-js/mdx 真实编译校验；环境不具备时退化为**增量**危险模式检测。

    workflow 的 sparse-checkout 不含 node_modules，此时走正则兜底。兜底必须做增量
    （与 baseline 相比只报新增），否则会被仓库存量合法 JSX 误报 —— 实测全量扫描
    198 个文件命中 160 个、全是误报。
    这也是防护必须同时做在 Python 侧转义里的原因：不能只依赖编译校验。
    """
    node = shutil.which("node")
    has_compiler = (NODE_MODULES / "@mdx-js" / "mdx").is_dir()
    if node and has_compiler:
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "probe.md"
            probe.write_text(text, encoding="utf-8")
            try:
                proc = subprocess.run(
                    [node, "-e", MDX_COMPILE_JS, str(probe)],
                    capture_output=True, text=True, timeout=60,
                )
            except (OSError, subprocess.SubprocessError) as err:
                return True, "{0}：MDX 编译校验未能执行（{1}）".format(label, err)
        if proc.returncode == 0 and "MDX_OK" in proc.stdout:
            return True, "{0}：MDX 编译校验通过".format(label)
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        return False, "{0}：MDX 编译失败：{1}".format(label, err[0] if err else "未知错误")

    findings = new_mdx_dangers(text, baseline) if baseline is not None else scan_mdx_danger(text)
    if findings:
        return False, "{0}：MDX 危险模式（增量）检测不通过（无 node/@mdx-js，已退化）：\n  {1}".format(
            label, "\n  ".join(findings[:10]))
    return True, "{0}：本环境无 node/@mdx-js，已用增量危险模式检测替代（未发现新增风险）".format(label)


def _entry_fragment(entry: dict) -> str:
    """把条目按最终写进页面的形态渲染成片段，用于 MDX 编译校验。

    含 new_section 时一并渲染 `## 标题` 行 —— 新小节标题同样会变成 heading，
    漏掉它就会出现「逐条校验通过、整页构建失败」的盲区。
    """
    parts: list[str] = []
    new_sec = str(entry.get("new_section") or "").strip()
    if new_sec:
        parts += ["## 1 {0}".format(new_sec), ""]
    parts += _render_entry(1, 1, entry)
    return "\n".join(parts)


def mdx_entry_ok(entry: dict) -> bool:
    """按条目的最终渲染形态做一次编译校验。静默返回结果，由调用方决定如何记录。"""
    ok, _ = mdx_compile_check(_entry_fragment(entry), label=str(entry.get("title") or "entry"))
    return ok


def ensure_mdx_safe_entry(entry: dict) -> dict | None:
    """保证单条条目能被 MDX 编译；返回可直接入库的条目，或 None（该条丢弃）。

    策略是「先不动刀」：原文能编译就原样保留，避免误伤合法 HTML / JSX；
    只有编译不过时才做转义挽救；转义后仍不过则丢弃这一条（宁缺毋滥）。
    """
    if mdx_entry_ok(entry):
        return entry
    log("[community_faq] 条目未通过 MDX 校验，自动转义后重试：{0}".format(entry.get("title")))
    safe = sanitize_entry(entry)
    if mdx_entry_ok(safe):
        return safe
    # 转义后仍不合法：说明是护栏未覆盖的新写法，宁可丢弃也不让它进 main
    _, note = mdx_compile_check(_entry_fragment(safe), label=str(safe.get("title") or "entry"))
    log("[community_faq] 转义后仍无法编译，丢弃「{0}」：{1}".format(safe.get("title"), note))
    return None


def load_pairs_from_json(path: str) -> tuple[list[dict], list[dict]]:
    # utf-8-sig：容忍带 BOM 的文件（Windows 下手写/PowerShell 导出的 JSON 很常见）
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    pairs = payload.get("pairs") if isinstance(payload, dict) else payload
    if not isinstance(pairs, list):
        raise fail(2, f"{path} 里没有 pairs 列表")
    clean: list[dict] = []
    for p in pairs:
        if isinstance(p, dict) and p.get("question") and p.get("answer"):
            # 必须原样带回 answerer / answerer_ids / official：build_question_digest 会
            # 依据 official 打「[官方已答]」标记，compose_entry 也会用它们判断依据是否
            # 来自官方。丢字段会让 --pairs-json 的复现结果与线上跑出来的不一样。
            item = {"date": str(p.get("date") or ""), "group": str(p.get("group") or ""),
                    "time": str(p.get("time") or ""), "question": str(p["question"]),
                    "answer": str(p["answer"])}
            if p.get("answerer"):
                item["answerer"] = str(p["answerer"])
            ids = p.get("answerer_ids")
            if isinstance(ids, list):
                item["answerer_ids"] = [str(i) for i in ids]
            if p.get("official"):
                item["official"] = True
            clean.append(item)
    stats: dict[str, int] = {}
    for p in clean:
        stats[p["date"]] = stats.get(p["date"], 0) + 1
    by_day = [{"date": d, "pairs": n} for d, n in sorted(stats.items())]
    return clean, by_day


# ---------------------------------------------------------------- 入口

def enabled_products() -> list[str]:
    """已启用的产品 key（保持 PRODUCTS 的声明顺序，与 gen_changelog_multi.py 一致）。"""
    return [k for k, v in PRODUCTS.items() if v.get("enabled", True)]


def emit_matrix(raw: str) -> int:
    """输出产品名 JSON 数组（供 workflow 的 matrix 使用）。

    带参数时按逗号分隔的白名单过滤；不带参数输出全部启用产品。
    与 gen_changelog_multi.py --matrix 行为一致，便于两个 workflow 用同一套写法。
    """
    enabled = enabled_products()
    items = [x.strip().lower() for x in raw.split(",") if x.strip()] if raw.strip() else enabled
    bad = [x for x in items if x not in enabled]
    if bad:
        log("[community_faq] 未知或已停用的产品：{0}（可用：{1}）".format(
            "、".join(bad), "、".join(enabled)))
        return 2
    print(json.dumps(items, ensure_ascii=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="从芝麻会话沉淀指定产品的社区常见问题到官方文档")
    ap.add_argument("--product", default="",
                    help="产品 key（{0}）；留空=jumpserver".format("/".join(PRODUCTS)))
    ap.add_argument("--list", action="store_true", help="只列出已启用产品后退出")
    ap.add_argument("--matrix", nargs="?", const="", default=None, metavar="PRODUCTS",
                    help="输出产品名 JSON 数组后退出（可带逗号分隔的白名单，留空=全部启用产品）")
    ap.add_argument("--print-config", action="store_true",
                    help="按 --product 解析并输出该产品的配置 JSON 后退出（供 workflow 取分支名/目录）")
    ap.add_argument("--days", type=int, default=8,
                    help="回看天数（含今天），默认 8：多留一天以补回上次运行漏掉的那半天")
    ap.add_argument("--max-items", type=int, default=MAX_ITEMS_CEILING,
                    help="一个 PR 里条目总数的上限（含上期续接的条目），默认 {0}，"
                         "再大也会被 MAX_ITEMS_CEILING 压到 {0}".format(MAX_ITEMS_CEILING))
    ap.add_argument("--min-items", type=int, default=MIN_ITEMS,
                    help="引导模型至少选几条，默认 {0}。**只作 prompt 引导**：模型判断"
                         "够格的不够时会照实少选，不会硬凑".format(MIN_ITEMS))
    ap.add_argument("--min-count", type=int, default=2,
                    help="（已弱化）出现次数仅作参考，选题以长期复用价值为准；保留仅为兼容")
    ap.add_argument("--apply", action="store_true", help="写回页面（默认只预览）")
    ap.add_argument("--skip-llm", action="store_true", help="只取数+聚类，不调模型")
    ap.add_argument("--pairs-json", default="", help="改用本地问答对 JSON，跳过取数")
    ap.add_argument("--dump-pairs", default="", help="把问答对写入该 JSON，便于排查")
    ap.add_argument("--report", default="", help="变更报告输出路径（markdown）")
    ap.add_argument("--pending-reuse", default="",
                    help="上期待续接清单 JSON（被名额截断的条目，本轮优先续接）")
    ap.add_argument("--pending-out", default="",
                    help="本轮被名额截断的条目写入该 JSON（随固定分支提交；传了且 --apply 时"
                         "无截断也会写空清单以清掉旧条目）")
    ap.add_argument("--reuse-page", default="",
                    help="上期固定分支的页面文件：只取其中多出来的条目续接进来（**整份文件永不覆盖当前页面**）")
    args = ap.parse_args()

    # 这两个开关不依赖产品配置，先处理（workflow 的 list job 用 --matrix）
    if args.list:
        print("\n".join(enabled_products()))
        return 0
    if args.matrix is not None:
        return emit_matrix(args.matrix)
    if args.print_config:
        conf = resolve_product(args.product)
        owner, oncall = owners_for(conf)
        out = {k: conf[k] for k in ("key", "docs", "faq_rel", "branch", "min_md")}
        out["owner"] = owner
        out["oncall"] = oncall
        print(json.dumps(out, ensure_ascii=False))
        return 0

    conf = use_product(args.product)

    # 群名关键词：PRODUCTS 表是默认值，PRODUCT_KEYWORD 环境变量可覆盖（历史兼容）。
    # 保留这个覆盖口是因为线上 JumpServer 任务一直靠 env 传值，改配置表不能让老任务行为漂移。
    env_keyword = cfg("PRODUCT_KEYWORD")
    keyword = env_keyword or conf["keyword"]
    log("[community_faq] 群名关键词 {0!r}（来源：{1}）".format(
        keyword, "PRODUCT_KEYWORD 环境变量" if env_keyword else "PRODUCTS 表"))
    stats: dict | None = None
    if args.pairs_json:
        pairs, by_day = load_pairs_from_json(args.pairs_json)
        log(f"[community_faq] 从 {args.pairs_json} 载入问答对 {len(pairs)} 条")
    else:
        pairs, by_day, stats = collect_pairs(args.days, keyword)

    if args.dump_pairs:
        Path(args.dump_pairs).write_text(
            json.dumps({"days": args.days, "total": len(pairs), "pairs": pairs},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        log(f"[community_faq] 问答对已写出: {args.dump_pairs}")

    log("[community_faq] 问答对 {0} 条".format(len(pairs)))
    if stats and stats.get("failures"):
        log("[community_faq] 注意：{0}/{1} 个取数请求失败，本期频次统计可能偏低（报告里已标注）".format(
            stats["failures"], stats["attempts"]))

    if args.skip_llm:
        log("[community_faq] --skip-llm：不调模型，仅列出提问清单前 20 行")
        for line in build_question_digest(pairs).splitlines()[:20]:
            log("[community_faq]   " + line)
        return 0
    if not pairs:
        # 必须区分「取数坏了」和「群里确实没消息」：接口整体挂掉若也返回 3，
        # workflow 会当成「本周无新增」绿色通过，静默跳过一整周而没人发现。
        if stats and stats.get("failures"):
            log("[community_faq] 取数失败：{0}/{1} 个请求出错，无法确认本周是否有新问题".format(
                stats["failures"], stats["attempts"]))
            return 1
        if stats and not stats.get("rows"):
            log("[community_faq] 所有群在所有日期都没取到任何消息，疑似接口异常或群范围配置有误")
            return 1
        log("[community_faq] 取到消息但没有形成问答对，跳过")
        return 3

    def emit_empty_report(note: str, funnel: dict | None = None,
                          candidates: list[dict] | None = None) -> None:
        """无新增条目时也落一份报告，否则 Actions 摘要在「本周无新增」时一片空白，
        长达一整周都只能翻日志才能知道为什么没产出。"""
        try:
            report = args.report or str(Path(tempfile.gettempdir()) / "community-faq-report.md")
            write_report(report, pairs=pairs, placed=[], skipped=skipped,
                         by_day=by_day, days=args.days, applied=False,
                         fetch_note=fetch_summary(stats), note=note, funnel=funnel,
                         candidates=candidates, cap=total_cap, reused_n=len(reused))
            set_action_output(False, 0, report)
            log("[community_faq] 已写出报告：{0}".format(report))
        except OSError as err:
            log("[community_faq] 写报告失败（忽略）: {0}".format(err))

    page = read_page()
    index = doc_index()
    keys = existing_entry_keys(page)

    # 一个 PR 里的**条目总数**上限（含上期续接）。超过说明调用方传了过大的值，
    # 压回 CEILING；下限至少 1，否则什么都加不了。
    total_cap = max(1, min(args.max_items, MAX_ITEMS_CEILING))
    min_items = max(1, min(args.min_items, total_cap))

    entries: list[dict] = []
    skipped: list[dict] = []
    reused: list[dict] = []
    # 先把上期未合并的条目续接进来，再跑本期模型选题，避免同一问题本期重复入选
    if args.reuse_page:
        reused, reused_skipped = reuse_entries_from_page(Path(args.reuse_page), page)
        skipped.extend(reused_skipped)
    # 待续接清单的条目等了至少一轮，排在页面续接前面，优先占名额
    pending_prev, pending_skipped = load_pending_reuse(args.pending_reuse, keys)
    skipped.extend(pending_skipped)
    reused = pending_prev + reused
    # 续接条目**也占名额**：超出的写进待续接清单（pending-out），随固定分支提交、
    # 下轮优先续接 —— 固定分支每轮从 main 重建，不落盘就是永久丢失（2026-10-15 复核确认）。
    overflow = reused[total_cap:]
    if overflow:
        for entry in overflow:
            skipped.append({"title": entry.get("title"),
                            "reason": "续接条目超出本 PR 名额（上限 {0} 条），"
                                      "已写入待续接清单，下轮优先续接".format(total_cap)})
        log("[community_faq] 续接候选 {0} 条超出名额上限 {1}，本轮取前 {1} 条，"
            "其余 {2} 条写入待续接清单".format(len(reused), total_cap, len(overflow)))
        reused = reused[:total_cap]
    for entry in reused:
        keys.add(normalize_text(entry["title"])[:40])
        q_probe = normalize_text(str(entry.get("question") or ""))[:40]
        if q_probe:
            keys.add(q_probe)
    if reused or pending_prev:
        log("[community_faq] 续接条目 {0} 条（占名额 {0}/{1}；其中待续接清单 {2} 条）".format(
            len(reused), total_cap, len(pending_prev)))

    # 留给「本期新增」的名额 = 总数上限 - 已续接。续接满额时这里为 0，
    # 本轮就不选新的（但报告仍会给出候选排序，方便人工判断该不该调大 --max-items）。
    remaining = max(0, total_cap - len(reused))
    log("[community_faq] 本期新增名额 {0} 条（总数上限 {1} - 续接 {2}）".format(
        remaining, total_cap, len(reused)))
    candidates = screen_questions(pairs, page, index, remaining, min_items) if remaining else []
    log("[community_faq] 模型初选 {0} 条".format(len(candidates)))
    for item in candidates:
        log("[community_faq]   候选 kind={0} conf={1} score={2} ｜ {3}".format(
            str(item.get("kind") or "?").upper(), item.get("confidence"),
            item.get("score"), item.get("title")))
    # 名额被续接占满（remaining==0 → 模型未被调用）时 reused 必非空，直接走下面的
    # 入库路径提交续接条目即可；这里只处理「续接与初选都为空」的真·无货场景。
    if not candidates and not reused:
        log("[community_faq] 模型没有选出合格问题")
        emit_empty_report("模型初选为 0：本期没有值得沉淀的主题（全部被判为一次性个案/无结论/重复）。",
                          funnel_stats(stats, pairs, [], 0, 0))
        print(json.dumps({"changed": False, "count": 0}, ensure_ascii=False))
        # 被否决/判重的 pending 条目不再留在清单里（否则下轮原样复活）；
        # overflow 为空时写空清单同样起到「清旧」作用
        if args.apply and args.pending_out:
            write_pending_out(args.pending_out, overflow)
        return 3
    limit = digest_limit(len(pairs))
    for item in candidates:
        if len(entries) >= remaining:
            break
        kind = str(item.get("kind") or "").strip().upper()
        if kind in ("B", "D"):
            skipped.append({"title": item.get("title"),
                            "reason": "模型判定为{0}（{1}），不具沉淀价值".format(
                                kind, "一次性个案" if kind == "B" else "未解决/无结论")})
            continue
        if item.get("rejected_by") == "confidence=low":
            # 分数沉底只是排序手段，这里明确记一条，避免「分数低但没说为什么」
            skipped.append({"title": item.get("title"),
                            "reason": "结论不明确（kind={0} 但同批存在 confidence=high 候选，本条只标 low）".format(kind)})
            continue
        ids = valid_question_ids(item, limit)
        if not ids:
            skipped.append({"title": item.get("title"),
                            "reason": "没有有效的社区问题编号"})
            continue
        title = str(item.get("title") or "")
        probe = normalize_text(title)[:40]
        if probe and probe in keys:
            skipped.append({"title": item.get("title"), "reason": "与页面已有条目标题重复"})
            continue
        dup = near_duplicate(title, keys)
        if dup:
            skipped.append({"title": item.get("title"),
                            "reason": "与页面已有条目标题近似（最像：{0}）".format(dup)})
            continue
        entry = compose_entry(item, pairs, index)
        if entry is None:
            skipped.append({"title": item.get("title"), "reason": "模型判定依据不足或成稿失败"})
            continue
        # MDX 安全护栏：原文能编译就不动刀（避免误伤合法 HTML/JSX）；
        # 编译不过则自动转义挽救；转义后仍不合法就丢弃这一条，绝不把词法炸弹写进页面
        safe_entry = ensure_mdx_safe_entry(entry)
        if safe_entry is None:
            skipped.append({"title": entry["title"], "reason": "MDX 编译校验失败（转义后仍不合法），已丢弃"})
            continue
        entry = safe_entry
        final_key = normalize_text(entry["title"])[:40]
        if final_key in keys:
            skipped.append({"title": entry["title"], "reason": "成稿后与页面已有条目重复"})
            continue
        dup = near_duplicate(entry["title"], keys)
        if dup:
            skipped.append({"title": entry["title"],
                            "reason": "成稿后与页面已有条目标题近似（最像：{0}）".format(dup)})
            continue
        keys.add(final_key)
        entries.append(entry)

    if reused:
        entries = reused + entries
        log("[community_faq] 入库 {0} 条（其中上期续接 {1} 条，本期新增 {2} 条；总数上限 {3}）"
            .format(len(entries), len(reused), len(entries) - len(reused), total_cap))
        new_page, placed = insert_entries(page, entries)
        if new_page == page:
            log("[community_faq] 页面无变化")
            set_action_output(False, 0, "")
            return 3
        page_ok, page_note = mdx_compile_check(new_page, label=str(FAQ_PAGE), baseline=page)
        log("[community_faq] 整页 MDX 校验：{0}".format(page_note))
        if not page_ok:
            log("[community_faq] 拒绝写回：页面无法通过 MDX 编译，页面保持原样")
            return 5
        report = args.report or str(Path(tempfile.gettempdir()) / "community-faq-report.md")
        write_report(report, pairs=pairs, placed=placed, skipped=skipped,
                     by_day=by_day, days=args.days, applied=args.apply,
                     fetch_note=fetch_summary(stats),
                     funnel=funnel_stats(stats, pairs, candidates, len(placed), len(skipped)),
                     candidates=candidates, cap=total_cap, reused_n=len(reused))
        if args.apply:
            FAQ_PAGE.write_text(new_page, encoding="utf-8")
            # 截断条目落盘为待续接清单；无截断时也要写空清单，把已续接走的旧条目清掉
            if args.pending_out:
                write_pending_out(args.pending_out, overflow)
            log("[community_faq] 已写回 {0}（新增/续接 {1} 条）".format(FAQ_PAGE, len(placed)))
        else:
            log("[community_faq] 预览模式，未写回（新增/续接 {0} 条）".format(len(placed)))
        set_action_output(True, len(placed), report)
        print(json.dumps({"changed": bool(placed), "count": len(placed), "report": report},
                         ensure_ascii=False))
        return 0

    if not entries:
        log("[community_faq] 没有可入库的新条目")
        report = args.report or str(Path(tempfile.gettempdir()) / "community-faq-report.md")
        write_report(report, pairs=pairs, placed=[], skipped=skipped,
                     by_day=by_day, days=args.days, applied=False,
                     fetch_note=fetch_summary(stats),
                     note="模型初选 {0} 个主题，但全部在成稿环节被否决（逐条原因见下方「未采纳的候选」）。"
                          .format(len(candidates)),
                     funnel=funnel_stats(stats, pairs, candidates, 0, len(skipped)),
                     cap=total_cap, reused_n=len(reused),
                     candidates=candidates)
        set_action_output(False, 0, report)
        print(json.dumps({"changed": False, "count": 0, "report": report}, ensure_ascii=False))
        if args.apply and args.pending_out:
            # pending 条目全部被否决/判重时，清空清单避免下轮原样复活
            write_pending_out(args.pending_out, [])
        return 3

    new_page, placed = insert_entries(page, entries)
    if new_page == page:
        log("[community_faq] 插入后页面无变化")
        set_action_output(False, 0, "")
        return 3

    # 最后一道闸：整页编译校验（兜底路径传原页面作基线，只报本次新增的危险模式）
    page_ok, page_note = mdx_compile_check(new_page, label=str(FAQ_PAGE), baseline=page)
    log("[community_faq] 整页 MDX 校验：{0}".format(page_note))
    if not page_ok:
        log("[community_faq] 拒绝写回：页面无法通过 MDX 编译，页面保持原样")
        return 5

    report = args.report or str(Path(tempfile.gettempdir()) / "community-faq-report.md")
    write_report(report, pairs=pairs, placed=placed, skipped=skipped,
                 by_day=by_day, days=args.days, applied=args.apply,
                 fetch_note=fetch_summary(stats),
                 funnel=funnel_stats(stats, pairs, candidates, len(placed), len(skipped)),
                 candidates=candidates, cap=total_cap, reused_n=len(reused))

    if args.apply:
        FAQ_PAGE.write_text(new_page, encoding="utf-8")
        # 无续接路径同样要写待续接清单（清空旧 pending，避免已消费条目下轮复活）
        if args.pending_out:
            write_pending_out(args.pending_out, overflow)
        log(f"[community_faq] 已写回 {FAQ_PAGE}")
    else:
        log("[community_faq] 预览模式，未写回页面。新增内容：")
        for row in placed:
            log(f"[community_faq]   {row['no']} {row['entry']['title']}")

    set_action_output(args.apply, len(placed), report)
    print(json.dumps({"changed": True, "applied": args.apply, "count": len(placed), "report": report,
                      "items": [r["no"] + " " + r["entry"]["title"] for r in placed]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        sys.exit(130)

