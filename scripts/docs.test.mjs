import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import {
  cp,
  mkdir,
  mkdtemp,
  readFile,
  realpath,
  rm,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";

// Exercise the real CLI orchestration with a lightweight child process instead of Rspress.
async function fixture(t, { ci = "", fail = "", project } = {}) {
  const root = await realpath(
    await mkdtemp(path.join(os.tmpdir(), "docs-build-test-")),
  );
  t.after(() => rm(root, { recursive: true, force: true }));
  for (const dir of [
    "scripts",
    "portal/public",
    "node_modules/rstack/bin",
    "build/keep",
  ])
    await mkdir(path.join(root, dir), { recursive: true });
  await cp(
    new URL("./docs.mjs", import.meta.url),
    path.join(root, "scripts/docs.mjs"),
  );
  await cp(
    new URL("./sitemap.mjs", import.meta.url),
    path.join(root, "scripts/sitemap.mjs"),
  );
  await writeFile(path.join(root, "package.json"), '{"type":"module"}');
  await writeFile(path.join(root, "build/keep/marker"), "keep");
  await mkdir(path.join(root, "build/a"), { recursive: true });
  await writeFile(path.join(root, "build/a/stale.html"), "stale");
  await writeFile(path.join(root, "rstack.config.ts"), "");
  await writeFile(path.join(root, "portal/public/shared.txt"), "shared");
  const ids = ["a", "b", "c", "d", "e", "f"];
  await writeFile(
    path.join(root, "portal/projects.json"),
    JSON.stringify(ids.map((id) => ({ id }))),
  );
  for (const id of ids) {
    await mkdir(path.join(root, "content", id, "public"), { recursive: true });
    await writeFile(path.join(root, "content", id, "public", "merged.txt"), id);
  }
  await writeFile(
    path.join(root, "scripts/search-index.mjs"),
    "export async function generateSearchIndex() {}\n",
  );
  await writeFile(
    path.join(root, "node_modules/rstack/bin/rs.js"),
    `
import { appendFileSync, cpSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
const root = path.resolve(process.cwd(), "../..");
const id = process.env.DOCS_PROJECT;
const event = (type) => appendFileSync(path.join(root, "events.jsonl"), JSON.stringify({id,type,cwd:process.cwd(),args:process.argv.slice(2)}) + "\\n");
event("start");
process.on("SIGTERM", () => { event("cancel"); process.exit(143); });
setTimeout(() => {
  if (id === process.env.FAIL_PROJECT) { event("fail"); process.exit(1); }
  const out = path.join(root, "build", id === "portal" ? "" : id);
  mkdirSync(out, { recursive: true });
  writeFileSync(path.join(out, "index.html"), id);
  if (id !== "portal") cpSync(path.join(root, "content", id, "public"), out, { recursive: true });
  event("end");
}, id === "portal" ? 20 : id === process.env.FAIL_PROJECT ? 100 : 500);
`,
  );
  const child = spawn(
    process.execPath,
    [
      path.join(root, "scripts/docs.mjs"),
      "build",
      ...(project ? ["--project", project] : []),
    ],
    {
      cwd: root,
      env: { ...process.env, CI: ci, FAIL_PROJECT: fail },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  let output = "";
  child.stdout.on("data", (data) => {
    output += data;
  });
  child.stderr.on("data", (data) => {
    output += data;
  });
  const code = await new Promise((resolve, reject) => {
    child.once("error", reject);
    child.once("close", resolve);
  });
  const events = (await readFile(path.join(root, "events.jsonl"), "utf8"))
    .trim()
    .split("\n")
    .map((line) => JSON.parse(line));
  return { root, events, code, output };
}

for (const [ci, expected] of [
  ["", 4],
  ["true", 2],
]) {
  test(`builds with ${expected} concurrent products (CI=${ci})`, async (t) => {
    const { root, events, code, output } = await fixture(t, { ci });
    assert.equal(code, 0, output);
    assert.deepEqual(
      events.slice(0, 2).map(({ id, type }) => [id, type]),
      [
        ["portal", "start"],
        ["portal", "end"],
      ],
    );
    let active = 0;
    let peak = 0;
    for (const event of events.filter(({ id }) => id !== "portal")) {
      active += event.type === "start" ? 1 : -1;
      peak = Math.max(peak, active);
      assert.equal(event.cwd, path.join(root, ".site-work", event.id));
      assert.deepEqual(event.args, [
        "doc",
        "build",
        "--config",
        path.join(root, "rstack.config.ts"),
      ]);
    }
    assert.equal(peak, expected);
    assert.equal(active, 0);
    assert.equal(
      await readFile(path.join(root, "build/shared.txt"), "utf8"),
      "shared",
    );
    for (const id of ["a", "b", "c", "d", "e", "f"]) {
      assert.equal(
        await readFile(path.join(root, "build", id, "merged.txt"), "utf8"),
        id,
      );
      await assert.rejects(
        readFile(path.join(root, "build", id, "shared.txt")),
        { code: "ENOENT" },
      );
    }
    await assert.rejects(readFile(path.join(root, "build/merged.txt")), {
      code: "ENOENT",
    });
    await assert.rejects(readFile(path.join(root, "build/keep/marker")), {
      code: "ENOENT",
    });
    const sitemap = await readFile(
      path.join(root, "build/sitemap.xml"),
      "utf8",
    );
    for (const id of ["a", "b", "c", "d", "e", "f"])
      assert.ok(sitemap.includes(`https://docs.fit2cloud.com/${id}/`));
  });
}

test("failed child cancels active jobs, stops queued jobs and skips shared assets", async (t) => {
  const { root, events, code } = await fixture(t, { ci: "true", fail: "a" });
  assert.notEqual(code, 0);
  assert.deepEqual(
    events
      .filter(({ type }) => type === "start")
      .map(({ id }) => id)
      .sort(),
    ["a", "b", "portal"],
  );
  assert.ok(events.some(({ id, type }) => id === "b" && type === "cancel"));
  await assert.rejects(readFile(path.join(root, "build/shared.txt")), {
    code: "ENOENT",
  });
});

for (const project of ["portal", "a"]) {
  test(`single ${project} build preserves other output`, async (t) => {
    const { root, events, code, output } = await fixture(t, { project });
    assert.equal(code, 0, output);
    assert.deepEqual(
      events.filter(({ type }) => type === "start").map(({ id }) => id),
      [project],
    );
    assert.equal(
      await readFile(path.join(root, "build/keep/marker"), "utf8"),
      "keep",
    );
    assert.equal(
      await readFile(path.join(root, "build/shared.txt"), "utf8"),
      "shared",
    );
    await assert.rejects(readFile(path.join(root, "build/merged.txt")), {
      code: "ENOENT",
    });
    if (project === "a")
      await assert.rejects(readFile(path.join(root, "build/a/stale.html")), {
        code: "ENOENT",
      });
    else
      assert.equal(
        await readFile(path.join(root, "build/a/stale.html"), "utf8"),
        "stale",
      );
  });
}
