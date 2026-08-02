import Link from "next/link";
import { BrandMark } from "@/components/brand-mark";

export function SiteHeader({ workspace = false }: { workspace?: boolean }) {
  return (
    <header className="site-header">
      <div className="site-header__inner shell">
        <BrandMark />
        <nav className="site-nav" aria-label="Primary navigation">
          <Link className="site-nav__link" href="/workspace">Workspace</Link>
          <Link className="site-nav__link" href="/benchmark">Evaluation</Link>
          <Link className="site-nav__link" href="/trials">Trials</Link>
          <Link className="site-nav__link" href="/methodology">Methodology</Link>
        </nav>
        {workspace ? (
          <a className="button-primary site-header__cta" href="/workspace">
            Restart demo <span aria-hidden="true">→</span>
          </a>
        ) : (
          <Link className="button-primary site-header__cta" href="/workspace">
            Open live incident <span aria-hidden="true">→</span>
          </Link>
        )}
      </div>
    </header>
  );
}
