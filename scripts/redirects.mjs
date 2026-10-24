import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const root = path.resolve("build");
const origin = "https://docs.fit2cloud.com";

// Docusaurus used these frontmatter slugs, so old public URLs did not match
// the file names Rspress routes by. Keep the published links working.
const redirects = {
  "/ai-gateway/ai-gateway/integrate-third-party":
    "/ai-gateway/integrate_third_party",
  "/ai-gateway/user_manual/ai_gateway/call_logs":
    "/ai-gateway/admin-user-manual/call-logs",
  "/ai-gateway/user_manual/ai_gateway/tasks":
    "/ai-gateway/admin-user-manual/tasks",
  "/ai-gateway/user_manual/ai_gateway/system_settings":
    "/ai-gateway/admin-user-manual/system_settings",
  "/ai-gateway/user_manual/ai_gateway/settings":
    "/ai-gateway/admin-user-manual/settings",
  "/ai-gateway/admin/ai_gateway/usage_statistics":
    "/ai-gateway/admin-user-manual/usage-statistics",
};

export async function generateRedirects(project) {
  let count = 0;
  for (const [from, to] of Object.entries(redirects)) {
    if (project && !from.startsWith(`/${project}/`)) continue;
    const target = path.join(root, from, "index.html");
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(
      target,
      [
        "<!doctype html>",
        '<html lang="zh">',
        "<head>",
        '<meta charset="utf-8">',
        `<title>${to}</title>`,
        `<link rel="canonical" href="${origin}${to}">`,
        `<meta http-equiv="refresh" content="0; url=${to}">`,
        "<script>location.replace(" +
          JSON.stringify(to) +
          " + location.search + location.hash)</script>",
        "</head>",
        `<body><a href="${to}">${to}</a></body>`,
        "</html>",
        "",
      ].join("\n"),
    );
    count++;
  }
  return count;
}
