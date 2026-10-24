#!/usr/bin/env python3
"""
JumpServer 更新日志自动生成脚本（Rspress / fit2cloud-docs）

从社区发布 API 取指定版本的发布说明，按本仓库 change_log.md 的既有格式
生成一个新版本区块，插入到对应更新日志文件的顶部。

用法:
    python .github/scripts/gen_changelog.py v5.0.1
    python .github/scripts/gen_changelog.py v4.10.20-lts
    python .github/scripts/gen_changelog.py v4.10.20 --dry-run     # 只看结果不落盘
    python .github/scripts/gen_changelog.py v4.10.20 --print-target # 只打印目标文件路径

版本 → 目标文件（按主版本号路由，v3/v4 的版本化文档与当前版本文档分属不同目录）:
    v5.x 及以后 -> content/jumpserver/v5/zh/change_log.mdx
    v4.x        -> content/jumpserver/v4/zh/change_log.mdx
    v3.x        -> content/jumpserver/v3/zh/change_log.mdx

退出码: 0=成功或已存在无需修改, 1=版本在社区列表中不存在, 2=参数/文件错误,
        3=版本与目标文件不匹配(见 sanity_check, 路由配置可能已过期)
"""
from __future__ import annotations

import sys, json, re, html, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

API_URL = "https://community.fit2cloud.com/v1/products/jumpserver/releases"
TZ = timezone(timedelta(hours=8))

# 主版本号 -> 更新日志文件。新增大版本时在此补一行。
TARGET_MAP = {
    '3': 'content/jumpserver/v3/zh/change_log.mdx',
    '4': 'content/jumpserver/v4/zh/change_log.mdx',
    '5': 'content/jumpserver/v5/zh/change_log.mdx',
}
DEFAULT_TARGET = 'content/jumpserver/v5/zh/change_log.mdx'

# 列表项自带的前缀，如 "fix: xxx" / "perf：xxx"；生成时统一归一成 "- <tag>: xxx"
PREFIX_RE = re.compile(r'^(feat|perf|fix|note)\s*[:：]\s*', re.I)

# 发布说明小标题 -> tag。按顺序匹配，先命中者胜:
# 「修复」优先于「优化」，否则「功能优化」这类标题会被误判成 feat。
TITLE_RULES = (
    (('修复', 'bug', 'fix'), 'fix'),
    (('优化', 'improve', 'perf'), 'perf'),
    (('功能', 'new', 'feature'), 'feat'),
)

# 版本块格式（与现有 change_log.md 保持一致）:
#     v4.10.19
#     ------------------------
#     2026年8月20日
#
#     - feat: ...
#     - feat: ...
#
#     - perf: ...
#
#     - fix: ...
#
# 即: 日期后空 2 行、各组之间空 2 行、块尾空 1 行（块自身以 \n\n 结束）
SEP = '------------------------'

H2_UL = re.compile(r'<h2><a[^>]*></a>([^<]+)</h2>\n?(<ul>.*?</ul>)', re.S)
LI = re.compile(r'<li>(.*?)</li>', re.S)
PARA = re.compile(r'<p>(.*?)</p>', re.S)
FRONTMATTER = re.compile(r'\A---[ \t]*\r?\n.*?\r?\n---[ \t]*\r?\n', re.S)


def fetch():
    with urllib.request.urlopen(API_URL, timeout=30) as r:
        return json.loads(r.read().decode())


def normalize(v: str) -> str:
    """去掉 -lts / -LTS 后缀，社区 API 中 LTS 版本形如 v4.10.19-lts。"""
    return re.sub(r'-lts$', '', (v or '').strip(), flags=re.I)


def find_release(target: str, data):
    for rel in data:
        if normalize(rel.get('version', '')) == target:
            return rel
    return None


def flatten(s: str) -> str:
    """剥掉 HTML 标签与多余空白，得到单行纯文本。"""
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', s or ''))).strip()


def title_tag(title: str) -> str:
    """由发布说明小标题推断 tag。

    标题形态在历史数据里并不统一：有「修复」，也有「问题修复」「2.1 功能优化」，
    英文版还有 What’s new / Improvements / Bug fixes（含弯引号）。因此先去掉编号
    前缀、统一弯引号与大小写，再做关键词包含匹配，而非精确查表。
    """
    t = title.replace('\u2018', "'").replace('\u2019', "'")
    t = re.sub(r'^\s*[\d.]+\s*', '', t.strip()).lower()
    for keys, tag in TITLE_RULES:
        for k in keys:
            if k in t:
                return tag
    return 'note'


