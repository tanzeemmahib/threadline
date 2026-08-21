"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { ConnectionState, ThreadButton, ThreadLink, ThreadTrace } from "@/components/thread-motion";
import type { ReveriePromptLabArtifact, SubmissionResultsArtifact } from "@/lib/reverie-evidence";

type WinningStory = ReveriePromptLabArtifact["winning_story"];
type PromptLabCase = ReveriePromptLabArtifact["cases"][number];
type JudgeComparison = SubmissionResultsArtifact["judge_case_comparison"];
type LiveEvidence = SubmissionResultsArtifact["archived_live_prompt_v2"];

const scenes = [
  { label: "Human stakes", summary: "Three organizations. Three incomplete records. One person—and one dangerously similar rival.", cue: "Name the two possible paths before explaining any architecture. Ask which records belong together.", seconds: 14 },
  { label: "One-shot baseline", summary: "The same complete packet reaches a plausible answer before contradictions are independently gated.", cue: "Point to the shared input digest, then the missing exact citations and rival contradiction.", seconds: 15 },
  { label: "Source-cited extraction", summary: "Original text stays intact while Prompt V2 evidence and deterministic representations remain separable.", cue: "Open one exact source span. Then show the Arabic and English evidence track without calling it a live comparison.", seconds: 17 },
  { label: "Supported thread", summary: "The family and shelter records form a possible connection eligible only for authorized review.", cue: "Stress that compatible fields support review; they do not confirm a person or fill missing evidence.", seconds: 14 },
  { label: "Conflict gate", summary: "A document-backed age conflict stops the hospital rival. The model cannot override the rule.", cue: "Open both age sources. The deterministic policy—not the model—closes this candidate path.", seconds: 18 },
  { label: "Measured proof", summary: "The handoff, artifact hashes, and evaluation limits remain visible at the decision boundary.", cue: "Close on one recovered connection, one prevented false merge, and the synthetic one-run limitation.", seconds: 14 },
] as const;

const sceneStartSeconds = scenes.map((_, index) => scenes.slice(0, index).reduce((total, scene) => total + scene.seconds, 0));
const presentationSeconds = scenes.reduce((total, scene) => total + scene.seconds, 0);

function formatClock(milliseconds: number) {
  const totalSeconds = Math.min(presentationSeconds, Math.max(0, Math.floor(milliseconds / 1000)));
  return `${String(Math.floor(totalSeconds / 60)).padStart(2, "0")}:${String(totalSeconds % 60).padStart(2, "0")}`;
}

function isNestedInteractive(target: EventTarget | null) {
  return target instanceof Element && Boolean(target.closest("button, a, input, select, textarea, summary, dialog, [role='dialog'], [contenteditable='true']"));
}

