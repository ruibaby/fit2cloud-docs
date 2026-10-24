import {
  pathnameToRouteService,
  removeBase,
  useLang,
  useLocation,
  useSite,
  useVersion,
} from "@rspress/core/runtime";
import {
  Link as OriginalLink,
  type LinkProps,
} from "@rspress/core/theme-original";

// Rspress 2.0.23 drops the first segment for the active default-version link.
// Keep native navigation UI, but preserve paths and fall back for missing pages.
export function Link(props: LinkProps) {
  const { pathname } = useLocation();
  const { site } = useSite();
  const version = useVersion();
  const lang = useLang();
  const label = props["aria-label"] || props.children;
  const versionMenu =
    props.className === "rp-hover-group__item__link" ||
    props.className?.startsWith("rp-nav-screen-versions-group__item");
  let href = props.href;
  if (
    versionMenu &&
    typeof label === "string" &&
    site.multiVersion?.versions?.includes(label)
  ) {
    const parts = removeBase(pathname).split("/").filter(Boolean);
    if (version !== site.multiVersion.default) parts.shift();
    const prefix = label === site.multiVersion.default ? "" : `/${label}`;
    href = `${prefix}/${parts.join("/")}`;
    const route = pathnameToRouteService(href);
    if (!route || route.path.includes("*")) {
      href = `${prefix}/${lang === site.lang ? "" : `${lang}/`}`;
    }
  }
  return <OriginalLink {...props} href={href} />;
}
