import { useEffect, useRef, useState, type ReactNode } from "react";
import { useLocation } from "@rspress/core/runtime";
import CloseIcon from "~icons/mingcute/close-line";
import DownIcon from "~icons/mingcute/down-line";
import { projects, logo, appliances, navLinks } from "./data";
import { SearchBox } from "./Search";
import "./header.css";

function Dropdown({ label, children }: { label: string; children: ReactNode }) {
  return (
    <details
      className="portal-dropdown"
      onMouseEnter={(e) => {
        if (window.matchMedia("(hover: hover)").matches)
          e.currentTarget.open = true;
      }}
      onMouseLeave={(e) => {
        if (window.matchMedia("(hover: hover)").matches)
          e.currentTarget.open = false;
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") e.currentTarget.open = false;
      }}
    >
      <summary>
        {label}
        <DownIcon aria-hidden="true" />
      </summary>
      <div className="portal-nav-dropdown">{children}</div>
    </details>
  );
}
function NavLinks() {
  return (
    <>
      <a
        className="portal-home-link"
        href="/"
        aria-current={__DOCS_PROJECT__ === "portal" ? "page" : undefined}
      >
        首页
      </a>
      <Dropdown label="开源产品">
        {projects.map((p) => (
          <a key={p.id} href={p.website} target="_blank" rel="noreferrer">
            <img src={`/img/logo/${p.logo}`} alt="" />
            <span>
              <strong>{p.name}</strong>
              <small>{p.desc}</small>
            </span>
          </a>
        ))}
      </Dropdown>
      <Dropdown label="一体机">
        {appliances.map((p) => (
          <a key={p.name} href={p.website} target="_blank" rel="noreferrer">
            <img src={`/img/logo/${p.logo}`} alt="" />
            <strong>
              {p.name}
              {p.isNew && <span className="portal-new">NEW</span>}
            </strong>
          </a>
        ))}
      </Dropdown>
      {navLinks.map(([label, url]) => (
        <a key={label} href={url} target="_blank" rel="noreferrer">
          {label}
        </a>
      ))}
    </>
  );
}
export function Header() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const saved = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", escape);
    return () => {
      document.body.style.overflow = saved;
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  const button = useRef<HTMLButtonElement>(null);
  const drawer = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!open) return;
    const first =
      drawer.current?.querySelector<HTMLElement>("button, a, input");
    first?.focus();
    const trap = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const items = Array.from(
        drawer.current?.querySelectorAll<HTMLElement>(
          "a[href], button, input, summary",
        ) || [],
      ).filter((el) => el.getClientRects().length);
      if (event.shiftKey && document.activeElement === items[0]) {
        event.preventDefault();
        items.at(-1)?.focus();
      }
      if (!event.shiftKey && document.activeElement === items.at(-1)) {
        event.preventDefault();
        items[0]?.focus();
      }
    };
    document.addEventListener("keydown", trap);
    return () => {
      document.removeEventListener("keydown", trap);
      button.current?.focus();
    };
  }, [open]);
  return (
    <>
      <header className="portal-nav">
        <nav aria-label="主导航">
          <button
            ref={button}
            className="portal-hamburger"
            aria-label="切换导航栏"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            <svg width="30" height="30" viewBox="0 0 30 30" aria-hidden="true">
              <path
                stroke="currentColor"
                strokeLinecap="round"
                strokeMiterlimit="10"
                strokeWidth="2"
                d="M4 7h22M4 15h22M4 23h22"
              />
            </svg>
          </button>
          <a href="/" className="portal-brand">
            <img src={logo} alt="FIT2CLOUD 飞致云 | 文档中心" />
          </a>
          <div className="portal-nav-links">
            <NavLinks />
          </div>
        </nav>
      </header>
      {open && (
        <div className="portal-mobile-overlay" onClick={() => setOpen(false)}>
          <aside
            ref={drawer}
            className="portal-mobile-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="导航菜单"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="portal-mobile-brand">
              <a href="/">
                <img src={logo} alt="文档中心" />
              </a>
              <button aria-label="关闭导航" onClick={() => setOpen(false)}>
                <CloseIcon />
              </button>
            </div>
            {__DOCS_PROJECT__ === "portal" && <SearchBox compact />}
            <div className="portal-mobile-links">
              <NavLinks />
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