export function ReverieJudgeMode({
  story,
  comparison,
  live,
  crossScriptCase,
  presentation = false,
}: {
  story: WinningStory;
  comparison: JudgeComparison;
  live: LiveEvidence;
  crossScriptCase: PromptLabCase;
  presentation?: boolean;
}) {
  const [step, setStep] = useState(0);
  const [sourceSpanId, setSourceSpanId] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [cuesVisible, setCuesVisible] = useState(true);
  const [elapsedMilliseconds, setElapsedMilliseconds] = useState(0);
  const [reducedMotion, setReducedMotion] = useState(false);
  const sourceTriggerRef = useRef<HTMLButtonElement | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const sceneHeadingRef = useRef<HTMLHeadingElement>(null);
  const previousTickRef = useRef<number | null>(null);
  const elapsedRef = useRef(0);
  const activeSpan = story.source_spans.find((span) => span.span_id === sourceSpanId);
  const activeRecord = story.records.find((record) => record.record_id === activeSpan?.record_id);
  const scene = scenes[step];
  const presentationProgress = useMemo(() => Math.min(1, elapsedMilliseconds / (presentationSeconds * 1000)), [elapsedMilliseconds]);
  const playbackLabel = reducedMotion
    ? "Manual timing"
    : playing
      ? "Pause"
      : elapsedMilliseconds >= presentationSeconds * 1000
        ? "Replay"
        : elapsedMilliseconds > 0
          ? "Resume"
          : "Autoplay";

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => {
      setReducedMotion(media.matches);
      if (media.matches) setPlaying(false);
    };
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (sourceSpanId) dialogRef.current?.showModal();
  }, [sourceSpanId]);

  useEffect(() => {
    if (!presentation || !playing || reducedMotion) {
      previousTickRef.current = null;
      return;
    }

    previousTickRef.current = performance.now();
    const timer = window.setInterval(() => {
      const now = performance.now();
      const previous = previousTickRef.current ?? now;
      previousTickRef.current = now;
      const nextElapsed = Math.min(presentationSeconds * 1000, elapsedRef.current + now - previous);
      elapsedRef.current = nextElapsed;
      setElapsedMilliseconds(nextElapsed);
      const elapsedSeconds = nextElapsed / 1000;
      const timedStep = sceneStartSeconds.reduce((active, start, index) => elapsedSeconds >= start ? index : active, 0);
      setStep((current) => current === timedStep ? current : timedStep);
      if (elapsedSeconds >= presentationSeconds) setPlaying(false);
    }, 200);
    return () => window.clearInterval(timer);
  }, [playing, presentation, reducedMotion]);

  function closeSource() {
    dialogRef.current?.close();
  }

  function chooseStep(nextStep: number, focusHeading = false, alignTimer = true) {
    const safeStep = Math.min(scenes.length - 1, Math.max(0, nextStep));
    setStep(safeStep);
    if (presentation && alignTimer) {
      const nextElapsed = sceneStartSeconds[safeStep] * 1000;
      elapsedRef.current = nextElapsed;
      setElapsedMilliseconds(nextElapsed);
    }
    if (focusHeading) window.requestAnimationFrame(() => sceneHeadingRef.current?.focus());
  }

  function restartPresentation(focusHeading = true) {
    setPlaying(false);
    elapsedRef.current = 0;
    setElapsedMilliseconds(0);
    chooseStep(0, focusHeading, false);
  }

  function togglePlayback() {
    if (reducedMotion) return;
    if (elapsedMilliseconds >= presentationSeconds * 1000) restartPresentation(false);
    setPlaying((current) => !current);
  }

  function openSource(spanId: string, trigger: HTMLButtonElement) {
    setPlaying(false);
    sourceTriggerRef.current = trigger;
    setSourceSpanId(spanId);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.altKey || event.ctrlKey || event.metaKey || isNestedInteractive(event.target)) return;
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      chooseStep(step - 1, true);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      chooseStep(step + 1, true);
    } else if (event.key === "Home") {
      event.preventDefault();
      chooseStep(0, true);
    } else if (event.key === "End") {
      event.preventDefault();
      chooseStep(scenes.length - 1, true);
    } else if (presentation && (event.key === " " || event.code === "Space")) {
      event.preventDefault();
      togglePlayback();
    } else if (presentation && event.shiftKey && event.key.toLowerCase() === "r") {
      event.preventDefault();
      restartPresentation();
    }
  }

  return (
    <section className={`reverie-judge${presentation ? " reverie-judge--present" : ""}`} aria-labelledby="reverie-judge-title" onKeyDown={handleKeyDown}>
      {presentation ? (
        <div className="reverie-presentation-bar" aria-label="Presentation controls">
          <div className="reverie-presentation-bar__identity"><span>THREADLINE / JUDGE PRESENTATION</span><strong>{String(step + 1).padStart(2, "0")} / {String(scenes.length).padStart(2, "0")}</strong></div>
          <div className="reverie-presentation-bar__clock">
            <time aria-label={`Presentation elapsed ${formatClock(elapsedMilliseconds)} of ${formatClock(presentationSeconds * 1000)}`} dateTime={`PT${Math.floor(elapsedMilliseconds / 1000)}S`}>{formatClock(elapsedMilliseconds)} / {formatClock(presentationSeconds * 1000)}</time>
            <span aria-hidden="true"><i style={{ transform: `scaleX(${presentationProgress})` }} /></span>
          </div>
          <div className="reverie-presentation-bar__actions">
            <ThreadButton variant="quiet" motion="quiet" type="button" disabled={reducedMotion} aria-pressed={playing} onClick={togglePlayback}>{playbackLabel}</ThreadButton>
            <ThreadButton variant="quiet" motion="quiet" type="button" aria-controls="reverie-presenter-cue" aria-expanded={cuesVisible} onClick={() => setCuesVisible((visible) => !visible)}>{cuesVisible ? "Hide cues" : "Show cues"}</ThreadButton>
            <ThreadLink variant="text" motion="quiet" href="/demo">Exit</ThreadLink>
          </div>
        </div>
      ) : null}

      {presentation && cuesVisible ? (
        <aside className="reverie-presentation-cue" id="reverie-presenter-cue" aria-label="Presenter cue" aria-live="polite">
          <span>Speaker cue / {scene.seconds}s</span><p>{scene.cue}</p>
        </aside>
      ) : null}

      <header className="reverie-judge__masthead">
        <div>
          <p className="eyebrow">THREADLINE / evidence case 01</p>
          <h1 id="reverie-judge-title">Same records.<br />Different workflow.</h1>
        </div>
        <dl>
          <div><dt>Case</dt><dd>{story.case_id}</dd></div>
          <div><dt>Mode</dt><dd>Deterministic synthetic replay</dd></div>
          <div><dt>Scope</dt><dd>No autonomous identity decision</dd></div>
        </dl>
      </header>

      <nav className="reverie-judge__rail" aria-label="Evidence case scenes">
        {scenes.map(({ label }, index) => (
          <button key={label} type="button" aria-current={step === index ? "step" : undefined} onClick={() => chooseStep(index, true)}>
            <span>{String(index + 1).padStart(2, "0")}</span><strong>{label}</strong>
          </button>
        ))}
      </nav>

      <div className="reverie-judge__stage">
        <header className="reverie-judge__scene-heading" aria-live="polite" aria-atomic="true">
          <p>{String(step + 1).padStart(2, "0")} / {String(scenes.length).padStart(2, "0")}</p>
          <h2 ref={sceneHeadingRef} tabIndex={-1}>{scene.label}</h2>
          <span>{scene.summary}</span>
        </header>
        <div className="reverie-judge__scene" data-reverie-scene={step}>
          {step === 0 ? <HumanStakes story={story} /> : null}
          {step === 1 ? <BaselineScene comparison={comparison} /> : null}
          {step === 2 ? <ExtractionScene story={story} crossScriptCase={crossScriptCase} onOpenSource={openSource} /> : null}
          {step === 3 ? <SupportedScene story={story} onOpenSource={openSource} /> : null}
          {step === 4 ? <BlockedScene story={story} onOpenSource={openSource} /> : null}
          {step === 5 ? <ProofScene story={story} comparison={comparison} live={live} /> : null}
        </div>
      </div>

      <footer className="reverie-judge__controls">
        <p>{presentation ? "←/→ scenes · Space pause/resume · Home/End jump · Shift+R restart" : "Left/Right Arrow changes scene · Home/End jumps"} · all identities are fictional.</p>
        <div>
          <ThreadButton variant="quiet" motion="quiet" type="button" onClick={() => presentation ? restartPresentation() : chooseStep(0, true)}>{presentation ? "Restart" : "Reset"}</ThreadButton>
          <ThreadButton variant="secondary" motion="connect" type="button" disabled={step === 0} onClick={() => chooseStep(step - 1, true)}>Back</ThreadButton>
          {step < scenes.length - 1 ? (
            <ThreadButton variant="primary" motion="signature" arrow="forward" type="button" onClick={() => chooseStep(step + 1, true)}>Next evidence</ThreadButton>
          ) : (
            <ThreadLink variant="primary" motion="signature" arrow="forward" bridge href="/prompt-lab">Compare the prompts</ThreadLink>
          )}
        </div>
      </footer>

      <dialog
        className="reverie-source-dialog"
        ref={dialogRef}
        aria-labelledby="reverie-source-dialog-title"
        aria-describedby="reverie-source-dialog-description"
        onCancel={(event) => { event.preventDefault(); closeSource(); }}
        onClose={() => {
          setSourceSpanId(null);
          window.requestAnimationFrame(() => sourceTriggerRef.current?.focus());
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            closeSource();
          }
        }}
      >
        <div className="reverie-source-dialog__head">
          <div><span>Exact source span</span><strong id="reverie-source-dialog-title">{activeSpan?.span_id ?? "No span selected"}</strong></div>
          <ThreadButton variant="quiet" motion="quiet" type="button" aria-label="Close source evidence" onClick={closeSource}>Close</ThreadButton>
        </div>
        {activeSpan && activeRecord ? (
          <div>
            <dl><div><dt>Record</dt><dd>{activeRecord.record_id}</dd></div><div><dt>Field</dt><dd>{activeSpan.field}</dd></div><div><dt>Offsets</dt><dd>{activeSpan.start}–{activeSpan.end}</dd></div><div><dt>Validation</dt><dd>{activeSpan.valid ? "Exact substring verified" : "Invalid"}</dd></div></dl>
            <blockquote>{activeRecord.text.slice(0, activeSpan.start)}<mark>{activeRecord.text.slice(activeSpan.start, activeSpan.end)}</mark>{activeRecord.text.slice(activeSpan.end)}</blockquote>
            <p id="reverie-source-dialog-description">Quoted span: <strong>{activeSpan.quote}</strong></p>
          </div>
        ) : <p id="reverie-source-dialog-description">No source evidence is available.</p>}
      </dialog>
    </section>
  );
}

