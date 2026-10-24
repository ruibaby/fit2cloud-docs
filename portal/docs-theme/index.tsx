import { Layout as OriginalLayout } from "@rspress/core/theme-original";
import { FooterColumns } from "../../theme/FooterColumns";
import { Header } from "../shared/Header";
import { ProjectSwitch } from "./ProjectSwitch";
import { ProjectTitle } from "./ProjectTitle";
import "./index.css";

export * from "@rspress/core/theme-original";
export { Link } from "./Link";

export function Layout() {
  return (
    <OriginalLayout
      beforeNav={<Header />}
      beforeNavTitle={<ProjectSwitch />}
      navTitle={<ProjectTitle />}
      bottom={__DOCS_PROJECT__ === "halo" ? <FooterColumns /> : undefined}
    />
  );
}
