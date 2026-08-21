import { ThreadLink } from "@/components/thread-motion";

export type LandingEvidence = {
  artifactId: string;
  evaluationLabel: string;
  baselineFalseProposals: string;
  workflowFalseProposals: string;
  exactSpans: string;
  liveExtraction: string;
  liveFalseMerges: string;
  conflictRecall: string;
};

const workflowStages = [
  ["01", "Preserve", "Retain exact source text and quarantine embedded instructions."],
  ["02", "Extract", "Prompt V2 returns constrained fields with source offsets."],
  ["03", "Validate", "Schema and exact-span checks reject unsupported claims."],
  ["04", "Retrieve", "Bounded retrieval proposes candidate record pairs."],
  ["05", "Challenge", "Deterministic comparison surfaces conflicts and rivals."],
  ["06", "Withhold", "The evidence contract stops unsafe release."],
  ["07", "Review", "An authorized human records the disposition."],
] as const;

export function ReverieLanding({ evidence }: { evidence: LandingEvidence }) {
  return (
    <div className="reverie-landing">
      <section className="reverie-hero" id="case" aria-labelledby="reverie-hero-title">
        <div className="reverie-hero__thread" aria-hidden="true">
          <span className="reverie-hero__node reverie-hero__node--a" />
          <span className="reverie-hero__node reverie-hero__node--b" />
          <span className="reverie-hero__node reverie-hero__node--c" />
          <span className="reverie-hero__line reverie-hero__line--a" />
          <span className="reverie-hero__line reverie-hero__line--b" />
        </div>
        <div className="reverie-hero__copy">
          <p className="eyebrow">Evidence-first record reconciliation</p>
          <h1 id="reverie-hero-title">Connect the records.<br /><span>Never guess the person.</span></h1>
          <p className="reverie-hero__lede">THREADLINE reconnects fragmented missing-person reports across hospitals, shelters, NGOs, and families. AI extracts source-cited evidence; deterministic safety rules decide when the system must stop.</p>
          <div className="reverie-hero__actions">
            <ThreadLink variant="primary" motion="signature" arrow="forward" bridge magnetic proximity data-threadline-cta href="/demo?demo=guided">Run the evidence case</ThreadLink>
            <ThreadLink variant="text" motion="quiet" arrow="forward" bridge href="/prompt-lab">Compare the prompts</ThreadLink>
          </div>
          <p className="reverie-scope">Synthetic research demonstration. No identity is autonomously confirmed.</p>
        </div>
        <div className="reverie-records" aria-label="Three fragmented fictional records">
          <article className="reverie-record reverie-record--family">
            <span>FAMILY REPORT / 018</span>
            <strong>Youssef Al Hassan</strong>
            <p>Age 14 · Al Noor School · 16:30</p>
          </article>
          <article className="reverie-record reverie-record--shelter">
            <span>SHELTER INTAKE / 204</span>
            <strong>Youssef Al Hassan</strong>
            <p>Age 14 · North Gate · 19:10</p>
          </article>
          <article className="reverie-record reverie-record--rival">
            <span>HOSPITAL INTAKE / 052</span>
            <strong>Youssef Al Hassan</strong>
            <p>Documented age 24 · South Clinic · 18:50</p>
          </article>
          <p className="reverie-records__question">Three organizations. Three incomplete records. One supported thread—and one dangerously similar rival.</p>
        </div>
      </section>

      <section className="reverie-distinction" id="method" aria-labelledby="distinction-title">
        <header>
          <p className="eyebrow">Same records · different workflow</p>
          <h2 id="distinction-title">A prompt can propose.<br />It cannot set the boundary.</h2>
        </header>
        <div className="reverie-distinction__grid">
          <article>
            <span className="reverie-index">ONE CALL</span>
            <h3>Single-prompt baseline</h3>
            <p>Returns a plausible candidate answer from the complete record packet, but the deterministic fixture provides no exact citations or rival analysis.</p>
            <dl><div><dt>Same input</dt><dd>Yes</dd></div><div><dt>False proposals</dt><dd>{evidence.baselineFalseProposals}</dd></div></dl>
          </article>
          <div className="reverie-distinction__interrupt" aria-hidden="true"><span /><i /></div>
          <article className="is-threadline">
            <span className="reverie-index">STRUCTURED WORKFLOW</span>
            <h3>THREADLINE</h3>
            <p>Preserves source spans, tests rival explanations, and lets deterministic conflict rules withhold what the evidence cannot support.</p>
            <dl><div><dt>Exact cited spans</dt><dd>{evidence.exactSpans}</dd></div><div><dt>False proposals</dt><dd>{evidence.workflowFalseProposals}</dd></div></dl>
          </article>
        </div>
        <p className="reverie-evidence-label">{evidence.evaluationLabel} · {evidence.artifactId}</p>
      </section>

      <section className="reverie-workflow" aria-labelledby="workflow-title">
        <header>
          <p className="eyebrow">Prompt workflow / seven visible stages</p>
          <h2 id="workflow-title">Probabilistic extraction.<br />Deterministic restraint.</h2>
          <p>The model structures evidence. Code validates, compares, blocks, and routes. The final identity disposition remains human.</p>
        </header>
        <ol>
          {workflowStages.map(([index, title, detail], stageIndex) => (
            <li key={index}>
              <span>{index}</span>
              <div><strong>{title}</strong><p>{detail}</p></div>
              {stageIndex < workflowStages.length - 1 ? <i aria-hidden="true" /> : null}
            </li>
          ))}
        </ol>
      </section>

      <section className="reverie-results" aria-labelledby="results-title">
        <header>
          <p className="eyebrow">Verified evidence / separate evaluation tracks</p>
          <h2 id="results-title">The numbers stay attached<br />to their limits.</h2>
        </header>
        <div className="reverie-results__grid">
          <article><span>LIVE PROMPT V2</span><strong>{evidence.liveExtraction}</strong><p>schema-valid extraction outputs · one archived provider run</p></article>
          <article><span>DIFFERENT-IDENTITY PAIRS</span><strong>{evidence.liveFalseMerges}</strong><p>false merges observed · small synthetic denominator</p></article>
          <article><span>BLOCKING CONFLICTS</span><strong>{evidence.conflictRecall}</strong><p>recall in the archived synthetic run</p></article>
        </div>
        <ThreadLink variant="text" arrow="forward" bridge href="/prompt-lab">Inspect prompts, cases, and raw evidence</ThreadLink>
      </section>

      <section className="reverie-safety" id="safety" aria-labelledby="safety-title">
        <div className="reverie-safety__gate" aria-hidden="true"><span /><i /><span /></div>
        <div>
          <p className="eyebrow">Deterministic safety gate</p>
          <h2 id="safety-title">A convincing rival is exactly<br />where the system must stop.</h2>
          <p>The walkthrough recovers one supported candidate connection for authorized review, then blocks the hospital rival on a document-backed age conflict. The LLM cannot override that rule.</p>
        </div>
        <dl>
          <div><dt>Possible connection</dt><dd>Supported for review</dd></div>
          <div><dt>Dangerous rival</dt><dd>Blocked by conflict</dd></div>
          <div><dt>Identity decision</dt><dd>Human authority only</dd></div>
        </dl>
      </section>

      <section className="reverie-closing" id="audit" aria-labelledby="closing-title">
        <p className="eyebrow">The evidence challenge / 75–100 seconds</p>
        <h2 id="closing-title">One connection recovered.<br />One false merge prevented.<br /><span>Every decision traceable.</span></h2>
        <p>Follow the same synthetic records from source text to exact spans, deterministic conflict policy, human handoff, audit, and replay.</p>
        <div>
          <ThreadLink variant="primary" motion="signature" arrow="forward" bridge magnetic data-threadline-cta href="/demo?demo=guided">Run the evidence case</ThreadLink>
          <ThreadLink variant="text" motion="quiet" arrow="forward" bridge href="/prompt-lab">Compare the prompts</ThreadLink>
        </div>
      </section>
    </div>
  );
}
