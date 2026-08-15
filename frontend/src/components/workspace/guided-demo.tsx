import {
  useEffect,
  useRef,
  type CSSProperties,
  type KeyboardEvent,
  type MouseEvent as ReactMouseEvent,
} from "react";
import { ConnectionState, ThreadButton, ThreadTrace } from "@/components/thread-motion";
import { judgeEvidence } from "@/data/judge-evidence";

export const guidedDemoSteps = [
  { label: "Fragmented records", title: "1. Fragmented records", detail: "A family report and shelter intake share plausible details, but incomplete evidence permits no identity conclusion.", phase: "fragment" },
  { label: "Single-prompt baseline", title: "2. Single-prompt baseline", detail: "A reasonable single prompt reaches a plausible answer on the same synthetic case input.", phase: "search" },
  { label: "Evidence extraction", title: "3. Evidence extraction", detail: "THREADLINE separates exact source text, normalized values, source status, and extraction uncertainty.", phase: "trace" },
  { label: "Contradiction challenge", title: "4. Contradiction challenge", detail: "A soft birth-date conflict and a material location contradiction remain visibly distinct.", phase: "interruption" },
  { label: "Rival candidate", title: "5. Rival candidate", detail: "A nearby record remains plausible enough that leading-candidate-only reasoning would create false certainty.", phase: "branch" },
  { label: "Evidence contract", title: "6. Evidence contract", detail: "Deterministic release requirements preserve what passed, what failed, and why the output remains withheld.", phase: "withhold" },
  { label: "Human review", title: "7. Human review", detail: "Verify the audit history. Record the disposition at an accountable handoff boundary without an autonomous identity decision.", phase: "handoff" },
  { label: "Measured comparison", title: "8. Measured comparison", detail: "Raw-count evidence is separated by evaluation mode so deterministic replay is never presented as model performance.", phase: "boundary" },
] as const;

const sourceByStep = ["SPAN-F42-NAME", "SPAN-S118-CONTACT", "SPAN-F42-NAME", "SPAN-F42-DOB", "SPAN-A209-DOB", "SPAN-F42-LOC", "SPAN-S118-LOC", "SPAN-F42-LOC"] as const;

