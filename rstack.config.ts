import { define } from "rstack";
import { createSiteConfig } from "./portal/config.ts";

define.doc(() => createSiteConfig(process.env.DOCS_PROJECT));

define.lint(({ js, ts }) => [js.configs.recommended, ts.configs.recommended]);

define.fmt({
  singleQuote: false,
  ignorePatterns: [".agents", "content", "portal/public"],
});

define.staged({
  "*.{js,jsx,ts,tsx,mjs,cjs,mts,cts}": ["rs lint --fix", "rs fmt"],
  "*.{json,jsonc,md,mdx,css,scss,less,html,yml,yaml}": "rs fmt",
});
