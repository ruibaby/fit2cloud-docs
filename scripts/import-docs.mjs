import { cp, mkdir, readFile, writeFile, readdir } from "node:fs/promises";
import path from "node:path";
import { scopeImagePaths } from "./image-paths.mjs";
import { pathToFileURL } from "node:url";
import { execFileSync } from "node:child_process";

const source = path.resolve(process.argv[2] || "");
if (!process.argv[2])
  throw new Error("Usage: pnpm import:docs /path/to/fit2cloud-docs");
const projects = JSON.parse(await readFile("portal/projects.json", "utf8"));
const titleOf = (text, fallback) =>
  text.match(/^title:\s*["']?(.+?)["']?\s*$/m)?.[1] ||
  text.match(/^# (.+)$/m)?.[1] ||
  fallback;
const walk = async (root) =>
  (
    await Promise.all(
      (await readdir(root, { withFileTypes: true }))
        .filter((e) => !e.name.startsWith(".") && e.name !== "static")
        .map(async (e) =>
          e.isDirectory()
            ? walk(path.join(root, e.name))
            : path.join(root, e.name),
        ),
    )
  ).flat();
const counts = {};
for (const project of projects.filter(
  (p) => p.id !== "metersphere" && p.id !== "halo",
)) {
  const dest = path.resolve("content", project.id);
  await mkdir(dest, { recursive: true });
  const sidebars = {};
  const titles = {};
  for (const [index, version] of project.versions.entries()) {
    const origin = path.join(
      source,
      index === 0
        ? `${project.id}-docs`
        : `${project.id}_versioned_docs/version-${version}`,
    );
    const output = path.join(dest, version, "zh");
    await mkdir(output, { recursive: true });
    for (const file of await walk(origin)) {
      if (!/\.mdx?$/.test(file)) continue;
      const relative = path.relative(origin, file);
      if (index === 0 && relative === "product_landing.md") continue;
      if (relative.split(path.sep).some((s) => s.startsWith("."))) continue;
      let text = await readFile(file, "utf8");
      // Rspress expects closing callout fences to end their own paragraph.
      text = text.replace(/^(:{3,})[ \t]*$/gm, "\n$1\n");
      // Docusaurus compiles .md as MDX; use explicit MDX extensions in Rspress.
      text = text.replace(
        /(\]\([^\s)]*|(?:from|import)\s*["'][^"']*)\.md(?=[#)"'])/g,
        "$1.mdx",
      );
      text = text.replace(
        /\[([^\]]+)\]\((\/(?:1panel|ai-gateway|jumpserver|maxkb|dataease|sqlbot|halo|cordys)\/[^\s)]*)\)/g,
        '<a data-portal-link href="$2">$1</a>',
      );
      text = text.replace(
        /^([ \t]*```)(mysql|pgsql|env|node)(?=\s|$)/gm,
        (_, fence, lang) =>
          fence +
          { env: "dotenv", node: "bash", mysql: "sql", pgsql: "sql" }[lang],
      );
      // Rspress checks local filenames before URL decoding.
      text = text.replace(
        /(!\[[^\]]*\]\()((?:[^\s()]|\([^()\n]*\))+)(\))/g,
        (_, start, url, end) => `${start}<${decodeURI(url)}>${end}`,
      );
      text = text.replace(
        /(src=["'])(\/[^"']+)(["'])/g,
        (_, start, url, end) => `${start}${decodeURI(url)}${end}`,
      );
      const target = path.join(
        output,
        index === 0 && relative === "index.md"
          ? "product-intro.mdx"
          : relative.replace(/\.md$/, ".mdx"),
      );
      await mkdir(path.dirname(target), { recursive: true });
      await writeFile(target, scopeImagePaths(text, project.id));
      titles[`${version}/${relative.replace(/\.mdx?$/, "")}`] = titleOf(
        text,
        path.basename(file, path.extname(file)),
      );
      counts[project.id] = (counts[project.id] || 0) + 1;
    }
    await cp(path.join(origin, "static"), path.join(dest, "public"), {
      recursive: true,
      force: false,
      errorOnExist: false,
    }).catch((e) => {
      if (e.code !== "ENOENT") throw e;
    });
    const sidebarFile =
      index === 0
        ? path.join(origin, "sidebars.js")
        : path.join(
            source,
            `${project.id}_versioned_sidebars/version-${version}-sidebars.json`,
          );
    const raw = sidebarFile.endsWith(".json")
      ? JSON.parse(await readFile(sidebarFile, "utf8"))
      : (await import(pathToFileURL(sidebarFile))).default;
    sidebars[version] = Object.values(raw).flat();
  }
  await writeFile(
    path.join(dest, "sidebars.json"),
    JSON.stringify(sidebars, null, 2) + "\n",
  );
  await writeFile(
    path.join(dest, "titles.json"),
    JSON.stringify(titles, null, 2) + "\n",
  );
}
await writeFile(
  "content/source.json",
  JSON.stringify(
    {
      repository: "fit2cloud-docs",
      commit: execFileSync("git", ["-C", source, "rev-parse", "HEAD"], {
        encoding: "utf8",
      }).trim(),
      documents: counts,
    },
    null,
    2,
  ) + "\n",
);
console.log(counts);
execFileSync(process.execPath, ["scripts/import-homepages.mjs", source], {
  stdio: "inherit",
});