function HumanStakes({ story }: { story: WinningStory }) {
  return (
    <div className="reverie-human-stakes">
      <div className="reverie-human-stakes__records">
        {story.records.map((record, index) => (
          <article key={record.record_id} className={index === 2 ? "is-rival" : undefined}>
            <span>{record.source_type.replaceAll("_", " ")} · {record.record_id}</span>
            <h3>{record.text.match(/Youssef Al Hassan/)?.[0] ?? record.record_id}</h3>
            <p>{index === 0 ? "Family report · age 14 · last seen 16:30" : index === 1 ? "Shelter intake · age 14 · arrived 19:10" : "Hospital intake · document says age 24 · admitted 18:50"}</p>
          </article>
        ))}
      </div>
      <div className="reverie-human-stakes__question">
        <ConnectionState state="fragmented" label="Three records remain separate before evidence is compared" />
        <div><span>Investigation question</span><h3>Which records support a possible connection—and which one must be blocked?</h3></div>
      </div>
      <p className="reverie-language-note">{story.language_limitation}</p>
    </div>
  );
}

function BaselineScene({ comparison }: { comparison: JudgeComparison }) {
  const baseline = comparison.systems.generic;
  return (
    <div className="reverie-baseline">
      <div className="reverie-baseline__manifest">
        <div><span>Prompt</span><strong>{comparison.prompts.generic_baseline.template_id} · {comparison.prompts.generic_baseline.version}</strong></div>
        <div><span>Model / mode</span><strong>{comparison.provider.model} · {comparison.provider.mode}</strong></div>
        <div><span>Temperature</span><strong>{comparison.provider.temperature.toFixed(1)}</strong></div>
        <div><span>Input proof</span><strong>{comparison.case.input_manifest.input_sha256.slice(0, 16)}…</strong></div>
      </div>
      <div className="reverie-baseline__answer">
        <div><span>Structured answer</span><h3>{baseline.classification.replaceAll("_", " ")}</h3><p>{baseline.candidate_record_ids.join(" ↔ ")}</p></div>
        <dl><div><dt>Exact citations</dt><dd>{baseline.citations.length}</dd></div><div><dt>Contradictions returned</dt><dd>{baseline.output.contradictions.length}</dd></div><div><dt>Same complete input</dt><dd>{comparison.same_input_verification.exact_input_shared ? "Verified" : "No"}</dd></div></dl>
      </div>
      <details>
        <summary>Inspect exact prompt and raw structured response</summary>
        <div className="reverie-baseline__technical"><blockquote>{comparison.prompts.generic_baseline.content}</blockquote><pre>{JSON.stringify(baseline.output, null, 2)}</pre></div>
      </details>
      <p className="reverie-boundary-note">{comparison.provider.warning} The limitation is real: the answer looks plausible, but it contains no exact source citation or explicit rival contradiction.</p>
    </div>
  );
}

