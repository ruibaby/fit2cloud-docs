import { cp, mkdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { scopeImagePaths } from "./image-paths.mjs";

const source = process.argv[2];
if (!source)
  throw new Error("Usage: pnpm import:homepages /path/to/fit2cloud-docs");
const projects = JSON.parse(await readFile("portal/projects.json", "utf8"));
const json = async (file, value) =>
  writeFile(file, JSON.stringify(value, null, 2) + "\n");
const variables = {
  "--ifm-background-surface-color": "--rp-c-bg",
  "--ifm-color-primary": "--rp-c-brand",
  "--ifm-color-content": "--rp-c-text-1",
  "--ifm-color-emphasis-900": "--rp-c-text-1",
  "--ifm-color-emphasis-800": "--rp-c-text-2",
  "--ifm-color-emphasis-700": "--rp-c-text-2",
  "--ifm-color-emphasis-600": "--rp-c-text-2",
  "--ifm-color-emphasis-200": "--rp-c-divider-light",
};
// Docusaurus slugs differ from the existing filename-based Rspress routes.
const aliases = {
  "ai-gateway": {
    "admin/ai_gateway/usage_statistics": "admin-user-manual/usage-statistics",
    "ai-gateway/integrate-third-party": "integrate_third_party",
    "user_manual/ai_gateway/call_logs": "admin-user-manual/call-logs",
    "user_manual/ai_gateway/settings": "admin-user-manual/settings",
    "user_manual/ai_gateway/system_settings":
      "admin-user-manual/system_settings",
  },
};

for (const project of projects.filter((p) => p.href.startsWith("/"))) {
  const { id } = project;
  const version = project.versions[0];
  const origin = path.join(source, `${id}-docs`);
  const dest = `content/${id}/${version}/zh`;
  const publicDir = `content/${id}/public`;
  const intro = path.join(dest, "product-intro.mdx");
  if (!existsSync(intro)) await cp(path.join(dest, "index.mdx"), intro);

  // Only these two new documents are needed by the updated landing page.
  if (id === "ai-gateway") {
    for (const name of ["offline_installation", "cli"]) {
      const text = (
        await readFile(path.join(origin, `installation/${name}.md`), "utf8")
      )
        .replace(/^(:{3,})[ \t]*$/gm, "\n$1\n")
        .replace(/\.md(?=[#)])/g, ".mdx");
      await writeFile(
        path.join(dest, `installation/${name}.mdx`),
        scopeImagePaths(text, id),
      );
      for (const [, asset] of text.matchAll(/src="(\/img\/[^"]+)"/g)) {
        await mkdir(path.dirname(path.join(publicDir, asset)), {
          recursive: true,
        });
        await cp(
          path.join(origin, "static", asset),
          path.join(publicDir, asset),
        );
      }
    }
  }

  let text = await readFile(path.join(origin, "product_landing.md"), "utf8");
  const title = text.match(/^title: (.+)$/m)[1];
  const description = text.match(/^description: (.+)$/m)[1];
  text = text
    .replace(
      /^---[\s\S]*?---/,
      `---\ntitle: ${title}\ndescription: ${description}\nfooter: false\n---`,
    )
    .replace(
      "import Link from '@docusaurus/Link';",
      "import { Link } from '@rspress/core/theme';",
    )
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
    .replace(
      /className=\{styles.videoCoverLogo\}/g,
      "className={`${styles.videoCoverLogo} no-zoom`}",
    )
    .replace(/<h1 className=\{styles.heroTitle\}>([^<]+)<\/h1>/, "")
    .replace(/\bto="([^"]+)"/g, (_, href) => {
      if (!href.startsWith(`/${id}/`)) return `href="${href}"`;
      const [pathname, hash] = href.slice(id.length + 2).split("#");
      let route = pathname.replace(/\/$/, "");
      route = aliases[id]?.[route] || route;
      const exists = (value) =>
        [".md", ".mdx", "/index.md", "/index.mdx"].some((suffix) =>
          existsSync(path.join(dest, value + suffix)),
        );
      if (route && !exists(route)) route += `/${path.basename(route)}`;
      if (route && !exists(route))
        throw new Error(`Missing landing link: ${id}/${route}`);
      return `href="/${route}${hash ? `#${hash}` : ""}"`;
    });
  for (const [, asset] of text.matchAll(/src="(\/img\/[^"]+)"/g)) {
    await mkdir(path.dirname(path.join(publicDir, asset)), { recursive: true });
    await cp(path.join(origin, "static", asset), path.join(publicDir, asset));
  }
  const start = text.indexOf("<div className={styles.hero}>");
  text =
    text.slice(0, start) +
    `# ${title}\n\n` +
    "<div className={`${styles.landing} rp-not-doc`}>\n" +
    text.slice(start) +
    "\n</div>\n";
  await writeFile(
    path.join(dest, "index.mdx"),
    scopeImagePaths(text, id)
      .replace(/[ \t]+$/gm, "")
      .replace(/\n{3,}/g, "\n\n"),
  );
  let css = await readFile(
    path.join(origin, "product_landing.module.css"),
    "utf8",
  );
  css = css
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/--ifm-[\w-]+/g, (name) => variables[name] || name)
    .replace(/\.heroTitle/g, ":global(.rp-doc):has(.landing) > h1")
    .replace(
      /repeat\(4, minmax\(0, 1fr\)\)/g,
      "repeat(auto-fill, minmax(min(160px, 100%), 1fr))",
    );
  css += `
/* Keep the imported design scoped to this page, including native heading UI. */
.landing { font-size: 14px; line-height: 1.75; }
/* The Markdown title stays at the root so Rspress detects it without a fallback. */
:global(.rp-doc):has(.landing) > :global(.rp-llms-container) { display: none; }
:global(.rp-doc):has(.landing) > h1 { letter-spacing: normal; }
:global(.rp-doc):has(.landing) > h1 a[href^='#'] { display: none; }
@media (min-width: 1280px) {
  :global(.rp-doc-layout__doc):has(.landing) { --rp-content-padding-x: 40px; }
}
@media (max-width: 996px) { .videoCard { margin-top: 24px; } }
`;
  await writeFile(path.join(dest, "product_landing.module.css"), css);

  if (id !== "halo") {
    const sidebarFile = `content/${id}/sidebars.json`;
    const sidebars = JSON.parse(await readFile(sidebarFile, "utf8"));
    // Preserve existing interior ordering and historical version sidebars.
    sidebars[version] = sidebars[version].filter(
      (item) =>
        item.id !== "product_landing" &&
        !(item.id === "index" && item.label === "概览"),
    );
    for (const item of sidebars[version])
      if (item.id === "index") item.id = "product-intro";
    sidebars[version].unshift({ type: "doc", id: "index", label: "概览" });
    if (id === "ai-gateway") {
      const items = sidebars[version].find(
        (item) => item.label === "安装部署",
      ).items;
      for (const [name, label] of [
        ["offline_installation", "离线安装"],
        ["cli", "1gctl 命令行工具"],
      ]) {
        if (!items.some((item) => item.id === `installation/${name}`))
          items.push({ type: "doc", id: `installation/${name}`, label });
      }
    }
    await json(sidebarFile, sidebars);
    const titlesFile = `content/${id}/titles.json`;
    const titles = JSON.parse(await readFile(titlesFile, "utf8"));
    titles[`${version}/product-intro`] = "产品介绍";
    titles[`${version}/index`] = title;
    await json(titlesFile, titles);
  }
  console.log(`Synced ${id} ${version} homepage`);
}
await json("content/homepages-source.json", {
  repository: "fit2cloud-docs",
  commit: execFileSync("git", ["-C", source, "rev-parse", "HEAD"], {
    encoding: "utf8",
  }).trim(),
  scope:
    "Current product landing pages, CSS and video covers; AI Gateway offline installation and CLI dependencies",
});
