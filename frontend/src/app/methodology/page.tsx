import type { Metadata } from "next";
import { SiteHeader } from "@/components/site-header";
import { StatusPill } from "@/components/status-pill";
import { ThreadLink } from "@/components/thread-motion";
import { workflowNodes } from "@/data/mock-data";

export const metadata: Metadata = {
  title: "Workflow methodology",
  description: "Node-by-node reasoning, structured output boundaries, evaluation design, privacy constraints, and limitations for THREADLINE.",
};

const candidateSchema = `{
  "candidate_id": "MATCH-001",
  "label": "Possible candidate connection",
  "review_status": "review_required",
  "compatibility_factors": [],
  "conflicts": [],
  "rivals": [],
  "verification_question": "..."
}`;

const spanSchema = `{
  "span_id": "SPAN-F18-NAME",
  "record_id": "FAMILY-018",
  "text": "يوسف الحسن",
  "field": "Name",
  "extraction_status": "extracted",
  "normalization_note": "Original text preserved."
}`;

export default function MethodologyPage() {
  return (
    <>
      <SiteHeader active="methodology" />
      <main id="main-content" className="methodology-page">
        <section className="methodology-hero shell" aria-labelledby="methodology-title">
          <div>
            <p className="eyebrow">Methodology / system boundary / safety</p>
            <h1 className="page-title" id="methodology-title">A workflow designed to show its work—and its limits.</h1>
            <p className="body-large">THREADLINE separates preservation, transformation, opposition, validation, privacy, and human decision-making so each stage can be inspected independently.</p>
          </div>
          <aside className="methodology-boundary panel-subtle">
            <StatusPill tone="amber">System boundary</StatusPill>
            <strong>THREADLINE does not autonomously determine identity.</strong>
            <p>It proposes candidate record connections for authorized human review using fictional identities and synthetic records in this prototype.</p>
          </aside>
        </section>

        <nav className="methodology-index shell" aria-label="Methodology sections">
          {[
            ["problem", "Problem definition"], ["boundary", "System boundary"], ["architecture", "Workflow architecture"],
            ["nodes", "Node reasoning"], ["prompts", "Prompt strategy"], ["schemas", "Output schemas"],
            ["checkpoints", "Human checkpoints"], ["synthetic", "Synthetic data"], ["evaluation", "Evaluation"],
            ["safety", "Safety & privacy"], ["limitations", "Limitations"], ["future", "Future research"],
          ].map(([id, label], index) => <a href={`#${id}`} key={id}><span>{String(index + 1).padStart(2, "0")}</span>{label}</a>)}
        </nav>

        <article className="methodology-content shell">
          <section id="problem" className="method-section">
            <header><span>01</span><div><p className="eyebrow">Problem definition</p><h2 className="section-title">Fragmented records are not identity decisions.</h2></div></header>
            <div className="method-section__body two-column-copy">
              <p>After a disaster, the same fictional person may appear across family reports, shelter registration, hospital intake, evacuation logs, translated phone reports, and volunteer notes. Literal search fails when names are transliterated differently, ages are estimated, locations change, or descriptions are incomplete.</p>
              <p>The system’s task is narrower than identity resolution: retrieve and structure possible candidate connections, retain support and opposition, expose missing evidence, and route the result to an authorized reviewer.</p>
            </div>
          </section>

          <section id="boundary" className="method-section">
            <header><span>02</span><div><p className="eyebrow">System boundary</p><h2 className="section-title">What the system may—and may not—do.</h2></div></header>
            <div className="boundary-grid method-section__body">
              <article><span>Within boundary</span><ul><li>Preserve and structure supplied records</li><li>Retrieve possible candidate pairs</li><li>Compare evidence and nearby rivals</li><li>Abstain or request human review</li><li>Record an auditable review action</li></ul></article>
              <article><span>Outside boundary</span><ul><li>Determine or prove identity</li><li>Declare a case resolved</li><li>Search unrestricted external sources</li><li>Override authorization procedures</li><li>Replace independent verification</li></ul></article>
            </div>
          </section>

          <section id="architecture" className="method-section">
            <header><span>03</span><div><p className="eyebrow">Workflow architecture</p><h2 className="section-title">Twelve distinct responsibilities.</h2></div></header>
            <div className="architecture-flow method-section__body" role="img" aria-label="Twelve workflow nodes progress from incident configuration through evidence quarantine, extraction, normalization, timeline reconstruction, retrieval, hypothesis, contradiction, rival testing, adjudication, privacy gate, and human review.">
              {workflowNodes.map((node, index) => <div className={`architecture-node architecture-node--${node.category.toLowerCase().replaceAll(" ", "-").replaceAll("/", "-")}`} key={node.node_id}><span>{String(node.order).padStart(2, "0")}</span><strong>{node.name}</strong><small>{node.category}</small>{index < workflowNodes.length - 1 && <i aria-hidden="true">→</i>}</div>)}
            </div>
            <ul className="category-legend" aria-label="Workflow category legend"><li><span className="legend-human" />Human input or decision</li><li><span className="legend-llm" />LLM transformation or reasoning</li><li><span className="legend-deterministic" />Deterministic validation or retrieval</li><li><span className="legend-safety" />Privacy and safety</li></ul>
          </section>

          <section id="nodes" className="method-section">
            <header><span>04</span><div><p className="eyebrow">Node-by-node reasoning</p><h2 className="section-title">Open every stage. Inspect every contract.</h2></div></header>
            <div className="node-method-ledger method-section__body">
              <div className="node-method-ledger__head" aria-hidden="true">
                <span>Stage</span><span>Responsibility</span><span>Execution</span><span>Hand-off</span><span>Contract</span>
              </div>
              <ol className="node-method-list">
                {workflowNodes.map((node) => (
                  <li className="node-method-list__item" key={node.node_id}>
                    <details className="node-method">
                      <summary>
                        <span className="node-method__stage">{String(node.order).padStart(2, "0")}</span>
                        <div className="node-method__identity"><strong>{node.name}</strong><small>{node.category}</small></div>
                        <span className="node-method__method"><span className="sr-only">Execution method: </span>{node.method}</span>
                        <span className="node-method__handoff"><span className="sr-only">Downstream consumer: </span>{node.downstream_consumer}</span>
                        <i aria-hidden="true">+</i>
                      </summary>
                      <div className="node-method__content">
                        <dl>
                          <div><dt>Objective</dt><dd>{node.purpose}</dd></div>
                          <div><dt>Why this node exists</dt><dd>It keeps {node.short_name.toLowerCase()} responsibility separate so its evidence, failure, and downstream effect can be inspected.</dd></div>
                          <div><dt>Input</dt><dd>{node.input}</dd></div>
                          <div><dt>Constraints</dt><dd><ul>{node.constraints.map((constraint) => <li key={constraint}>{constraint}</li>)}</ul></dd></div>
                          <div><dt>Output schema</dt><dd>{node.output}</dd></div>
                          <div><dt>Failure behaviour</dt><dd>{node.failure_condition} The original record remains preserved and the stage may return a warning or abstention.</dd></div>
                          <div><dt>Downstream consumer</dt><dd>{node.downstream_consumer}</dd></div>
                          <div><dt>Uses an LLM?</dt><dd>{node.method === "Configured LLM" ? "Yes — Configured LLM. No model name is assumed by the frontend." : `No — ${node.method}.`}</dd></div>
                          <div><dt>Requires human input?</dt><dd>{node.human_input_requirement}</dd></div>
                        </dl>
                      </div>
                    </details>
                  </li>
                ))}
              </ol>
            </div>
          </section>

          <section id="prompts" className="method-section">
            <header><span>05</span><div><p className="eyebrow">Prompt strategy</p><h2 className="section-title">Separate proposal from opposition.</h2></div></header>
            <div className="method-card-grid method-section__body">
              <article><span>A / Transform</span><h3>Extract before reasoning</h3><p>Schema-constrained extraction attaches certainty and source spans before candidate reasoning begins.</p></article>
              <article><span>B / Propose</span><h3>Build the strongest hypothesis</h3><p>The hypothesis stage may use only preserved evidence and may not invent a probability.</p></article>
              <article><span>C / Challenge</span><h3>Search independently for opposition</h3><p>The contradiction prosecutor receives equal prominence and distinguishes absence, uncertainty, soft conflict, and hard conflict.</p></article>
              <article><span>D / Adjudicate</span><h3>Permit abstention</h3><p>An independent structured stage checks evidence coverage, rivals, and conflicts before routing to a human checkpoint.</p></article>
            </div>
          </section>

          <section id="schemas" className="method-section">
            <header><span>06</span><div><p className="eyebrow">Structured output schemas</p><h2 className="section-title">Machine-checkable outputs, human-readable evidence.</h2></div></header>
            <div className="schema-grid method-section__body"><article><header><span>CandidateConnection</span><small>Review packet</small></header><pre><code>{candidateSchema}</code></pre></article><article><header><span>OriginalEvidenceSpan</span><small>Source provenance</small></header><pre><code>{spanSchema}</code></pre></article></div>
          </section>

          <section id="checkpoints" className="method-section">
            <header><span>07</span><div><p className="eyebrow">Human checkpoints</p><h2 className="section-title">Authorization enters more than once.</h2></div></header>
            <ol className="checkpoint-list method-section__body"><li><span>01</span><div><strong>Incident configuration</strong><p>An authorized operator defines scope, sources, languages, and review boundary.</p></div></li><li><span>02</span><div><strong>Ambiguous extraction or safety review</strong><p>Language and safety ambiguities can stop downstream processing without discarding original evidence.</p></div></li><li><span>03</span><div><strong>Privacy gate exception</strong><p>Access exceptions require an authorized procedure and an audit entry.</p></div></li><li><span>04</span><div><strong>Candidate review</strong><p>A reviewer may request more information, dismiss, escalate, or mark records unrelated. There is no one-click identity confirmation.</p></div></li></ol>
          </section>

          <section id="synthetic" className="method-section">
            <header><span>08</span><div><p className="eyebrow">Synthetic-data design</p><h2 className="section-title">Fictional by construction.</h2></div></header>
            <div className="method-section__body two-column-copy"><p>The demo uses deterministic fictional identities across English, Arabic, and French records. Cases cover transliteration, approximate age, changing location, duplicates, close rivals, a hard contradiction, complete abstention, translation loss, and one embedded-instruction test.</p><p>Values do not change on refresh. Original-language spans remain visible beside translated and normalized representations; a French case explicitly flags a meaningful qualifier omitted by its reference translation.</p></div>
          </section>

          <section id="evaluation" className="method-section">
            <header><span>09</span><div><p className="eyebrow">Evaluation methodology</p><h2 className="section-title">Reference cases, baselines, and ablations.</h2></div></header>
            <div className="method-section__body evaluation-method"><div><strong>Systems</strong><p>A fixed-seed deterministic harness compares exact/fuzzy matching, two reasonable single-call prompts, and the full workflow on identical record packets. It evaluates workflow behavior, not live-model quality.</p></div><div><strong>Safety-first metrics</strong><p>Raw false-release opportunities are reported separately from possible-connection coverage, abstention, contradiction recall, citation validity, and reviewer handoff. A withheld case is not counted as an ordinary error.</p></div><div><strong>Measured live comparison</strong><p>A frozen preregistered comparison (3 synthetic cases × 3 repetitions × 2 systems = 18 runs, same model and settings) ran on a live OpenAI-compatible provider. THREADLINE emitted 0 invalid citations and 0 unsupported fields across 9 runs; the structured one-shot was outcome-acceptable in 9/9 runs but emitted 45 invalid citations. Every request, response, retry, and error is recorded in a sanitized checkpoint.</p></div><div><strong>Archived live evidence</strong><p>The versioned Prompt V2 archive measures extraction and downstream policy on 58 synthetic records. It is one provider run, not a same-model baseline comparison or a field-validation claim.</p></div><div><strong>Ablations and counterfactuals</strong><p>Node removals are reported even when they produce no measured change. A separate deterministic counterfactual records the first rule changed when material contradictory evidence is removed.</p></div></div>
            <p className="method-note">Submission artifacts lock fixture hashes, prompt and provider identifiers, raw outputs, metric definitions, denominators, and limitations. Cost and repeated-run confidence intervals remain explicitly not measured; the live same-model comparison completed 18/18 runs with mixed outcomes and claims no superiority.</p>
          </section>

          <section id="safety" className="method-section">
            <header><span>10</span><div><p className="eyebrow">Safety and privacy</p><h2 className="section-title">Treat records as evidence, never instructions.</h2></div></header>
            <div className="safety-grid method-section__body"><article><h3>Instruction/data separation</h3><p>Embedded instructions are preserved as record content, quarantined, and excluded from workflow control. The demonstrated case is a test, not proof of universal resistance.</p></article><article><h3>Reviewer minimization</h3><p>The privacy gate limits reviewer-facing packets. It runs after model-backed stages and must not be mistaken for provider-side data minimization.</p></article><article><h3>Language safety</h3><p>The interface uses candidate and compatibility language, avoids invented probabilities, and retains uncertainty labels.</p></article><article><h3>Human authority</h3><p>Final decisions require authorized external procedures and independent verification beyond this prototype.</p></article></div>
          </section>

          <section id="limitations" className="method-section">
            <header><span>11</span><div><p className="eyebrow">Limitations</p><h2 className="section-title">What remains unresolved.</h2></div></header>
            <ul className="limitation-list method-section__body"><li>Synthetic examples do not represent the distribution, ambiguity, or harm profile of real disaster records.</li><li>The local backend has no production authentication, case-level authorization, encryption-at-rest boundary, retention policy, or operational privacy governance.</li><li>The central baseline comparison is a deterministic mock workflow harness—not measured live-model performance. A frozen same-model live comparison completed 18/18 runs with mixed outcomes (one-shot: 9/9 outcome-acceptable with 45 invalid citations; THREADLINE: 0 invalid citations with abstention on 6/9 runs) and claims no superiority.</li><li>Transliteration and translation can erase context; language-specialist review remains necessary.</li><li>Prompt-injection testing covers bounded synthetic cases and cannot establish universal protection.</li><li>Candidate retrieval can miss relevant records or surface harmful false links; abstention and independent review remain essential.</li></ul>
          </section>

          <section id="future" className="method-section">
            <header><span>12</span><div><p className="eyebrow">Future research</p><h2 className="section-title">Evidence needed before expansion.</h2></div></header>
            <div className="method-section__body two-column-copy"><p>Future work should prioritize independently reviewed synthetic benchmark suites, adversarial multilingual records, calibrated abstention studies, reviewer usability research, and reproducible comparisons across configured models.</p><p>Any work with sensitive real-world data would require governance, threat modeling, privacy review, access controls, community consultation, and formal authorization outside this prototype.</p></div>
          </section>
        </article>

        <section className="methodology-close shell"><div><p className="eyebrow">See the method in motion</p><h2 className="section-title">Replay the synthetic workflow and inspect its evidence.</h2></div><ThreadLink variant="primary" bridge arrow="forward" href="/workspace">Open workspace</ThreadLink></section>
      </main>
    </>
  );
}