type OpenSource = (spanId: string, trigger: HTMLButtonElement) => void;

function ExtractionScene({ story, crossScriptCase, onOpenSource }: { story: WinningStory; crossScriptCase: PromptLabCase; onOpenSource: OpenSource }) {
  const candidate = story.candidates.find((item) => item.candidate_id === "MATCH-001") ?? story.candidates[0];
  const factors = candidate.compatibility_factors.filter((factor) => ["full_name", "age", "distinguishing_marks"].includes(factor.field));
  return (
    <div className="reverie-extraction">
      <div className="reverie-extraction__legend"><span>ORIGINAL SOURCE</span><i aria-hidden="true" /><span>STRUCTURED FIELD</span><i aria-hidden="true" /><span>DETERMINISTIC REPRESENTATION</span></div>
      {factors.map((factor) => (
        <article key={factor.factor_id}>
          <div><span>{factor.field.replaceAll("_", " ")}</span><strong>{factor.record_a_value}</strong></div>
          <ThreadTrace state="partial" />
          <div><span>{factor.interpretation}</span><strong>{factor.record_b_value}</strong></div>
          <div className="reverie-extraction__sources">
            {factor.evidence_span_ids.map((spanId) => <button key={spanId} type="button" onClick={(event) => onOpenSource(spanId, event.currentTarget)}>{spanId} ↗</button>)}
          </div>
        </article>
      ))}
      <p>Missing values remain missing. Normalized representations never replace the source text.</p>
      <CrossScriptProof item={crossScriptCase} />
    </div>
  );
}

