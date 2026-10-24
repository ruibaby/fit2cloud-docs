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
// Docusaurus folds `<dir>/<dir>.md` onto the directory route; Rspress serves
// that route from `<dir>/index.mdx`.
const isCollapsed = (id) => {
  const parts = id.split("/");
  return parts.length > 1 && parts.at(-1) === parts.at(-2);
};
const collapseId = (id) =>
  isCollapsed(id) ? `${path.posix.dirname(id)}/index` : id;
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
  const versions = await Promise.all(
    project.versions.map(async (version, index) => {
      const origin = path.join(
        source,
        index === 0
          ? `${project.id}-docs`
          : `${project.id}_versioned_docs/version-${version}`,
      );
      const files = await walk(origin);
      return {
        version,
        index,
        origin,
        files,
        collapsed: new Set(
          files
            .map((file) => path.relative(origin, file).replace(/\.mdx?$/, ""))
            .filter(isCollapsed),
        ),
      };
    }),
  );
  const collapsedByVersion = new Map(
    versions.map(({ version, collapsed }) => [version, collapsed]),
  );
  for (const { version, index, origin, files, collapsed } of versions) {
    const output = path.join(dest, version, "zh");
    await mkdir(output, { recursive: true });
    const rewriteLink = (url, from) => {
      const [, target = "", suffix = ""] =
        url.match(/^([^#?]*)([#?].*)?$/) || [];
      if (!target || /^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(target)) return url;
      const ext = target.match(/\.mdx?$/)?.[0] || "";
      const stem = ext ? target.slice(0, -ext.length) : target;
      if (stem.startsWith("/")) {
        const parts = stem.slice(1).split("/");
        if (parts.shift() !== project.id) return url;
        const targetVersion = project.versions.includes(parts[0])
          ? parts.shift()
          : project.versions[0];
        if (parts[0] === "zh") parts.shift();
        const id = parts.join("/");
        if (!collapsedByVersion.get(targetVersion)?.has(id)) return url;
        return `${stem.slice(0, stem.length - id.length)}${path.posix.dirname(id)}/${suffix}`;
      }
      const id = path.posix.normalize(
        path.posix.join(path.posix.dirname(from), stem),
      );
      if (!collapsed.has(id)) return url;
      return `${path.posix.relative(
        path.posix.dirname(from),
        `${collapseId(id)}.mdx`,
      )}${suffix}`;
    };
    const collapseSidebar = (value) => {
      if (typeof value === "string")
        return collapsed.has(value) ? collapseId(value) : value;
      if (Array.isArray(value)) return value.map(collapseSidebar);
      if (!value || typeof value !== "object") return value;
      const next = { ...value };
      if (typeof next.id === "string" && collapsed.has(next.id))
        next.id = collapseId(next.id);
      if (typeof next.key === "string")
        next.key = next.key.replace(/(:)([^ ]+) @ /, (match, colon, id) =>
          collapsed.has(id) ? `${colon}${collapseId(id)} @ ` : match,
        );
      for (const [key, child] of Object.entries(next))
        if (key !== "id" && key !== "key") next[key] = collapseSidebar(child);
      return next;
    };
    for (const file of files) {
      if (!/\.mdx?$/.test(file)) continue;
      const relative = path.relative(origin, file);
      const relativeWithoutExt = relative.replace(/\.mdx?$/, "");
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
      text = text
        .replace(
          /(?<!!)\]\(([^)\s]+)\)/g,
          (_, url) => `](${rewriteLink(url, relativeWithoutExt)})`,
        )
        .replace(
          /(href=["'])([^"']+)(["'])/g,
          (_, start, url, end) =>
            `${start}${rewriteLink(url, relativeWithoutExt)}${end}`,
        );
      const docId =
        index === 0 && relative === "index.md"
          ? "product-intro"
          : collapseId(relativeWithoutExt);
      const target = path.join(output, `${docId}.mdx`);
      await mkdir(path.dirname(target), { recursive: true });
      await writeFile(target, scopeImagePaths(text, project.id));
      titles[`${version}/${docId}`] = titleOf(
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
    sidebars[version] = collapseSidebar(Object.values(raw).flat());
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