def build_block(rel: dict) -> str:
    version = normalize(rel['version'])
    ts = rel.get('publishTime')
    dt = datetime.fromtimestamp(ts / 1000, tz=TZ) if ts else datetime.now(tz=TZ)
    date_str = f"{dt.year}年{dt.month}月{dt.day}日"

    html_content = rel.get('releaseNoteH') or ''

    # 优先按 h2+ul 分节；历史版本里也有只有 ul 或只有 p 的情况，逐级兜底
    sections = H2_UL.findall(html_content)
    if not sections:
        sections = [(None, ul) for ul in re.findall(r'<ul>(.*?)</ul>', html_content, re.S)]
    if not sections and flatten(html_content):
        sections = [(None, html_content)]

    order: list = []
    items_by_tag: dict = {}
    for title, body_html in sections:
        default_tag = title_tag(title) if title else 'note'
        raw_items = LI.findall(body_html) if '<li' in body_html else PARA.findall(body_html)
        if not raw_items:
            raw_items = [body_html]

        for raw in raw_items:
            text = flatten(raw)
            if not text:
                continue
            # 条目自带前缀时以它为准（v3 系列数据自带 fix:/perf:），并剥掉避免重复
            m = PREFIX_RE.match(text)
            tag = m.group(1).lower() if m else default_tag
            if m:
                text = PREFIX_RE.sub('', text).strip()
            if not text:
                continue
            if tag not in items_by_tag:
                items_by_tag[tag] = []
                order.append(tag)
            items_by_tag[tag].append(f"- {tag}: {text}")

    groups = ['\n'.join(items_by_tag[t]) for t in order]
    if not groups:
        raise ValueError(f'{version} 的发布说明为空，无法生成条目')

    return '\n'.join([version, SEP, date_str]) + '\n\n\n' + '\n\n\n'.join(groups) + '\n\n'


def insert(content: str, block: str) -> str:
    """插到 frontmatter 之后；没有 frontmatter 时插到文件开头。"""
    m = FRONTMATTER.match(content)
    if m:
        return content[:m.end()] + '\n' + block + content[m.end():].lstrip('\r\n')
    return block + content.lstrip('\r\n')


def sanity_check(version: str, path: Path, content: str) -> None:
    """写入前的护栏：确认 version 与目标文件确实匹配。

    为什么需要: TARGET_MAP 是硬编码的。每次发布新大版本都要做版本快照
    (docusaurus docs:version:jumpserver v5)，它会把整个 jumpserver-docs/
    复制成 jumpserver_versioned_docs/version-v5/，而 jumpserver-docs/ 随即
    代表下一个大版本；但 TARGET_MAP 不会自动跟着变。若不检查，旧大版本的
    补丁会被静默写进新大版本的文档里，且不报任何错。

    规则:
      1. 目标是 *_versioned_docs/version-vX/ 时, X 必须等于 version 的主版本
      2. 目标文件中已出现比 version 更大的主版本 -> 报错(映射漂移的铁证)
      3. 目标文件中既无同主版本、也无更大主版本 -> 只警告(新大版本首发属正常)

    不匹配时抛 ValueError, 由 main() 转成退出码 3。
    """
    major = int(re.match(r'v(\d+)', version).group(1))

    m = re.search(r'version-v(\d+)/', str(path).replace('\\', '/'))
    if m and int(m.group(1)) != major:
        raise ValueError(
            f'目标文件 {path} 是 v{m.group(1)} 的版本快照，与 {version} 的主版本不符；'
            f'请检查 TARGET_MAP 是否已随版本快照更新')

    majors = {int(x) for x in re.findall(r'^v(\d+)\.', content, re.M)}
    if not majors:
        print(f'WARNING: {path} 里没有任何版本条目，无法校验路由是否正确', file=sys.stderr)
        return
    if max(majors) > major:
        raise ValueError(
            f'{path} 里已有 v{max(majors)} 的条目(比 {version} 更新)，'
            f'{version} 应写在更旧的版本目录里；TARGET_MAP 很可能已过期')
    if major not in majors:
        print(f'WARNING: {path} 里暂无 v{major} 的条目，按新大版本首发处理', file=sys.stderr)


def resolve_target(version: str):
    m = re.match(r'v(\d+)', version)
    if not m:
        return None
    return Path(TARGET_MAP.get(m.group(1), DEFAULT_TARGET))


def main() -> int:
    argv = sys.argv[1:]
    dry_run = '--dry-run' in argv
    print_target = '--print-target' in argv
    args = [a for a in argv if not a.startswith('--')]

    if not args:
        print('Version arg required, e.g. v5.0.1 or v4.10.20-lts', file=sys.stderr)
        return 2

    raw = args[0].strip()
    if not raw.startswith('v'):
        raw = 'v' + raw
    target = normalize(raw)

    path = resolve_target(target)
    if path is None:
        print(f'Cannot parse major version from {target!r}', file=sys.stderr)
        return 2

    if print_target:
        print(path)
        return 0

    if not path.exists():
        print(f'Changelog file not found: {path}', file=sys.stderr)
        return 2

    content = path.read_text(encoding='utf-8')

    # 先校验路由，再判断"是否已存在"，否则映射漂移时会被静默跳过
    try:
        sanity_check(target, path, content)
    except ValueError as e:
        print(f'Sanity check failed: {e}', file=sys.stderr)
        return 3

    # 版本号独占一行才算已存在；v4.10.1 不会被 v4.10.19 误判
    if re.search(rf'^{re.escape(target)}$', content, re.M):
        print(f'{target} already exists in {path}, skip.')
        return 0

    rel = find_release(target, fetch())
    if not rel:
        print(f'Target version {raw} (normalized {target}) not found in community release list',
              file=sys.stderr)
        return 1

    block = build_block(rel)

    if dry_run:
        print(f'--- dry-run: would insert into {path} ---')
        print(block, end='')
        return 0

    path.write_text(insert(content, block), encoding='utf-8')
    print(f'Inserted {target} into {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
