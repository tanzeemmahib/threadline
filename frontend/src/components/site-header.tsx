import { BrandMark } from "@/components/brand-mark";
import { ThreadLink } from "@/components/thread-motion";

export function SiteHeader({
  workspace = false,
  demo = false,
  landing = false,
  active,
}: {
  workspace?: boolean;
  demo?: boolean;
  landing?: boolean;
  active?: "workspace" | "prompt-lab" | "evaluation" | "trials" | "methodology";
}) {
  return (
    <header className={`site-header ${landing ? "site-header--landing" : ""}`}>
      <div className="site-header__inner shell">
        <BrandMark />
        <nav className={`site-nav ${landing ? "site-nav--landing" : ""}`} aria-label="Primary navigation">
          {landing ? (
            <>
              <ThreadLink variant="nav" href="#case">Case</ThreadLink>
              <ThreadLink variant="nav" href="#method">Method</ThreadLink>
              <ThreadLink variant="nav" href="#safety">Safety</ThreadLink>
              <ThreadLink variant="nav" href="#audit">Audit</ThreadLink>
            </>
          ) : (
            <>
              <ThreadLink variant="nav" bridge current={demo} href="/demo?demo=guided">Guided Case</ThreadLink>
              <ThreadLink variant="nav" bridge current={active === "prompt-lab"} href="/prompt-lab">Prompt Lab</ThreadLink>
              <ThreadLink variant="nav" bridge current={active === "workspace"} href="/workspace">Workspace</ThreadLink>
              <ThreadLink variant="nav" bridge current={active === "evaluation"} href="/benchmark">Evaluation</ThreadLink>
              <details className="site-nav__technical" open={active === "trials" || active === "methodology"}>
                <summary data-active={active === "trials" || active === "methodology" || undefined}>
                  <span className="site-nav__technical-label site-nav__technical-label--full">Technical evidence</span>
                  <span className="site-nav__technical-label site-nav__technical-label--compact">Technical</span>
                </summary>
                <div className="site-nav__technical-menu">
                  <ThreadLink variant="nav" bridge current={active === "trials"} href="/trials">Trials</ThreadLink>
                  <ThreadLink variant="nav" bridge current={active === "methodology"} href="/methodology">Methodology</ThreadLink>
                </div>
              </details>
            </>
          )}
        </nav>
        {landing ? (
          <ThreadLink variant="bare" motion="signature" arrow="forward" bridge className="site-header__text-cta" data-threadline-cta href="/demo?demo=guided">Run the evidence case</ThreadLink>
        ) : workspace ? (
          <ThreadLink variant="primary" motion="signature" arrow="forward" bridge className="site-header__cta" data-threadline-cta data-threadline-reload href={demo ? "/demo?demo=guided" : "/workspace?demo=guided"}>
            <span className="site-header__cta-label site-header__cta-label--full">Restart guided case</span>
            <span className="site-header__cta-label site-header__cta-label--compact">Restart case</span>
          </ThreadLink>
        ) : (
          <ThreadLink variant="primary" motion="signature" arrow="forward" bridge className="site-header__cta" data-threadline-cta href="/demo?demo=guided">
            <span className="site-header__cta-label site-header__cta-label--full">Run the evidence case</span>
            <span className="site-header__cta-label site-header__cta-label--compact">Run case</span>
          </ThreadLink>
        )}
      </div>
    </header>
  );
}