function CrossScriptProof({ item }: { item: PromptLabCase }) {
  const [nativeRecord, latinRecord] = item.records;
  const candidate = item.systems.threadline.candidate;
  const nameFactor = candidate.compatibility_factors.find((factor) => factor.field === "full_name");
  const nativeName = nativeRecord.archived_live_v2_extraction.fields.find((field) => field.key === "name");
  const latinName = latinRecord.archived_live_v2_extraction.fields.find((field) => field.key === "name");

  return (
    <aside className="reverie-cross-script" aria-labelledby="reverie-cross-script-title">
      <header>
        <div><span>Archived Prompt V2 extraction / separate evidence track</span><h3 id="reverie-cross-script-title">Cross-script evidence stays attached to both sources.</h3></div>
        <strong>{item.decision.state.replaceAll("_", " ")}</strong>
      </header>
      <div className="reverie-cross-script__path">
        <article>
          <span>{nativeRecord.record_id} / exact source</span>
          <b lang="ar" dir="rtl">{nativeName?.value ?? nativeRecord.display_name}</b>
          <small>{nativeRecord.archived_live_v2_extraction.supported_field_keys.length} supported extracted fields · Prompt {nativeRecord.archived_live_v2_extraction.prompt_version.toUpperCase()}</small>
        </article>
        <div aria-label="Derived transliteration and normalization, supporting evidence only—not identity confirmation"><ThreadTrace state="partial" /><span>derived transliteration / normalization</span></div>
        <article>
          <span>{latinRecord.record_id} / exact source</span>
          <b lang="en">{latinName?.value ?? latinRecord.display_name}</b>
          <small>{latinRecord.archived_live_v2_extraction.supported_field_keys.length} supported extracted fields · Prompt {latinRecord.archived_live_v2_extraction.prompt_version.toUpperCase()}</small>
        </article>
      </div>
      <p><span>Deterministic comparison</span>{nameFactor?.interpretation ?? "Cross-script name evidence remains supporting evidence."}{" "}Missing government ID and complete date of birth keep the disposition at authorized human review.</p>
    </aside>
  );
}

function SupportedScene({ story, onOpenSource }: { story: WinningStory; onOpenSource: OpenSource }) {
  const candidate = story.candidates.find((item) => item.candidate_id === "MATCH-001") ?? story.candidates[0];
  const contract = story.evidence_contracts.find((item) => item.candidate_id === candidate.candidate_id);
  const support = candidate.compatibility_factors.filter((factor) => factor.status === "compatible").slice(0, 4);
  return (
    <div className="reverie-supported">
      <div className="reverie-supported__connection">
        <article><span>FAMILY-018</span><strong>Youssef Al Hassan</strong><p>Age 14 · estimated last-seen time</p></article>
        <ConnectionState state="partial" label="Possible record connection supported for authorized human review" announce />
        <article><span>SHELTER-204</span><strong>Youssef Al Hassan</strong><p>Age 14 · direct shelter intake</p></article>
      </div>
      <ul>{support.map((factor) => <li key={factor.factor_id}><span>{factor.field.replaceAll("_", " ")}</span><strong>{factor.interpretation}</strong><button type="button" onClick={(event) => onOpenSource(factor.evidence_span_ids[0], event.currentTarget)}>Source ↗</button></li>)}</ul>
      <div className="reverie-supported__boundary"><span>{contract?.contract_status.replaceAll("_", " ")}</span><strong>Possible connection prepared for authorized review</strong><p>This is a supported candidate thread, not an identity confirmation or autonomous merge.</p></div>
    </div>
  );
}

