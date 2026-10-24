import { useEffect, useRef } from "react";
import { useLocation } from "@rspress/core/runtime";
import projects from "../projects.json";
import "./project-switch.css";

export function ProjectSwitch() {
  const menu = useRef<HTMLDetailsElement>(null);
  const trigger = useRef<HTMLElement>(null);
  const { pathname } = useLocation();
  useEffect(() => {
    if (menu.current) menu.current.open = false;
  }, [pathname]);
  useEffect(() => {
    const dismiss = (event: PointerEvent) => {
      if (menu.current && !menu.current.contains(event.target as Node)) {
        menu.current.open = false;
      }
    };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, []);
  return (
    <details
      ref={menu}
      className="docs-project-menu"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.currentTarget.open = false;
          trigger.current?.focus();
          event.stopPropagation();
        }
      }}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget))
          event.currentTarget.open = false;
      }}
    >
      <summary
        ref={trigger}
        aria-label="切换项目"
        aria-controls="docs-project-panel"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          {[3, 9, 15].flatMap((y) =>
            [3, 9, 15].map((x) => (
              <rect key={`${x}-${y}`} x={x} y={y} width="2.5" height="2.5" />
            )),
          )}
        </svg>
      </summary>
      <nav
        id="docs-project-panel"
        className="docs-project-panel"
        aria-label="项目文档"
      >
        <a className="docs-project-panel__home" href="/">
          <span>FIT2CLOUD</span>
          <strong>文档中心</strong>
        </a>
        <div className="docs-project-panel__grid">
          {projects.map((item) => (
            <a
              key={item.id}
              href={item.href}
              aria-current={item.id === __DOCS_PROJECT__ ? "true" : undefined}
            >
              <img src={`/img/logo/${item.logo}`} alt="" />
              <span>
                <strong>{item.name}</strong>
                <small>{item.desc}</small>
              </span>
            </a>
          ))}
        </div>
      </nav>
    </details>
  );
}
