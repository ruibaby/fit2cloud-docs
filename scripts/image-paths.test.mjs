import assert from "node:assert/strict";
import { test } from "node:test";
import { scopeImagePaths } from "./image-paths.mjs";

test("scope literal MDX images while leaving Markdown and other URLs alone", () => {
  const source = `<img\n src="/img/demo.png" alt="demo" />
<img src='/img/截图.png?size=2#preview' />
![demo](/img/demo.png)
<img src="/halo/img/demo.png" />
<img src="https://example.com/img/demo.png" />
<img src="./demo.png" />`;
  const result = scopeImagePaths(source, "halo");
  assert.equal(
    result,
    `<img\n src={"/halo/img/demo.png"} alt="demo" />
<img src={"/halo/img/截图.png?size=2#preview"} />
![demo](/img/demo.png)
<img src={"/halo/img/demo.png"} />
<img src="https://example.com/img/demo.png" />
<img src="./demo.png" />`,
  );
  assert.equal(scopeImagePaths(result, "halo"), result);
});

test("preserve image examples in code fences and inline code", () => {
  const source =
    '```html\n<img src="/img/example.png" />\n```\n\n~~~mdx\n<img src="/img/example.png" />\n~~~\n\n`<img src="/img/example.png" />`\n';
  assert.equal(scopeImagePaths(source, "halo"), source);
});
