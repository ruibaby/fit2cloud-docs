# Repository Guidelines

## Project Structure & Module Organization

This repository builds the whole fit2cloud documentation site with Rspress 2. Every product is an independent Rspress build (own `base`, version list and locales) that outputs into `build/<product>/`; the portal is built separately into the root of `build/`.

- `content/<product>/<version>/<lang>/`: documentation sources. Historical versions live next to the current one, e.g. `content/1panel/v1/zh/`.
- `content/<product>/sidebars.json`: sidebar tree per version (`sidebars.<lang>.json` for translations).
- `content/<product>/titles.json`: sidebar labels keyed by `<version>/<doc id>`.
- `content/<product>/public/`: product images and other static assets.
- `content/halo/`: imported from [halo-dev/docs](https://github.com/halo-dev/docs); navigation uses its own `_nav.json` / `_meta.json`.
- `portal/projects.json`: product registry (order, versions, locales, logo, website).
- `portal/pages/`, `portal/shared/`, `portal/docs-theme/`: portal home, shared header/search, and the docs theme override.
- `scripts/`: build/dev orchestration, import scripts, search index and build verification.
- `build/` is generated output; never edit it. `.site-work/` holds per-product build caches.

## Build, Test, and Development Commands

Use Node.js 24 and pnpm 12.4.2, as declared in `package.json`.

- `pnpm dev` starts the unified dev server at `http://localhost:3000/`: the portal starts first and each product starts on first visit.
- `pnpm dev --project <id>` starts only one product's dev server.
- `pnpm build` builds all sites into `build/` (concurrency 4, or 2 with `CI=true`) and checks dead links and images.
- `pnpm build --project <id>` rebuilds only that site.
- `pnpm preview` serves `build/`.
- `pnpm check` runs Rslint/Rsfmt with fixes; `pnpm check:ci` checks without writing.
- `pnpm typecheck` runs TypeScript; `node --test scripts/*.test.mjs` runs orchestration tests.
- `pnpm verify:build` checks every local href/src in emitted HTML.

Do not hand-edit `pnpm-lock.yaml`, `build/`, or `portal/public/search-index.json`.

## Content Conventions

- Product pages are Markdown; use MDX only when a page needs components.
- Images in Markdown use `/img/...` (Rspress prefixes the product base). Native MDX `<img>` uses a deployment-path expression such as `src={"/halo/img/..."}`; raw HTML in plain `.md` uses `src="/halo/img/..."`. `pnpm verify:build` enforces this.
- Halo directories and files prefixed with `_` are include partials: they produce no page, are inlined elsewhere, and must not be linked or deleted.
- Sidebar order comes from `content/<product>/sidebars.json`; labels fall back to `titles.json`, then the file name. Keep both in sync when adding pages.
- When adding a product, register it in `portal/projects.json` first; versions and locales there drive routing, the product switcher and per-version sidebars.
- Unrelated products' content is expected to stay as imported; change it only when it fails to compile.

## Coding Style & Naming Conventions

Rslint and Rsfmt are the source of truth for TypeScript, JavaScript, JSON and CSS. Use spaces, double quotes in JSON, and keep configuration in TypeScript. Prefer Rspress options and slots over custom CSS; the only custom visual layer is the portal home and shared header. Documentation files use lowercase kebab-case (`migrate-from-1.x.md`), except Halo files whose names and routes come from upstream.

## Testing Guidelines

There is no coverage threshold. `pnpm build` (dead links + images), `pnpm verify:build`, `pnpm typecheck` and `pnpm check:ci` are the required validation. For content or theme changes, open the affected pages with `pnpm dev` or `pnpm preview` and check navigation, version switching, code blocks, images and narrow viewports.

## Commit & Pull Request Guidelines

Write short imperative subjects, e.g. `Document offline installation`. Keep each pull request focused on one topic, explain the user-facing impact, link the relevant issue, and include screenshots for layout changes. Run `pnpm check:ci` and `pnpm build` before requesting review; avoid force-pushing after review begins.

## Automation

`.github/workflows/` regenerates changelogs (`auto-changelog*.yml`), appends community FAQs (`auto-community-faq.yml`), updates offline installer versions (`check-latest-version.yml`) and deploys to OSS (`deploy-oss.yml`). Their path mappings live in the matching scripts under `.github/scripts/`; update those when product/version directories change.
