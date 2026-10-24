import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import type { UserConfig, SidebarItem, SidebarGroup } from "@rspress/core";
import projects from "./projects.json" with { type: "json" };

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const siteOrigin = "https://docs.fit2cloud.com";
interface SourceItem {
  type?: string;
  id?: string;
  label?: string;
  href?: string;
  items?: (SourceItem | string)[];
  link?: { id?: string };
  className?: string;
}
export function projectSidebar(id: string) {
  const project = projects.find((p) => p.id === id)!;
  const source = JSON.parse(
    readFileSync(path.join(root, "content", id, "sidebars.json"), "utf8"),
  );
  const titles = JSON.parse(
    readFileSync(path.join(root, "content", id, "titles.json"), "utf8"),
  );
  const result: Record<string, (SidebarItem | SidebarGroup)[]> = {};
  for (const lang of project.locales) {
    const localizedFile = path.join(
      root,
      "content",
      id,
      `sidebars.${lang}.json`,
    );
    const localizedSource = existsSync(localizedFile)
      ? JSON.parse(readFileSync(localizedFile, "utf8"))
      : source;
    for (const [version, items] of Object.entries(localizedSource)) {
      const prefix = `${version === project.versions[0] ? "/" : `/${version}/`}${lang === "zh" ? "" : `${lang}/`}`;
      const link = (doc: string) => prefix + doc.replace(/(^|\/)index$/, "$1");
      const convert = (
        item: SourceItem | string,
        depth = 0,
      ): SidebarItem | SidebarGroup => {
        if (typeof item === "string") item = { type: "doc", id: item };
        const text =
          item.label ||
          titles[`${version}/${item.id}`] ||
          item.id?.split("/").at(-1) ||
          "";
        if (item.type === "category")
          return {
            text,
            ...(item.link?.id ? { link: link(item.link.id) } : {}),
            items: (item.items || []).map((i) => convert(i, depth + 1)),
            collapsed: depth > 0,
          };
        return {
          text,
          link: item.href || link(item.id || ""),
          ...(item.className?.endsWith("-rec") ? { tag: "推 荐" } : {}),
        };
      };
      result[prefix] = (items as SourceItem[]).map((i) => convert(i));
    }
  }
  return result;
}
export async function createSiteConfig(id = "portal"): Promise<UserConfig> {
  const project = projects.find((p) => p.id === id);
  if (id !== "portal" && (!project || id === "metersphere"))
    throw new Error(`Unknown docs project: ${id}`);
  const [
    { pluginSass },
    { default: mermaid },
    { default: fileTree },
    { default: Icons },
    { transformerCompatibleMetaHighlight },
    { transformerNotationDiff },
    { default: ga },
  ] = await Promise.all([
    import("@rsbuild/plugin-sass"),
    import("rspress-plugin-mermaid"),
    import("rspress-plugin-file-tree"),
    import("unplugin-icons/rspack"),
    import("@rspress/core/shiki-transformers"),
    import("@shikijs/transformers"),
    import("rspress-plugin-google-analytics"),
  ]);
  return {
    root: path.join(root, id === "portal" ? "portal/pages" : `content/${id}`),
    base: id === "portal" ? "/" : `/${id}/`,
    outDir: path.join(root, "build", id === "portal" ? "" : id),
    themeDir: path.join(
      root,
      id === "portal" ? "portal/theme" : "portal/docs-theme",
    ),
    ...(id === "halo"
      ? { globalStyles: path.join(root, "styles/index.scss") }
      : {}),
    lang: "zh",
    ...(project
      ? {
          locales: project.locales.map((lang) => ({
            lang,
            label: lang === "zh" ? "简体中文" : "English",
          })),
          multiVersion: {
            default: project.versions[0],
            versions: project.versions,
          },
        }
      : {}),
    title: project
      ? `${id === "halo" ? "Halo" : project.name} 文档`
      : "飞致云文档中心",
    ...(project
      ? {
          logoText: `${id === "halo" ? "Halo" : project.name} 文档`,
          logo:
            id === "halo"
              ? "https://www.halo.run/logo"
              : `/img/logo/${project.logo}`,
        }
      : {}),
    icon: pathToFileURL(
      path.join(
        root,
        id === "halo"
          ? "content/halo/public/img/favicon-96x96.png"
          : "portal/public/img/favicon.ico",
      ),
    ),
    siteOrigin,
    route: { cleanUrls: true },
    llms:
      id === "portal"
        ? {
            llmsTxt: ({ title, sections }) =>
              [
                `# ${title}`,
                "> 飞致云各项目文档的总入口。请先读取对应项目的 llms.txt，再按其中的索引查阅文档。",
                "## 项目文档索引",
                projects
                  .filter((item) => item.href.startsWith("/"))
                  .map(
                    (item) =>
                      `- [${item.name}](${siteOrigin}${item.href}llms.txt): ${item.desc}`,
                  )
                  .join("\n"),
                "## 外部项目文档",
                projects
                  .filter((item) => !item.href.startsWith("/"))
                  .map(
                    (item) =>
                      `- [${item.name}](${item.href}): ${item.desc}（外部文档站）`,
                  )
                  .join("\n"),
                ...sections.map(
                  (section) =>
                    `## ${section.title}\n\n${section.pages
                      .map(
                        (page) =>
                          `- [${page.title}](${page.link})${page.description ? `: ${page.description}` : ""}`,
                      )
                      .join("\n")}`,
                ),
              ].join("\n\n") + "\n",
          }
        : true,
    mediumZoom: { selector: ".rspress-doc img:not(.no-zoom)" },
    markdown: {
      showLineNumbers: id === "halo",
      link: { checkDeadLinks: true },
      image: { checkDeadImages: true },
      shiki: {
        theme: "github-dark",
        transformers:
          id === "halo"
            ? [transformerCompatibleMetaHighlight(), transformerNotationDiff()]
            : [],
      },
    },
    plugins: [mermaid(), fileTree(), ga({ id: "G-PRP2HJ49K6" })],
    builderConfig: {
      root: path.join(root, ".site-work", id),
      // 统一开发服务器按路径把 HMR 连接分发到各站点，避免全部落到门户。
      dev: {
        client: { path: `/${id}/rsbuild-hmr` },
      },
      performance: {
        buildCache: {
          cacheDirectory: path.join(root, ".site-work", id, "cache"),
          buildDependencies: [
            "rstack.config.ts",
            "portal/config.ts",
            "portal/projects.json",
            "package.json",
            "pnpm-lock.yaml",
            "tsconfig.json",
          ].map((file) => path.join(root, file)),
        },
      },
      server: {
        publicDir: [
          ...(project
            ? [{ name: path.join(root, "content", id, "public") }]
            : []),
          // Serve shared files in dev; the orchestrator copies them once to build/.
          { name: path.join(root, "portal/public"), copyOnBuild: false },
        ],
        setup: ({ server }) => {
          // Shared UI uses root URLs even in a standalone product dev server.
          server.middlewares.use((req, _res, next) => {
            if (
              id !== "portal" &&
              (req.url?.startsWith("/img/") ||
                req.url?.startsWith("/search-index.json"))
            )
              req.url = `/${id}${req.url}`;
            next();
          });
        },
      },
      plugins: [pluginSass()],
      source: {
        tsconfigPath: path.join(root, "tsconfig.json"),
        define: { __DOCS_PROJECT__: JSON.stringify(id) },
      },
      output: {
        // Only the build orchestrator cleans output; dev must preserve production files.
        cleanDistPath: false,
      },
      tools: {
        rspack: {
          plugins: [
            Icons({
              compiler: "jsx",
              jsx: "react",
              customCollections: {
                custom: {
                  "bt-panel": () =>
                    readFileSync(
                      path.join(root, "theme/images/bt-panel-logo.svg"),
                      "utf8",
                    ),
                },
              },
            }),
          ],
        },
      },
    },
    themeConfig:
      id === "portal"
        ? {
            darkMode: false,
            llmsUI: false,
            lastUpdated: false,
            hideNavbar: "always",
            nav: [],
            sidebar: {},
            enableScrollToTop: true,
          }
        : {
            // 与门户保持一致：全站使用浅色模式，不提供暗色切换。
            darkMode: "force-light",
            enableScrollToTop: true,
            ...(id === "halo"
              ? {
                  lastUpdated: true,
                  editLink: {
                    docRepoBaseUrl:
                      "https://github.com/fit2cloud-dev/fit2cloud-docs/tree/main/content/halo/v2/zh",
                  },
                  socialLinks: [
                    {
                      icon: "github",
                      mode: "link",
                      content: "https://github.com/halo-dev/halo",
                    },
                  ],
                }
              : {
                  lastUpdated: false,
                  nav: [{ text: "官网", link: project!.website }],
                  sidebar: projectSidebar(id),
                }),
          },
  };
}
