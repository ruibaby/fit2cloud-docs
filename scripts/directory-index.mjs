import { mkdir, readdir, rename, rm } from "node:fs/promises";
import path from "node:path";

const root = path.resolve("build");
const walk = async (directory, skip = [], depth = 0) =>
  (
    await Promise.all(
      (await readdir(directory, { withFileTypes: true })).flatMap((entry) => {
        // A portal-only build must not rewrite product output.
        if (depth === 0 && skip.includes(entry.name)) return [];
        const target = path.join(directory, entry.name);
        return entry.isDirectory() ? walk(target, skip, depth + 1) : [target];
      }),
    )
  ).flat();

// Rspress writes flat `page.html` files while clean URLs link to `/page`.
// Aliyun OSS only serves `/page` and legacy `/page/` links from `page/index.html`,
// so move every page into a directory index before deployment.
export async function createDirectoryIndexes(directory = root, skip = []) {
  let count = 0;
  for (const file of await walk(directory, skip)) {
    const name = path.basename(file);
    if (!file.endsWith(".html") || name === "index.html" || name === "404.html")
      continue;
    const target = path.join(
      path.dirname(file),
      name.slice(0, -".html".length),
      "index.html",
    );
    await mkdir(path.dirname(target), { recursive: true });
    // A repeated build can leave the previous directory index behind.
    await rm(target, { force: true });
    await rename(file, target);
    count++;
  }
  return count;
}
