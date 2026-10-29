import { readFile, writeFile, readdir } from "node:fs/promises";
import path from "node:path";
export async function generateSearchIndex() {
  const projects = JSON.parse(await readFile("portal/projects.json", "utf8"));
  const entries = [];
  const walk = async (root) =>
    (
      await Promise.all(
        (await readdir(root, { withFileTypes: true }))
          .filter(
            (e) =>
              !e.name.startsWith("_") &&
              !e.name.startsWith(".") &&
              e.name !== "public",
          )
          .map((e) =>
            e.isDirectory()
              ? walk(path.join(root, e.name))
              : path.join(root, e.name),
          ),
      )
    ).flat();
  for (const p of projects) {
    for (const [i, version] of p.versions.entries()) {
      for (const lang of p.locales) {
        const root = `content/${p.id}/${version}/${lang}`;
        const prefix = `/${p.id}/${i ? `${version}/` : ""}${lang === "zh" ? "" : `${lang}/`}`;
        for (const file of await walk(root)) {
          if (!/\.mdx?$/.test(file)) continue;
          const source = await readFile(file, "utf8");
          const title =
            source.match(/^title:\s*["']?(.+?)["']?\s*$/m)?.[1] ||
            source.match(/^# (.+)$/m)?.[1] ||
            path.basename(file).replace(/\.mdx?$/, "");
          const body = source
            .replace(/^---[\s\S]*?---/, "")
            .replace(/```[\s\S]*?```/g, "")
            .replace(/^import .*$/gm, "")
            .replace(/^\s*:::[^\n]*$/gm, "")
            .replace(/^\s*> ?/gm, "")
            .replace(/<[^>]+>/g, "")
            .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
            .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
            .replace(/[#*`|{}]/g, "")
            .replace(/\s+/g, " ")
            .trim();
          const description =
            source.match(/^description:\s*["']?(.+?)["']?\s*$/m)?.[1] ||
            body.slice(0, 240);
          entries.push({
            title,
            description,
            text: body,
            href:
              prefix +
              path
                .relative(root, file)
                .replace(/\.mdx?$/, "")
                .replace(/(^|\/)index$/, "$1"),
            project: p.name,
            version,
            lang,
            current: i === 0,
          });
        }
      }
    }
  }
  await writeFile("portal/public/search-index.json", JSON.stringify(entries));
  console.log(`Search index: ${entries.length} documents`);
}