export function GuidedDemo({
  active,
  step,
  onStart,
  onExit,
  onReset,
  onStepChange,
  onOpenSource,
  onViewTechnicalEvidence,
}: {
  active: boolean;
  step: number;
  onStart: (event: ReactMouseEvent<HTMLButtonElement>) => void;
  onExit: () => void;
  onReset: () => void;
  onStepChange: (step: number) => void;
  onOpenSource: (spanId: string) => void;
  onViewTechnicalEvidence: (step: number) => void;
}) {
  const primaryActionRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!active) return;
    const frame = window.requestAnimationFrame(() => primaryActionRef.current?.focus());
    function handleEscape(event: globalThis.KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      onExit();
    }
    document.addEventListener("keydown", handleEscape);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [active, onExit, step]);

  if (!active) {
    return (
      <ThreadButton className="guided-demo-launch" id="guided-demo-launcher" variant="bare" motion="signature" type="button" onClick={onStart}>
        <span className="guided-demo-launch__copy"><span>Judge mode · under four minutes</span><strong>Start evidence challenge</strong></span>
      </ThreadButton>
    );
  }

  const item = guidedDemoSteps[step] ?? guidedDemoSteps[0];
  const isLast = step === guidedDemoSteps.length - 1;

  function handlePanelKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const target = event.target as HTMLElement;
    if (["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) return;
    if (event.key === "ArrowLeft" && step > 0) {
      event.preventDefault();
      onStepChange(step - 1);
    } else if (event.key === "ArrowRight" && !isLast) {
      event.preventDefault();
      onStepChange(step + 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      onStepChange(0);
    } else if (event.key === "End") {
      event.preventDefault();
      onStepChange(guidedDemoSteps.length - 1);
    }
  }

  return (
    <aside className="guided-demo guided-demo--judge" aria-label="Guided evidence challenge" aria-describedby="guided-demo-instructions" aria-keyshortcuts="ArrowLeft ArrowRight Home End Escape" onKeyDown={handlePanelKeyDown}>
      <div className="guided-demo__progress" aria-hidden="true"><span style={{ "--thread-progress": (step + 1) / guidedDemoSteps.length } as CSSProperties} /></div>
      <header className="guided-demo__header">
        <div className="guided-demo__index"><span>Evidence challenge</span><strong>{String(step + 1).padStart(2, "0")} / {String(guidedDemoSteps.length).padStart(2, "0")}</strong></div>
        <div className="guided-demo__copy" aria-live="polite" aria-atomic="true"><span>{item.phase}</span><h2>{item.label}</h2><p>{item.detail}</p></div>
        <ThreadButton variant="quiet" motion="quiet" type="button" onClick={onExit}>Exit guided case</ThreadButton>
      </header>
      <nav className="guided-demo__scene-nav" aria-label="Evidence challenge scenes">
        {guidedDemoSteps.map((scene, index) => <button type="button" key={scene.label} aria-label={`Scene ${index + 1}: ${scene.label}`} aria-current={index === step ? "step" : undefined} onClick={() => onStepChange(index)}><span>{String(index + 1).padStart(2, "0")}</span></button>)}
      </nav>
      <div className="guided-demo__scene" data-judge-scene={item.phase}><JudgeSceneContent step={step} onOpenSource={onOpenSource} /></div>
      <footer className="guided-demo__footer">
        <p id="guided-demo-instructions">Use Tab for controls, Left and Right Arrow for scenes, or Escape to exit. All records and identities are fictional.</p>
        <div className="guided-demo__evidence-actions">
          <ThreadButton variant="quiet" motion="quiet" type="button" onClick={() => onOpenSource(sourceByStep[step] ?? sourceByStep[0])}>Open source</ThreadButton>
          <ThreadButton variant="secondary" motion="connect" type="button" onClick={() => onViewTechnicalEvidence(step)}>View technical evidence</ThreadButton>
        </div>
        <div className="guided-demo__actions">
          <ThreadButton variant="quiet" motion="quiet" type="button" onClick={onReset}>Reset</ThreadButton>
          <ThreadButton variant="quiet" motion="quiet" type="button" disabled={step === 0} onClick={() => onStepChange(step - 1)}>Back</ThreadButton>
          {!isLast ? <ThreadButton variant="primary" motion="signature" arrow="forward" ref={primaryActionRef} type="button" onClick={() => onStepChange(step + 1)}>Next</ThreadButton> : <ThreadButton variant="primary" motion="signature" ref={primaryActionRef} type="button" onClick={onExit}>Finish evidence challenge</ThreadButton>}
        </div>
      </footer>
    </aside>
  );
}

function JudgeSceneContent({ step, onOpenSource }: { step: number; onOpenSource: (spanId: string) => void }) {
  if (step === 0) {
    return <div className="judge-fragment-scene"><div className="judge-fragment-pair"><article><span>Family report · FAMILY-042</span><h3>Amira Saleh</h3><p>Translated name · shared contact · Narin Quay at 18:20</p></article><ThreadTrace state="fragmented" /><article><span>Shelter intake · SHELTER-118</span><h3>Ameera Salih</h3><p>Direct intake · shared contact · Hillcrest School at 18:40</p></article></div><div className="judge-question"><span>No identity conclusion</span><h3>{judgeEvidence.case.question}</h3><p>Compatible details make the question reasonable. Missing and conflicting evidence keep the answer open.</p></div></div>;
  }

  if (step === 1) {
    const baseline = judgeEvidence.baseline;
    return (
      <div className="judge-baseline-scene">
        <header><span>{baseline.evaluationLabel}</span><strong>{baseline.promptTemplateId}.{baseline.promptTemplateVersion}</strong></header>
        <div className="judge-structured-output">
          <div><span>Structured answer · proposed pair</span><h3>{baseline.classification}</h3><p>{baseline.candidateRecordIds.join(" ↔ ")}</p></div>
          <dl><div><dt>Exact citations</dt><dd>{baseline.citations.length ? baseline.citations.join(", ") : "0 returned"}</dd></div><div><dt>Contradictions</dt><dd>{baseline.contradictions.length ? baseline.contradictions.join("; ") : "0 returned"}</dd></div><div><dt>Uncertainty</dt><dd>{baseline.uncertainty.join(" ")}</dd></div></dl>
        </div>
        <details className="judge-baseline-manifest">
          <summary>Exact prompt and shared six-record input manifest</summary>
          <blockquote>{baseline.prompt}</blockquote>
          <dl><div><dt>Prompt SHA-256</dt><dd>{baseline.promptSha256}</dd></div><div><dt>Input SHA-256</dt><dd>{judgeEvidence.case.inputSha256}</dd></div><div><dt>Records provided to both systems</dt><dd>{baseline.inputRecordIds.join(" · ")}</dd></div></dl>
        </details>
        <p className="judge-boundary-note">The answer is plausible. This replay evaluates workflow behavior, not model quality.</p>
      </div>
    );
  }

  if (step === 2) {
    return <div className="judge-extraction-scene"><header><span>Original source → normalized representation</span><p>Select either claim to open its exact source span in one interaction.</p></header><div className="judge-extraction-grid">{judgeEvidence.extractions.map((claim) => <button type="button" key={claim.spanId} onClick={() => onOpenSource(claim.spanId)}><span>{claim.source} · {claim.category}</span><strong>{claim.original}</strong><dl><div><dt>Normalized</dt><dd>{claim.normalized}</dd></div><div><dt>Independent source</dt><dd>{claim.independentSourceStatus}</dd></div><div><dt>Extraction uncertainty</dt><dd>{claim.uncertainty}</dd></div></dl><small>Open exact source span ↗</small></button>)}</div></div>;
  }

  if (step === 3) {
    return <div className="judge-conflict-scene">{judgeEvidence.conflicts.map((conflict, index) => <article className={index === 1 ? "is-material" : ""} key={conflict.field}><header><span>{conflict.kind}</span><strong>{conflict.field}</strong></header><div><p>{conflict.left}</p><ConnectionState state={index === 1 ? "interrupted" : "partial"} label={`${conflict.kind}: ${conflict.explanation}`} announce /><p>{conflict.right}</p></div><p>{conflict.explanation}</p></article>)}</div>;
  }

  if (step === 4) {
    const rival = judgeEvidence.rival;
    return <div className="judge-rival-scene"><div><span>Leading thread</span><h3>FAMILY-042 ↔ SHELTER-118</h3><p>Name and contact are compatible; birth date and location remain unresolved.</p></div><ThreadTrace state="partial" /><article><span>Credible rival · {rival.recordId}</span><h3>{rival.displayName}</h3><div><ul>{rival.support.map((item) => <li key={item}>+ {item}</li>)}</ul><ul>{rival.limits.map((item) => <li key={item}>— {item}</li>)}</ul></div></article><p>Considering only the leading candidate would hide a live alternative and create false certainty.</p></div>;
  }

  if (step === 5) {
    const contract = judgeEvidence.contract;
    return <div className="judge-contract-scene"><header><div><span>Deterministic release gate</span><strong>{contract.contractId}</strong></div><ConnectionState state="interrupted" label="Release withheld because a material contradiction remains unresolved" announce /></header><div className="judge-contract-rules"><section><h3>Passed</h3><ul>{contract.passed.map((item) => <li key={item}><span aria-hidden="true">◇</span>{item}</li>)}</ul></section><section><h3>Review required</h3><ul>{contract.warning.map((item) => <li key={item}><span aria-hidden="true">△</span>{item}</li>)}</ul></section><section className="is-blocked"><h3>Blocked</h3><ul>{contract.blocked.map((item) => <li key={item}><span aria-hidden="true">×</span>{item}</li>)}</ul></section></div><p className="judge-decisive-text">{contract.decisiveText}</p></div>;
  }

  if (step === 6) {
    const review = judgeEvidence.humanReview;
    return <div className="judge-review-scene"><ConnectionState state="partial" label="Evidence packet handed to authorized human review without an identity conclusion" announce /><div><span>Authorized handoff</span><h3>{review.state}</h3><p>{review.boundary}</p></div><blockquote>{review.question}</blockquote><dl><div><dt>Release state</dt><dd>Withheld</dd></div><div><dt>Reviewer authority</dt><dd>Required</dd></div><div><dt>Autonomous merge</dt><dd>Not permitted</dd></div></dl></div>;
  }

  const comparison = judgeEvidence.comparison;
  return (
    <div className="judge-comparison-scene">
      <div className="judge-case-comparison"><article><span>Same six-record synthetic case · single prompt</span><h3>The baseline produced an answer.</h3><p>{comparison.judgeCase.baseline}</p></article><article><span>Same six-record synthetic case · full workflow</span><h3>THREADLINE produced an evidence boundary.</h3><p>{comparison.judgeCase.threadline}</p></article></div>
      <article className="judge-deterministic-band">
        <header><span>{comparison.deterministic21.label}</span><strong>{comparison.deterministic21.artifactId}</strong></header>
        <div><section><h3>Single-prompt fixture</h3><ul>{comparison.deterministic21.baseline.map((item) => <li key={item}>{item}</li>)}</ul></section><section><h3>Full workflow fixture</h3><ul>{comparison.deterministic21.threadline.map((item) => <li key={item}>{item}</li>)}</ul></section></div>
        <p>{comparison.deterministic21.limitation}</p>
      </article>
      <div className="judge-evidence-bands"><article><span>{comparison.v1Holdout.label}</span><strong>{comparison.v1Holdout.result}</strong><p>{comparison.v1Holdout.limitation}</p></article><article><span>{comparison.archivedLiveV2.label}</span><strong>{comparison.archivedLiveV2.extraction}</strong><strong>{comparison.archivedLiveV2.falseMerges}</strong><p>{comparison.archivedLiveV2.limitation}</p></article></div>
      <p className="judge-artifact-reference">Artifact {judgeEvidence.releaseArtifact.artifactId} · {judgeEvidence.releaseArtifact.source}</p>
      <p className="judge-final-thesis">The baseline produced an answer. THREADLINE produced an auditable boundary around what the evidence can support.</p>
    </div>
  );
}
