import type { Metadata } from "next";
import Link from "next/link";
import { LandingEvidenceThread } from "@/components/landing-evidence-thread";
import { SiteHeader } from "@/components/site-header";
import { WorkflowStrip } from "@/components/workflow-strip";

export const metadata: Metadata = {
  title: "Traceable candidate connections",
  description: "See how THREADLINE turns fragmented synthetic records into auditable candidate connections for human review.",
};

const principles = [
  {
    number: "01",
    title: "Fragmented records",
    copy: "Exact-name search fails when names, languages, ages, and locations differ.",
  },
  {
    number: "02",
    title: "Reasoning with opposition",
    copy: "One workflow stage proposes a connection while another tries to disprove it.",
  },
  {
    number: "03",
    title: "Auditable human review",
    copy: "Every candidate includes evidence, contradictions, and the next useful verification question.",
  },
];

export default function Home() {
  return (
    <>
      <SiteHeader />
      <main id="main-content">
        <section className="landing-hero shell" aria-labelledby="hero-title">
          <div className="landing-hero__copy">
            <p className="eyebrow">Humanitarian record reconciliation</p>
            <h1 className="display-title" id="hero-title">
              One person can exist as five disconnected records.
            </h1>
            <p className="body-large landing-hero__description">
              THREADLINE helps trained reviewers trace possible connections across fragmented multilingual reports—without asking them to trust a black-box identity match.
            </p>
            <div className="landing-hero__actions">
              <Link className="button-primary" href="/workspace">
                Open live incident <span aria-hidden="true">→</span>
              </Link>
              <Link className="button-secondary" href="/benchmark">
                View evaluation
              </Link>
            </div>
            <div className="landing-boundary">
              <span aria-hidden="true">◆</span>
              <p>
                Decision-support only. Candidate connections remain subject to authorized human review and independent verification.
              </p>
            </div>
          </div>
          <LandingEvidenceThread />
        </section>

        <section className="principles shell" aria-labelledby="principles-title">
          <div className="principles__header">
            <p className="eyebrow">Why the workflow is structured</p>
            <h2 className="section-title" id="principles-title">Reasoning that can be inspected, challenged, and stopped.</h2>
          </div>
          <ol className="principles__grid">
            {principles.map((principle) => (
              <li className="principle" key={principle.number}>
                <span className="principle__number">{principle.number}</span>
                <h3>{principle.title}</h3>
                <p>{principle.copy}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="workflow-section" aria-labelledby="workflow-title">
          <div className="shell">
            <div className="workflow-section__heading">
              <div>
                <p className="eyebrow">Inspectable ML workflow</p>
                <h2 className="section-title" id="workflow-title">From preserved evidence to a human checkpoint.</h2>
              </div>
              <p>Open any stage to inspect its role. No stage is permitted to make a final identity decision.</p>
            </div>
            <WorkflowStrip />
          </div>
        </section>

        <section className="landing-close shell" aria-labelledby="close-title">
          <div>
            <p className="eyebrow">Synthetic incident ready</p>
            <h2 className="section-title" id="close-title">Follow one evidence thread from source text to review.</h2>
          </div>
          <Link className="button-primary" href="/workspace">
            Enter workspace <span aria-hidden="true">→</span>
          </Link>
        </section>
      </main>
      <footer className="site-footer">
        <div className="shell">
          <span>THREADLINE / Research prototype</span>
          <p>Fictional identities. Synthetic records. Human verification required.</p>
        </div>
      </footer>
    </>
  );
}