function BlockedScene({ story, onOpenSource }: { story: WinningStory; onOpenSource: OpenSource }) {
  const candidate = story.candidates.find((item) => item.candidate_id === "MATCH-002") ?? story.candidates[1];
  const contract = story.evidence_contracts.find((item) => item.candidate_id === candidate.candidate_id);
  const blockingRules = contract?.rule_results.filter((rule) => rule.status === "block") ?? [];
  const ageSpans = story.source_spans.filter((span) => ["SPAN-FAMILY-018-AGE-37", "SPAN-HOSPITAL-052-AGE-36"].includes(span.span_id));
  return (
    <div className="reverie-blocked">
      <header><span>Dangerously similar rival</span><h3>FAMILY-018 ↔ HOSPITAL-052</h3><p>Same stated name. Incompatible document-backed age.</p></header>
      <div className="reverie-blocked__comparison">
        {ageSpans.map((span, index) => <button key={span.span_id} type="button" onClick={(event) => onOpenSource(span.span_id, event.currentTarget)}><span>{span.record_id}</span><strong>{span.quote}</strong><small>{index === 0 ? "family report" : "presented identity card"} · open source ↗</small></button>)}
        <ConnectionState state="interrupted" label="Deterministic identity conflict interrupts the candidate path" announce />
      </div>
      <div className="reverie-blocked__gate">
        <div><span>BLOCKED</span><h3>Deterministic identity conflict</h3><p>The LLM cannot suppress or upgrade this result.</p></div>
        <ul>{blockingRules.map((rule) => <li key={rule.rule_id}><span>{rule.rule_id}</span><strong>{rule.reason_code}</strong></li>)}</ul>
      </div>
    </div>
  );
}

function ProofScene({ story, comparison, live }: { story: WinningStory; comparison: JudgeComparison; live: LiveEvidence }) {
  const supportedContract = story.evidence_contracts.find((item) => item.candidate_id === "MATCH-001");
  const blockedContract = story.evidence_contracts.find((item) => item.candidate_id === "MATCH-002");
  return (
    <div className="reverie-proof">
      <div className="reverie-proof__outcomes">
        <article><span>POSSIBLE CONNECTION</span><strong>FAMILY-018 ↔ SHELTER-204</strong><p>{supportedContract?.contract_status.replaceAll("_", " ")} · human disposition required</p></article>
        <article className="is-blocked"><span>RIVAL STOPPED</span><strong>FAMILY-018 ↔ HOSPITAL-052</strong><p>{blockedContract?.contract_status} · age conflict retained</p></article>
      </div>
      <div className="reverie-proof__ledger">
        <dl><div><dt>Same-input SHA-256</dt><dd>{comparison.case.input_manifest.input_sha256}</dd></div><div><dt>Available-evidence SHA-256</dt><dd>{comparison.case.input_manifest.available_evidence_sha256}</dd></div><div><dt>Evidence contract</dt><dd>{supportedContract?.candidate_id} / {blockedContract?.candidate_id}</dd></div><div><dt>Human review</dt><dd>Required before any disposition</dd></div></dl>
        <div><span>ARCHIVED LIVE PROMPT V2 / SEPARATE EVIDENCE TRACK</span><strong>{live.extraction_quality.records_ok} / {live.extraction_quality.records_total}</strong><p>schema-valid extraction outputs · {live.decision_metrics.false_merge_count} / {live.decision_metrics.different_identity_pairs} observed false merges · synthetic one-run limitation</p></div>
      </div>
      <p className="reverie-proof__climax">{story.climax}</p>
      <div className="reverie-proof__actions"><ThreadLink variant="secondary" motion="connect" arrow="forward" bridge href="/demo?workspace=1">Open the technical workspace</ThreadLink><ThreadLink variant="text" motion="quiet" arrow="forward" bridge href="/prompt-lab">Inspect Prompt V1 / V2 / V3</ThreadLink></div>
    </div>
  );
}
