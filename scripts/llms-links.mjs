import { readFile, readdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";

const root = path.resolve("build");
const origin = "https://docs.fit2cloud.com/";
const walk = async (directory) =>
  (
    await Promise.all(
      (await readdir(directory, { withFileTypes: true })).map((entry) =>
        entry.isDirectory()
          ? walk(path.join(directory, entry.name))
          : [path.join(directory, entry.name)],
      ),
    )
  ).flat();

// Rspress links index pages as `/page.md`, but emits them at `page/index.md`.
const isFile = (file) =>
  stat(file)
    .then((s) => s.isFile())
    .catch(() => false);

export async function fixLlmsLinks() {
  let count = 0;
  for (const file of (await walk(root)).filter((file) =>
    /^llms.*\.txt$/.test(path.basename(file)),
  )) {
    let text = await readFile(file, "utf8");
    const replacements = [];
    for (const match of text.matchAll(
      new RegExp(`${origin}[^\\s)\\]>"']*\\.md`, "g"),
    )) {
      const url = match[0];
      const page = decodeURIComponent(url.slice(origin.length, -".md".length));
      if (
        (await isFile(path.join(root, page + ".md"))) ||
        !(await isFile(path.join(root, page, "index.md")))
      )
        continue;
      replacements.push([url, `${origin}${page}/index.md`]);
    }
    for (const [from, to] of replacements) text = text.replaceAll(from, to);
    if (replacements.length) {
      await writeFile(file, text);
      count += replacements.length;
    }
  }
  return count;
}
