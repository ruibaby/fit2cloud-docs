import { illustration, projects } from "./data";
import { SearchBox } from "./Search";
import styles from "./home.module.css";

export function PortalHome() {
  return (
    <main id="main-content" className={styles.portalPage}>
      <section className={styles.hero}>
        <span
          className={`${styles.heroDecor} ${styles.heroDecorBlue}`}
          aria-hidden="true"
        />
        <span
          className={`${styles.heroDecor} ${styles.heroDecorPurple}`}
          aria-hidden="true"
        />
        <div className={styles.heroInner}>
          <img
            src={illustration}
            alt="FIT2CLOUD 文档中心"
            className={styles.heroIllustration}
          />
          <h1 className={styles.heroTitle}>文档中心</h1>
          <p className={styles.heroSubtitle}>
            我们秉持"软件用起来才有价值，才有改进机会"的核心价值观，向中国数字化团队交付被广泛验证、可信赖的开源软件。
          </p>
          <div className="portal-hero-search">
            <SearchBox />
          </div>
        </div>
      </section>
      <section className={styles.productsSection} aria-label="产品文档">
        <div className={styles.productsInner}>
          <div className={styles.productsTitle} aria-hidden="true" />
          <div className={styles.productGrid}>
            {projects.map((p) => (
              <a
                key={p.id}
                href={p.href}
                className={styles.productCard}
                {...(p.href.startsWith("https:")
                  ? { target: "_blank", rel: "noreferrer" }
                  : {})}
              >
                <span className={styles.productHeader}>
                  <img
                    src={`/img/logo/${p.logo}`}
                    alt={p.name}
                    className={styles.productLogo}
                  />
                  <span className={styles.productName}>{p.name}</span>
                </span>
                <span className={styles.productSubtitle}>{p.desc}</span>
                <span className={styles.productDesc}>{p.description}</span>
                <span className={styles.productEnter}>进入文档</span>
              </a>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
