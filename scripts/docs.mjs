import { spawn } from "node:child_process";
import { cp, mkdir, readFile, stat, rm } from "node:fs/promises";
import path from "node:path";
import net from "node:net";
import http from "node:http";
import { createReadStream } from "node:fs";
import { fileURLToPath } from "node:url";
import { createDirectoryIndexes } from "./directory-index.mjs";
import { fixLlmsLinks } from "./llms-links.mjs";
import { generateSearchIndex } from "./search-index.mjs";
import { generateSitemap } from "./sitemap.mjs";
import { generateRedirects } from "./redirects.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
process.chdir(root);
const cli = path.join(root, "node_modules/rstack/bin/rs.js");
const projects = JSON.parse(await readFile("portal/projects.json", "utf8"));
const sites = ["portal", ...projects.map((p) => p.id)];
const command = process.argv[2] || "dev";
const option = (name) => process.argv[process.argv.indexOf(name) + 1];
const project = process.argv.includes("--project")
  ? option("--project")
  : undefined;
if (project && !sites.includes(project))
  throw new Error(`Unknown project: ${project}`);
const children = new Set();
let interrupted = false;
function stopChildren(signal = "SIGTERM") {
  for (const child of children) child.kill(signal);
}
for (const signal of command === "preview" ? [] : ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    interrupted = true;
    stopChildren(signal);
    process.exitCode = signal === "SIGINT" ? 130 : 143;
  });
}
async function run(args, id) {
  const cwd = path.join(root, ".site-work", id);
  await mkdir(cwd, { recursive: true });
  if (interrupted) throw new Error("Build interrupted");
  console.log(`[${id}] Starting ${args[0] || "dev"}`);
  await new Promise((resolve, reject) => {
    const child = spawn(
      process.execPath,
      [cli, "doc", ...args, "--config", path.join(root, "rstack.config.ts")],
      {
        cwd,
        stdio: "inherit",
        env: { ...process.env, DOCS_PROJECT: id },
      },
    );
    children.add(child);
    child.once("error", reject);
    child.once("close", (code, signal) => {
      children.delete(child);
      if (code === 0) resolve();
      else reject(new Error(`${id} exited with ${signal || code}`));
    });
  });
  console.log(`[${id}] Finished`);
}
async function build() {
  const concurrency = process.env.CI && process.env.CI !== "false" ? 2 : 4;
  console.log(`Build concurrency: ${concurrency}`);
  await generateSearchIndex();
  if (!project) await rm("build", { recursive: true, force: true });
  else if (project !== "portal")
    await rm(path.join("build", project), { recursive: true, force: true });
  // The portal owns build/; finish it before starting the product builds.
  if (!project || project === "portal") await run(["build"], "portal");
  const products = project
    ? project === "portal"
      ? []
      : [project]
    : sites.filter((id) => id !== "portal");
  const queue = [...products];
  let failure;
  await Promise.all(
    Array.from({ length: Math.min(concurrency, queue.length) }, async () => {
      while (queue.length && !failure && !interrupted) {
        try {
          await run(["build"], queue.shift());
        } catch (error) {
          failure ||= error;
          interrupted = true;
          stopChildren();
        }
      }
    }),
  );
  if (failure) throw failure;
  if (interrupted) throw new Error("Build interrupted");
  // Shared assets live at the root; Rspress emits each product's own public files.
  await cp("portal/public", "build", { recursive: true });
  const pageCount = await generateSitemap();
  console.log(`[sitemap] ${pageCount} URLs`);
  const directoryCount =
    project && project !== "portal"
      ? await createDirectoryIndexes(path.join(root, "build", project))
      : await createDirectoryIndexes(
          path.join(root, "build"),
          project === "portal" ? sites.filter((id) => id !== "portal") : [],
        );
  console.log(`[pages] ${directoryCount} directory indexes`);
  const redirectCount = await generateRedirects(project);
  console.log(`[redirects] ${redirectCount} pages`);
  const llmsCount = await fixLlmsLinks();
  console.log(`[llms] ${llmsCount} links fixed`);
}
// ---------------------------------------------------------------------------
// Development server
//
// Each product needs its own Rspress instance (independent versions and base
// paths). To keep `pnpm dev` a single, familiar entry point, the portal is
// started eagerly and product servers are started on first request, then
// proxied under the same origin. Only the products you actually open cost
// startup time and memory.
// ---------------------------------------------------------------------------
const projectIds = new Set(
  projects.filter((p) => p.href?.startsWith("/")).map((p) => p.id),
);
const devSites = new Map();

async function freePort() {
  const server = net.createServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  await new Promise((resolve) => server.close(resolve));
  return port;
}

async function waitForPort(port, id) {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    const reachable = await new Promise((resolve) => {
      const socket = net.connect(port, "127.0.0.1");
      socket.once("connect", () => {
        socket.destroy();
        resolve(true);
      });
      socket.once("error", () => resolve(false));
    });
    if (reachable) return;
    if (interrupted) throw new Error("Dev server interrupted");
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  throw new Error(`${id} dev server did not start within 120s`);
}

