# 飞致云文档中心

使用 Rspress 2 构建 [docs.fit2cloud.com](https://docs.fit2cloud.com/)：一个仓库管理飞致云所有产品的文档，门户首页复刻原站样式，各产品文档使用 Rspress 默认主题。每个产品独立构建（拥有自己的版本列表和 URL 前缀），最终合并为一个静态站点。

## 运行

需要 Node.js 24 和 pnpm 12.4.2。

```bash
pnpm install
pnpm dev            # 统一开发服务器，默认 http://localhost:3000/
pnpm build          # 完整构建到 build/
pnpm preview        # 预览构建产物，默认 http://localhost:4173/
```

`pnpm dev` 先启动门户；首次访问某个产品时再按需启动该产品的开发服务器，并代理到同一端口，因此只需记住 `http://localhost:3000/`。产品开发服务器首次启动需要几秒，之后热更新正常。日常只开发一个产品时，可以跳过代理：

```bash
pnpm dev --project halo           # 只启动 Halo，直接访问其自身端口
pnpm build --project 1panel       # 只更新一个产品的构建产物
pnpm typecheck                    # TypeScript 检查
pnpm verify:build                 # 检查构建产物中的本地链接和图片
pnpm check:ci                     # Rslint + Rsfmt 检查（提交前执行）
```

全量构建包含 8 个产品、13 个产品版本和门户；MeterSphere 与参考站一致，链接到外部文档。全量构建在本地使用四并发，CI 环境（`CI=true`）使用双并发。每个产品使用独立的工作目录和缓存；不要同时运行多个全量构建命令，它们会清理同一个 `build/` 目录。

## 目录

- `portal/projects.json`：产品注册表，包含名称、入口、版本列表、语言列表和 logo；第一个版本为当前版。
- `portal/pages/`：门户首页和搜索结果页。
- `portal/shared/`：门户与产品文档共用的 header，以及门户首页、页脚和跨产品搜索。
- `portal/docs-theme/`：Rspress 默认文档主题，通过插槽复用门户 header，并添加九宫格产品切换和 Halo 页脚。
- `content/<产品>/<版本>/<语言>/`：各产品正文。
- `content/<产品>/sidebars.json`：按版本组织的侧栏；可添加 `sidebars.en.json` 等翻译侧栏。
- `content/<产品>/public/`：产品图片等资源。
- `content/<产品>/titles.json`：侧栏标题文案。
- `portal/public/`：门户公共品牌素材和跨产品搜索索引。

各产品使用自己的 Rspress `base`、`multiVersion` 和 `locales`，互不共用版本列表。URL 示例：

| 内容                         | 路径              |
| ---------------------------- | ----------------- |
| 1Panel 当前版中文            | `/1panel/`        |
| 1Panel v1 中文               | `/1panel/v1/`     |
| JumpServer v4 中文           | `/jumpserver/v4/` |
| 后续增加的 1Panel 当前版英文 | `/1panel/en/`     |
| 后续增加的 1Panel v1 英文    | `/1panel/v1/en/`  |

增加版本时，在 `portal/projects.json` 对应产品的 `versions` 中登记，并添加该版本目录、侧栏和 `content/<产品>/sidebars.json` 条目；版本和语言切换由 Rspress 默认导航提供。版本切换保留当前页面路径；目标版本没有该页面时回到该版本首页。

Halo 文档直接从 [halo-dev/docs](https://github.com/halo-dev/docs) 复制，保留 `_nav.json`、`_meta.json` 和原有内部路径；其首页与其他产品一样使用统一的产品概览风格，位于 `content/halo/v2/zh/index.mdx`。

参考仓库没有完整的产品英文文档，目前仅导入真实中文内容，没有生成或展示虚假的英文翻译。

## 导入参考内容

```bash
pnpm import:docs /path/to/fit2cloud-docs
```

导入脚本复制正文、历史版本、图片和侧栏，处理 Docusaurus MDX、代码块语言和 URL 编码差异。来源提交和文档数量记录在 `content/source.json`。再次导入会覆盖导入的正文；Halo 的内页和原导航配置保留。

各项目当前版本首页同步参考仓库的产品概览布局，使用简介、操作按钮、视频封面和分组文档链接，并保留 Rspress 默认侧栏。只同步这些首页时运行：

```bash
pnpm import:homepages /path/to/fit2cloud-docs
```

该命令转换首页组件、样式变量和 Docusaurus 路径，复制视频封面，并补齐新版 AI 网关首页引用的离线安装、命令行工具文档。来源记录在 `content/homepages-source.json`；历史版本首页保持原样。完整导入也会执行此步骤，Halo 仅同步概览页，原产品介绍与内部文档保留。

门户图片和样式来自参考仓库；智能小助手使用参考站公开的 MaxKB 服务，点击后才加载 iframe，此服务需要联网。搜索使用构建时生成的本地全文索引，不依赖搜索后端；首页跨产品搜索当前版本，文档页使用 Rspress 默认本地搜索。

## 构建与部署

`build/` 是最终部署目录，各站点直接输出到此目录。`.site-work/<产品>/` 保存独立工作目录和编译缓存，不存放文档副本。全量构建先清理 `build/` 并构建门户，再以本地四并发、CI 双并发构建产品，最后将门户公共资源复制到根目录一次。构建失败时停止派发任务并终止其余构建，命令返回失败。单独构建门户时保留产品目录，单独构建产品时只清理该产品目录。搜索索引由构建脚本生成，不要手改。

每个产品的产物放在 `build/<产品>/`。产品图片只保存在 `build/<产品>/img/`，门户品牌素材只保存在 `build/img/`，跨产品搜索索引只保存在 `build/search-index.json`。Markdown 图片继续使用 `/img/...`，由 Rspress 添加项目路径；原生 MDX `<img>` 使用部署路径表达式（如 `src={"/halo/img/..."}`），导入脚本自动转换；普通 `.md` 中的 HTML 图片则使用 `src="/halo/img/..."`。这些部署路径由 `pnpm verify:build` 检查，避免复制两份产品图片。单产品开发服务同时提供产品资源和门户公共资源。静态服务器需支持无扩展名页面，例如 Nginx：

```nginx
location / {
    try_files $uri $uri.html $uri/index.html =404;
}
```

外部产品官网、MeterSphere 文档、视频和智能小助手保留真实外链。构建检查本地文档链接和图片；不替代外部服务可用性检查。

## LLM 友好

门户在 `build/llms.txt` 汇总各站内项目的 `llms.txt` 入口，外部项目另列文档地址；各产品在构建时独立生成自己的 `llms.txt` 和 `llms-full.txt`（包含各自历史版本）。索引由 Rspress 根据文档结构生成，不需要维护额外清单。
