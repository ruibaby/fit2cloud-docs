# 文档发布 Action

发布由 `.github/workflows/deploy-oss.yml` 完成，仅手动触发，一个 Job 内依次执行：
检出代码 → `pnpm install --frozen-lockfile` → `pnpm build` → OSS 同步 → 可选 CDN 刷新。

## 构建

- 仓库要求 Node.js 24 和 pnpm 12；工作流用 `pnpm/action-setup` 与 `actions/setup-node` 的 pnpm 缓存安装依赖。
- `pnpm build` 按 `scripts/docs.mjs` 编排：先构建门户到 `build/` 根目录，再并发构建各产品到 `build/<产品>/`；CI 环境使用双并发。
- 构建末尾生成 `build/sitemap.xml`（汇总门户、全部产品和历史版本的页面）并复制门户公共资源，因此 `build/` 可直接作为完整站点镜像。
- 构建末尾把 Rspress 的平铺页面（`page.html`）转为目录索引（`page/index.html`）。OSS 静态托管没有无扩展名重写，这一步让 `/page`（OSS 会 302 到 `/page/`）和旧站已有的 `/page/` 链接都能正常打开。
- 构建还会为旧站 6 个 AI 网关 slug 地址生成跳转页，旧链接不会 404。
- 新增产品、版本或页面后无需改工作流，重新执行构建即可。

## 同步与刷新

核心同步命令：

```bash
./ossutil sync ./build/ "oss://$ALIYUN_OSS_BUCKET/" --delete --checksum -f --job 20
```

- 上传并发从 ossutil 默认的 `3` 提高到 `20`，图片较多的站点可减少传输等待；实际耗时仍受总带宽限制。
- `ossutil 2.4.0` 的 `--checksum` 仅对 OSS 对象之间拷贝生效，本地上传仍可能全量传输；同大小但内容变化的文件会正常覆盖。
- 同步以 `build/` 镜像 Bucket 根目录，`--delete` 会删除云端多余文件，包括已下线的产品版本。
- CDN 刷新提供两种方式：`directory` 刷新整站目录，`url-all` 按本次构建的 HTML 生成完整 URL 批量刷新；可通过 `purge_cdn=false` 跳过。

## 需要的 Secrets

`ALIYUN_ACCESS_KEY_ID`、`ALIYUN_ACCESS_KEY_SECRET`、`ALIYUN_OSS_ENDPOINT`、`ALIYUN_OSS_BUCKET`、`ALIYUN_CDN_DOMAIN`。OSS 同步需要对象读写权限，CDN 刷新需要 `cdn:RefreshObjectCaches` 权限。

## 本地校验

发布前在本地执行 `pnpm check:ci`、`pnpm build`、`pnpm verify:build`，然后可用 `pnpm preview` 打开 `http://localhost:4173/` 检查产物，包括 `/sitemap.xml` 和 `/robots.txt`。