function startSiteDev(id) {
  if (devSites.has(id)) return devSites.get(id);
  const entry = { port: undefined, ready: undefined, child: undefined };
  entry.ready = (async () => {
    entry.port = await freePort();
    const cwd = path.join(root, ".site-work", id);
    await mkdir(cwd, { recursive: true });
    console.log(`[${id}] Starting dev server`);
    const child = spawn(
      process.execPath,
      [
        cli,
        "doc",
        "--port",
        String(entry.port),
        "--host",
        "127.0.0.1",
        "--config",
        path.join(root, "rstack.config.ts"),
      ],
      {
        cwd,
        stdio: ["ignore", "pipe", "pipe"],
        env: { ...process.env, DOCS_PROJECT: id },
      },
    );
    entry.child = child;
    children.add(child);
    child.stdout.on("data", (chunk) => process.stdout.write(chunk));
    child.stderr.on("data", (chunk) => process.stderr.write(chunk));
    child.once("close", (code, signal) => {
      children.delete(child);
      if (!interrupted && code !== 0)
        console.error(`[${id}] dev server exited (${signal || code})`);
    });
    await waitForPort(entry.port, id);
    console.log(
      `[${id}] Ready at http://localhost:${devServerPort}/${
        id === "portal" ? "" : `${id}/`
      }`,
    );
  })();
  devSites.set(id, entry);
  return entry;
}

// Root-level endpoints that every dev server serves itself (HMR, lazy
// compilation) arrive without a site prefix, so attribute them to the product
// of the page that issued the request.
function siteForRequest(req) {
  const segment = new URL(req.url, "http://localhost").pathname.split("/")[1];
  if (projectIds.has(segment)) return segment;
  const referer = req.headers.referer;
  if (referer && segment !== "") {
    try {
      const refSegment = new URL(referer).pathname.split("/")[1];
      if (projectIds.has(refSegment)) return refSegment;
    } catch {
      // ignore malformed referer
    }
  }
  return "portal";
}

let devServerPort = 3000;

async function dev(port) {
  devServerPort = port;
  await generateSearchIndex();
  if (project) {
    // Focused mode: keep the old behaviour of exposing just one product.
    await run(["--port", String(port)], project);
    return;
  }
  await startSiteDev("portal").ready;
  const server = http.createServer(async (req, res) => {
    try {
      const id = siteForRequest(req);
      const entry = startSiteDev(id);
      await entry.ready;
      proxyRequest(req, res, entry.port);
    } catch (error) {
      res.writeHead(502, { "Content-Type": "text/plain; charset=utf-8" });
      res.end(`文档服务启动失败: ${error.message}`);
    }
  });
  server.on("upgrade", async (req, socket, head) => {
    try {
      // Each site owns a base-prefixed HMR path (see builderConfig.dev.client),
      // so the request path alone tells us which dev server to use.
      const id = siteForRequest(req);
      const entry = startSiteDev(id);
      await entry.ready;
      proxyUpgrade(req, socket, head, entry.port);
    } catch {
      socket.destroy();
    }
  });
  server.listen(port, () => {
    console.log(`\nDocs center: http://localhost:${port}/`);
    console.log("Product docs start on first visit.\n");
  });
}

function proxyRequest(req, res, port) {
  const headers = { ...req.headers, host: `127.0.0.1:${port}` };
  const upstream = http.request(
    {
      host: "127.0.0.1",
      port,
      method: req.method,
      path: req.url,
      headers,
    },
    (response) => {
      res.writeHead(response.statusCode, response.headers);
      response.pipe(res);
    },
  );
  upstream.on("error", () => {
    if (!res.headersSent) res.writeHead(502, { "Content-Type": "text/plain" });
    res.end("Upstream dev server unavailable");
  });
  req.pipe(upstream);
}

function proxyUpgrade(req, socket, head, port) {
  const upstream = net.connect(port, "127.0.0.1", () => {
    const headers = [];
    for (let i = 0; i < req.rawHeaders.length; i += 2)
      headers.push(`${req.rawHeaders[i]}: ${req.rawHeaders[i + 1]}`);
    upstream.write(
      `${req.method} ${req.url} HTTP/1.1\r\n${headers.join("\r\n")}\r\n\r\n`,
    );
    if (head?.length) upstream.write(head);
    socket.pipe(upstream).pipe(socket);
  });
  upstream.on("error", () => socket.destroy());
  socket.on("error", () => upstream.destroy());
}

function preview(port = 4173) {
  const root = path.resolve("build");
  const mime = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".pdf": "application/pdf",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
  };
  const server = http.createServer(async (req, res) => {
    try {
      const requestUrl = new URL(req.url, "http://local");
      const pathname = decodeURIComponent(requestUrl.pathname);
      const requested = path.resolve(root, "." + pathname);
      if (requested !== root && !requested.startsWith(root + path.sep)) {
        res.writeHead(403);
        res.end();
        return;
      }
      let file;
      for (const candidate of [
        requested,
        path.join(requested, "index.html"),
        `${requested}.html`,
      ])
        if ((await stat(candidate).catch(() => null))?.isFile()) {
          file = candidate;
          break;
        }
      if (!file) {
        res.writeHead(404, { "Content-Type": "text/html; charset=utf-8" });
        res.end('<h1>页面不存在</h1><a href="/">返回文档中心</a>');
        return;
      }
      // Match OSS: a directory page requested without the trailing slash redirects.
      if (
        file === path.join(requested, "index.html") &&
        pathname !== "/" &&
        !pathname.endsWith("/")
      ) {
        res.writeHead(302, {
          Location: `${requestUrl.pathname}/${requestUrl.search}`,
        });
        res.end();
        return;
      }
      res.writeHead(200, {
        "Content-Type": mime[path.extname(file)] || "application/octet-stream",
      });
      createReadStream(file).pipe(res);
    } catch {
      res.writeHead(400);
      res.end("Bad request");
    }
  });
  server.listen(port, "127.0.0.1", () =>
    console.log(`Docs center: http://localhost:${port}`),
  );
}
if (command === "build") await build();
else if (command === "preview")
  preview(process.argv.includes("--port") ? Number(option("--port")) : 4173);
else if (command === "dev")
  await dev(process.argv.includes("--port") ? Number(option("--port")) : 3000);
else throw new Error(`Unknown command: ${command}`);
