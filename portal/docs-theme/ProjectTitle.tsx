import { useLang, useSite } from "@rspress/core/runtime";
import { Link, NavTitle } from "@rspress/core/theme-original";
import projects from "../projects.json";

// Keep the native title layout, but do not prefix shared logo URLs with the project base.
export function ProjectTitle() {
  const lang = useLang();
  const { site } = useSite();
  if (__DOCS_PROJECT__ === "halo") return <NavTitle />;
  const project = projects.find((item) => item.id === __DOCS_PROJECT__)!;
  return (
    <div className="rp-nav__title">
      <Link
        href={lang === site.lang ? "/" : `/${lang}/`}
        className="rp-nav__title__link"
      >
        <div className="rp-nav__title__logo">
          <img
            src={`/img/logo/${project.logo}`}
            alt="logo"
            id="logo"
            className="rspress-logo rp-nav__title__logo-image"
          />
        </div>
        <span>{site.logoText}</span>
      </Link>
    </div>
  );
}
