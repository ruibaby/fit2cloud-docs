import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";

const root = path.resolve("build");
const walk = async (directory) =>
  (
    await Promise.all(
      (await readdir(directory, { withFileTypes: true })).map((entry) =>
        entry.isDirectory()
          ? walk(path.join(directory, entry.name))
          : path.join(directory, entry.name),
      ),
    )
  ).flat();
const files = (await walk(root)).filter((file) => file.endsWith(".html"));
const cache = new Map();
async function exists(url) {
  const pathname = decodeURIComponent(url.pathname);
  if (!cache.has(pathname)) {
    const file = path.join(root, pathname);
    cache.set(
      pathname,
      Promise.all(
        [file, `${file}.html`, path.join(file, "index.html")].map((candidate) =>
          stat(candidate)
            .then((s) => s.isFile())
            .catch(() => false),
        ),
      ).then((results) => results.some(Boolean)),
    );
  }
  return cache.get(pathname);
}
const failures = new Map();
for (const file of files) {
  const html = await readFile(file, "utf8");
  for (const match of html.matchAll(/\b(?:href|src)="([^"]+)"/g)) {
    const ref = match[1].replaceAll("&amp;", "&");
    if (
      !ref ||
      ref.startsWith("#") ||
      /^(?:data:|mailto:|tel:|javascript:)/.test(ref)
    )
      continue;
    const url = new URL(ref, `http://docs.local/${path.relative(root, file)}`);
    if (url.origin !== "http://docs.local" || (await exists(url))) continue;
    if (!failures.has(url.pathname))
      failures.set(url.pathname, path.relative(root, file));
  }
}
console.log(`Checked ${files.length} HTML pages and ${cache.size} local URLs.`);
if (failures.size) {
  for (const [url, file] of failures) console.error(`${file}: ${url}`);
  process.exitCode = 1;
} else
  console.log("All local page, script, stylesheet and image URLs resolve.");
