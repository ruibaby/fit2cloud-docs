import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation } from "@rspress/core/runtime";
import SearchIcon from "~icons/mingcute/search-line";
import FileIcon from "~icons/mingcute/file-line";
import ArrowLeft from "~icons/mingcute/arrow-left-line";
import { illustration } from "./data";
import styles from "./search-page.module.css";

interface SearchItem {
  title: string;
  description: string;
  text: string;
  href: string;
  project: string;
  version: string;
  current: boolean;
  lang: string;
}
let cached: Promise<SearchItem[]> | undefined;
function loadIndex() {
  return (cached ??= fetch("/search-index.json")
    .then((r) => {
      if (!r.ok) throw new Error("搜索索引加载失败");
      return r.json();
    })
    .catch((e) => {
      cached = undefined;
      throw e;
    }));
}
function search(items: SearchItem[], query: string, scope?: string) {
  const words = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  return items
    .filter((item) =>
      scope
        ? item.href.startsWith(scope) &&
          (scope.split("/").filter(Boolean).length > 1 || item.current)
        : item.current,
    )
    .filter((item) =>
      words.every((w) =>
        `${item.title} ${item.text} ${item.project}`
          .toLocaleLowerCase()
          .includes(w),
      ),
    )
    .sort(
      (a, b) =>
        Number(
          b.title.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
        ) -
        Number(a.title.toLocaleLowerCase().includes(query.toLocaleLowerCase())),
    );
}
function Highlight({ text, query }: { text: string; query: string }) {
  const terms = query
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!terms.length) return text;
  const expression = new RegExp(`(${terms.join("|")})`, "gi");
  return text
    .split(expression)
    .map((part, i) => (i % 2 ? <mark key={i}>{part}</mark> : part));
}
function searchUrl(query: string, scope?: string) {
  return `/search?${new URLSearchParams({ q: query.trim(), ...(scope ? { scope } : {}) })}`;
}
export function SearchBox({
  compact = false,
  initial = "",
  suggest = true,
  scope,
}: {
  compact?: boolean;
  initial?: string;
  suggest?: boolean;
  scope?: string;
}) {
  const [query, setQuery] = useState(initial);
  const [items, setItems] = useState<SearchItem[]>([]);
  const [status, setStatus] = useState("loading");
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState(-1);
  const [box, setBox] = useState<DOMRect | null>(null);
  const form = useRef<HTMLFormElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    setQuery(initial);
  }, [initial]);
  useEffect(() => {
    if (!open) return;
    let active = true;
    loadIndex()
      .then((data) => {
        if (active) {
          setItems(data);
          setStatus("ready");
        }
      })
      .catch(() => {
        if (active) setStatus("error");
      });
    const close = (event: MouseEvent) => {
      if (
        !form.current?.contains(event.target as Node) &&
        !panel.current?.contains(event.target as Node)
      )
        setOpen(false);
    };
    const position = () =>
      setBox(form.current?.getBoundingClientRect() || null);
    position();
    document.addEventListener("click", close);
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    return () => {
      active = false;
      document.removeEventListener("click", close);
      window.removeEventListener("resize", position);
      window.removeEventListener("scroll", position, true);
    };
  }, [open]);
  const hits = search(items, query, scope).slice(0, 5);
  return (
    <>
      <form
        ref={form}
        role="search"
        className={`portal-search ${compact ? "portal-search--compact" : ""}`}
        action="/search"
        onSubmit={(e) => {
          if (!query.trim()) e.preventDefault();
        }}
      >
        {scope && <input type="hidden" name="scope" value={scope} />}
        {compact && <SearchIcon aria-hidden="true" />}
        <input
          type="search"
          name="q"
          aria-label="搜索文档"
          placeholder={
            compact ? "搜索文档" : "请输入关键词回车检索，例如：1Panel 如何安装"
          }
          autoComplete="off"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setSelected(-1);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setOpen(false);
            if (e.key === "ArrowDown" || e.key === "ArrowUp") {
              e.preventDefault();
              setSelected((n) =>
                Math.max(
                  -1,
                  Math.min(
                    hits.length - 1,
                    n + (e.key === "ArrowDown" ? 1 : -1),
                  ),
                ),
              );
            }
            if (e.key === "Enter" && selected >= 0 && hits[selected]) {
              e.preventDefault();
              window.location.assign(hits[selected].href);
            }
          }}
        />
        {!compact && <button type="submit">搜索</button>}
      </form>
      {suggest &&
        open &&
        query.trim() &&
        box &&
        createPortal(
          <div
            ref={panel}
            className="portal-search-results"
            style={{
              top: box.bottom + 8,
              left: Math.min(
                box.left,
                window.innerWidth -
                  Math.min(compact ? 560 : box.width, window.innerWidth - 32) -
                  16,
              ),
              width: Math.min(
                compact ? 560 : box.width,
                window.innerWidth - 32,
              ),
            }}
          >
            {status !== "ready" ? (
              <p role="status">
                {status === "error"
                  ? "搜索暂时不可用，请稍后重试"
                  : "正在加载文档…"}
              </p>
            ) : hits.length ? (
              hits.map((item, i) => (
                <a
                  key={item.href}
                  href={item.href}
                  className={selected === i ? "selected" : ""}
                >
                  <FileIcon aria-hidden="true" />
                  <span>
                    <span className="portal-result-title">
                      <Highlight text={item.title} query={query} />
                      <small>{item.project}</small>
                    </span>
                    <span className="portal-result-desc">
                      <Highlight text={item.description} query={query} />
                    </span>
                  </span>
                </a>
              ))
            ) : (
              <p role="status">未找到相关文档，换个关键词试试</p>
            )}
            <a className="portal-search-all" href={searchUrl(query, scope)}>
              查看全部结果
            </a>
          </div>,
          document.body,
        )}
    </>
  );
}
export function SearchPage() {
  const location = useLocation();
  const query = new URLSearchParams(location.search).get("q") || "";
  const [items, setItems] = useState<SearchItem[]>([]);
  const [status, setStatus] = useState("loading");
  const [page, setPage] = useState(1);
  useEffect(() => {
    loadIndex()
      .then((data) => {
        setItems(data);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);
  useEffect(() => {
    setPage(1);
  }, [query]);
  const scope = new URLSearchParams(location.search).get("scope") || undefined;
  const hits = search(items, query, scope);
  const pages = Math.ceil(hits.length / 10);
  return (
    <main id="main-content" className={styles.page}>
      <div className={styles.container}>
        <div className={styles.heroBox}>
          <div className={styles.heroBody}>
            <button
              className={styles.quickBack}
              onClick={() =>
                window.history.length > 1
                  ? window.history.back()
                  : window.location.assign("/")
              }
            >
              <ArrowLeft />
              快速返回上一页
            </button>
            <h1 className={styles.heroTitle}>全部结果</h1>
            <div className={styles.searchWrap}>
              <SearchBox initial={query} suggest={false} scope={scope} />
            </div>
          </div>
          <img className={styles.heroIllu} src={illustration} alt="文档中心" />
        </div>
        <div className={styles.results} aria-live="polite">
          {hits.slice((page - 1) * 10, page * 10).map((item) => (
            <a key={item.href} href={item.href} className={styles.row}>
              <FileIcon className={styles.rowIcon} />
              <span className={styles.rowBody}>
                <span className={styles.rowTitleRow}>
                  <span className={styles.rowTitle}>
                    <Highlight text={item.title} query={query} />
                  </span>
                  <span className={styles.rowTag}>{item.project}</span>
                </span>
                <span className={styles.rowDesc}>
                  <Highlight text={item.description} query={query} />
                </span>
              </span>
            </a>
          ))}
          {!hits.length && (
            <p className={styles.empty}>
              {status === "loading"
                ? "正在加载文档…"
                : status === "error"
                  ? "搜索暂时不可用，请刷新重试"
                  : "未找到相关文档，换个关键词试试"}
            </p>
          )}
          {pages > 1 && (
            <nav className="portal-pagination" aria-label="搜索结果分页">
              <button disabled={page === 1} onClick={() => setPage(page - 1)}>
                上一页
              </button>
              {Array.from({ length: pages }, (_, i) => i + 1)
                .filter(
                  (n) => n === 1 || n === pages || Math.abs(n - page) <= 2,
                )
                .map((n) => (
                  <button
                    aria-current={n === page ? "page" : undefined}
                    key={n}
                    onClick={() => setPage(n)}
                  >
                    {n}
                  </button>
                ))}
              <button
                disabled={page === pages}
                onClick={() => setPage(page + 1)}
              >
                下一页
              </button>
            </nav>
          )}
        </div>
      </div>
    </main>
  );
}
