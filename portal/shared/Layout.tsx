import { useEffect, useRef, useState } from "react";
import { useLocation } from "@rspress/core/runtime";
import { Layout as OriginalLayout } from "@rspress/core/theme-original";
import CloseIcon from "~icons/mingcute/close-line";
import { project, footerColumns } from "./data";
import { footerIcons } from "./footer-icons";

export { Header as Nav } from "./Header";
export function Layout() {
  return (
    <>
      <a className="portal-skip" href="#main-content">
        跳到主要内容
      </a>
      <OriginalLayout bottom={<Footer />} />
      <Assistant />
    </>
  );
}
export function Footer() {
  return (
    <footer className="portal-footer">
      <div className="portal-footer-inner">
        <div className="portal-footer-columns">
          {footerColumns.map((column) => (
            <section key={column.title}>
              <h2>{column.title}</h2>
              <ul>
                {column.links.map(([label, url, icon]) => (
                  <li key={label}>
                    <a href={url} target="_blank" rel="noreferrer">
                      <svg
                        width="1em"
                        height="1em"
                        viewBox="0 0 32 32"
                        fill="currentColor"
                        aria-hidden="true"
                      >
                        {footerIcons[icon].map((d, i) => (
                          <path d={d} key={i} />
                        ))}
                      </svg>
                      {label}
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
        <div className="portal-copyright">
          <a href="https://beian.miit.gov.cn/" target="_blank" rel="noreferrer">
            浙ICP备14038283号
          </a>{" "}
          2014-{new Date().getFullYear()} 版权所有©杭州飞致云信息科技有限公司
          <br />
          <a
            href="https://fit2cloud.com/legal/privacy-policy.html"
            target="_blank"
            rel="noreferrer"
          >
            隐私政策
          </a>
          <span> | </span>
          <a
            href="https://fit2cloud.com/legal/licenses.html"
            target="_blank"
            rel="noreferrer"
          >
            社区软件许可协议
          </a>
        </div>
      </div>
    </footer>
  );
}
function Assistant() {
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const { pathname } = useLocation();
  const history = project?.versions
    .slice(1)
    .find((v) => pathname === `/${v}` || pathname.startsWith(`/${v}/`));
  const params = new URLSearchParams({
    mode: "embed",
    ...(project ? { product: project.id } : {}),
    ...(history ? { version: history } : {}),
  });
  useEffect(() => {
    if (!open) return;
    close.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      button.current?.focus();
    };
  }, [open]);
  return (
    <>
      <button
        ref={button}
        className="portal-assistant-button"
        aria-label="打开智能小助手"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        <img src="/img/assistant.gif" alt="" />
      </button>
      {open && (
        <section
          className="portal-assistant-panel"
          role="dialog"
          aria-label="智能小助手"
        >
          <iframe
            title="飞致云智能小助手"
            src={`https://maxkb-internal.fit2cloud.com/chat/d876eead1840ecc7?${params}`}
          />
          <button
            ref={close}
            className="portal-assistant-close"
            aria-label="关闭智能小助手"
            onClick={() => setOpen(false)}
          >
            <CloseIcon />
          </button>
        </section>
      )}
    </>
  );
}
