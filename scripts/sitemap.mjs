import { readdir, writeFile } from "node:fs/promises";
import path from "node:path";

const root = path.resolve("build");
const origin = "https://docs.fit2cloud.com";
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

// One sitemap for the whole site: the portal, every product and every version
// are separate builds, so collect the pages from the merged output directory.
export async function generateSitemap() {
  const files = (await walk(root)).filter(
    (file) => file.endsWith(".html") && path.basename(file) !== "404.html",
  );
  const urls = new Set();
  for (const file of files) {
    const relative = path.relative(root, file).split(path.sep).join("/");
    const pathname =
      relative === "index.html"
        ? "/"
        : relative.endsWith("/index.html")
          ? `/${relative.slice(0, -"index.html".length)}`
          : `/${relative.slice(0, -".html".length)}`;
    urls.add(origin + encodeURI(pathname));
  }
  const entries = [...urls]
    .sort()
    .map((url) => `  <url><loc>${url.replaceAll("&", "&amp;")}</loc></url>`);
  await writeFile(
    path.join(root, "sitemap.xml"),
    [
      '<?xml version="1.0" encoding="UTF-8"?>',
      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
      ...entries,
      "</urlset>",
      "",
    ].join("\n"),
  );
  return entries.length;
}
