"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import { ConnectionState } from "@/components/thread-motion";
import { StatusPill } from "@/components/status-pill";
import type { ReverieLiveEvaluationRunSummary, ReverieLiveEvaluationState, ReveriePromptLabArtifact } from "@/lib/reverie-evidence";

type PromptLabCase = ReveriePromptLabArtifact["cases"][number];
type PromptLabSystem = PromptLabCase["systems"]["one_shot"] | PromptLabCase["systems"]["threadline"];
type PromptCohort = ReveriePromptLabArtifact["prompt_iterations"]["cohorts"][number];
type PromptRun = PromptCohort["runs"][number];
type PromptVersion = keyof ReveriePromptLabArtifact["prompt_iterations"]["prompts"];

type PromptDiffLine = {
  kind: "context" | "added" | "removed";
  line: string;
  leftNumber: number | null;
  rightNumber: number | null;
};


function titleCase(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function compactHash(value: string) {
  return `${value.slice(0, 10)}…${value.slice(-8)}`;
}

function percent(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}

function formatComparisonValue(key: string, value: boolean | number | string) {
  if (typeof value === "boolean") {
    if (key === "schema_validity") return value ? "Valid" : "Invalid";
    return value ? "Present" : "Absent";
  }
  if (typeof value === "number" && key === "source_span_coverage") return percent(value);
  return typeof value === "string" ? titleCase(value) : String(value);
}

function decisionCopy(item: PromptLabCase) {
  if (item.decision.state === "blocked_by_conflict") {
    return {
      state: "blocked",
      title: "BLOCKED — deterministic identity conflict",
      body: "A material date-of-birth conflict stops release. The prompt cannot override this rule.",
      tone: "red" as const,
    };
  }
  if (item.kind === "shared_contact_insufficient") {
    return {
      state: "insufficient",
      title: "Insufficient independent evidence — human review required",
      body: "The repeated phone number may identify a household, not a person. Missing evidence is not treated as agreement.",
      tone: "amber" as const,
    };
  }
  return {
    state: "review",
    title: "Possible connection supported for human review",
    body: "Cross-script name evidence remains supporting evidence only. The deterministic gate preserves the missing discriminators.",
    tone: "slate" as const,
  };
}

function connectionState(item: PromptLabCase) {
  if (item.decision.state === "blocked_by_conflict") return "interrupted" as const;
  return "partial" as const;
}

function JsonBlock({ value }: { value: unknown }) {
  return <pre className="prompt-lab-code">{JSON.stringify(value, null, 2)}</pre>;
}

function buildPromptDiff(leftText: string, rightText: string): PromptDiffLine[] {
  const left = leftText.replaceAll("\r\n", "\n").split("\n");
  const right = rightText.replaceAll("\r\n", "\n").split("\n");
  const table = Array.from({ length: left.length + 1 }, () => Array<number>(right.length + 1).fill(0));

  for (let leftIndex = left.length - 1; leftIndex >= 0; leftIndex -= 1) {
    for (let rightIndex = right.length - 1; rightIndex >= 0; rightIndex -= 1) {
      table[leftIndex][rightIndex] = left[leftIndex] === right[rightIndex]
        ? table[leftIndex + 1][rightIndex + 1] + 1
        : Math.max(table[leftIndex + 1][rightIndex], table[leftIndex][rightIndex + 1]);
    }
  }

  const diff: PromptDiffLine[] = [];
  let leftIndex = 0;
  let rightIndex = 0;
  while (leftIndex < left.length || rightIndex < right.length) {
    if (leftIndex < left.length && rightIndex < right.length && left[leftIndex] === right[rightIndex]) {
      diff.push({ kind: "context", line: left[leftIndex], leftNumber: leftIndex + 1, rightNumber: rightIndex + 1 });
      leftIndex += 1;
      rightIndex += 1;
    } else if (rightIndex < right.length && (leftIndex === left.length || table[leftIndex][rightIndex + 1] >= table[leftIndex + 1][rightIndex])) {
      diff.push({ kind: "added", line: right[rightIndex], leftNumber: null, rightNumber: rightIndex + 1 });
      rightIndex += 1;
    } else {
      diff.push({ kind: "removed", line: left[leftIndex], leftNumber: leftIndex + 1, rightNumber: null });
      leftIndex += 1;
    }
  }
  return diff;
}

function PromptDiff({ cohort, artifact }: { cohort: PromptCohort; artifact: ReveriePromptLabArtifact }) {
  const [leftVersion, rightVersion] = cohort.comparable_versions as [PromptVersion, PromptVersion];
  const leftPrompt = artifact.prompt_iterations.prompts[leftVersion];
  const rightPrompt = artifact.prompt_iterations.prompts[rightVersion];
  const diff = buildPromptDiff(leftPrompt.text, rightPrompt.text);
  const changedLines = diff.filter((line) => line.kind !== "context").length;

  return (
    <details className="prompt-lab-disclosure prompt-lab-prompt-diff">
      <summary>Inspect artifact-derived Prompt {leftVersion.toUpperCase()} → Prompt {rightVersion.toUpperCase()} diff <span>{changedLines} changed lines</span></summary>
      <div className="prompt-lab-disclosure__body">
        <dl className="prompt-lab-prompt-diff__provenance">
          <div><dt>From</dt><dd>Prompt {leftVersion.toUpperCase()} / {compactHash(leftPrompt.sha256)}</dd></div>
          <div><dt>To</dt><dd>Prompt {rightVersion.toUpperCase()} / {compactHash(rightPrompt.sha256)}</dd></div>
        </dl>
        <div className="prompt-lab-prompt-diff__lines" role="region" aria-label={`Line diff from Prompt ${leftVersion.toUpperCase()} to Prompt ${rightVersion.toUpperCase()}`} tabIndex={0}>
          {diff.map((item, index) => {
            const content = <><span aria-hidden="true">{item.leftNumber ?? "·"}</span><span aria-hidden="true">{item.rightNumber ?? "·"}</span><code>{item.kind === "added" ? "+ " : item.kind === "removed" ? "− " : "  "}{item.line || " "}</code></>;
            if (item.kind === "added") return <ins key={`${item.kind}-${index}`}>{content}<span className="sr-only">Added in Prompt {rightVersion.toUpperCase()}</span></ins>;
            if (item.kind === "removed") return <del key={`${item.kind}-${index}`}>{content}<span className="sr-only">Removed from Prompt {leftVersion.toUpperCase()}</span></del>;
            return <div key={`${item.kind}-${index}`}>{content}</div>;
          })}
        </div>
      </div>
    </details>
  );
}

function average(values: number[]) {
  return values.length ? values.reduce((total, value) => total + value, 0) / values.length : null;
}

function LiveRunDisclosure({ item }: { item: Extract<ReverieLiveEvaluationState, { state: "complete" }>["artifact"]["cases"][number] }) {
  const oneShot = item.systems.structured_one_shot;
  const threadline = item.systems.full_threadline;
  const metricRows: Array<[string, (run: ReverieLiveEvaluationRunSummary | undefined) => string]> = [
    ["Schema validity", (run) => run?.metrics ? run.metrics.schema_valid ? "Valid" : "Invalid" : titleCase(run?.status ?? "Not run")],
    ["Source-span coverage", (run) => run?.metrics?.source_span_coverage == null ? "Not measured" : percent(run.metrics.source_span_coverage)],
    ["Supported fields", (run) => run?.metrics ? String(run.metrics.supported_field_count) : "Not recorded"],
    ["Unsupported fields", (run) => run?.metrics ? String(run.metrics.unsupported_field_count) : "Not recorded"],
    ["Exact citations", (run) => run?.metrics ? String(run.metrics.exact_citation_count) : "Not recorded"],
    ["Latency", (run) => run?.metrics ? `${Math.round(run.metrics.latency_ms).toLocaleString()} ms` : "Not recorded"],
    ["Token usage", (run) => run?.metrics?.token_usage == null ? "Not recorded" : run.metrics.token_usage.toLocaleString()],
    ["Identity outcome", (run) => run?.metrics ? titleCase(run.metrics.identity_outcome) : titleCase(run?.status ?? "Not run")],
  ];

  return (
    <details className="prompt-lab-live-run">
      <summary><span>{item.case_id} / repetition {String(item.repetition).padStart(2, "0")}</span><strong>{oneShot?.metrics ? titleCase(oneShot.metrics.identity_outcome) : titleCase(oneShot?.status ?? "Not run")} → {threadline?.metrics ? titleCase(threadline.metrics.identity_outcome) : titleCase(threadline?.status ?? "Not run")}</strong></summary>
      <div className="prompt-lab-live-run__body">
        <div className="prompt-lab-live-run__table" role="region" aria-label={`${item.case_id} repetition ${item.repetition} live metrics`} tabIndex={0}>
          <table className="prompt-lab-table"><thead><tr><th scope="col">Measured dimension</th><th scope="col">Structured one-shot</th><th scope="col">Full THREADLINE</th></tr></thead><tbody>{metricRows.map(([label, read]) => <tr key={label}><th scope="row">{label}</th><td>{read(oneShot)}</td><td>{read(threadline)}</td></tr>)}</tbody></table>
        </div>
        <div className="prompt-lab-live-run__downloads">
          {[oneShot, threadline].map((run) => run?.technical_output_sha256 ? <a key={run.system_run_id} href={`/prompt-lab/live-output/${encodeURIComponent(run.system_run_id)}`} target="_blank" rel="noreferrer"><span>{run.system_run_id}</span><strong>Download sanitized raw + validated output ↗</strong><small>SHA-256 / {run.technical_output_sha256}</small></a> : null)}
        </div>
      </div>
    </details>
  );
}

function LiveComparisonPanel({ liveEvaluation }: { liveEvaluation: ReverieLiveEvaluationState }) {
  const complete = liveEvaluation.state === "complete" ? liveEvaluation.artifact : null;
  const stateMessage = liveEvaluation.state === "complete" ? "" : liveEvaluation.message;
  const comparableRuns = complete?.cases.filter((item) => {
    const oneShot = item.systems.structured_one_shot;
    const threadline = item.systems.full_threadline;
    return oneShot?.status === "ok"
      && threadline?.status === "ok"
      && oneShot.same_input_verified
      && threadline.same_input_verified
      && oneShot.metrics
      && threadline.metrics;
  }) ?? [];
  const summarize = (system: "structured_one_shot" | "full_threadline") => {
    const metrics = comparableRuns.flatMap((item) => {
      const run = item.systems[system];
      return run?.metrics ? [run.metrics] : [];
    });
    return {
      runs: metrics.length,
      schemaValid: metrics.filter((item) => item.schema_valid).length,
      sourceSpanCoverage: average(metrics.flatMap((item) => item.source_span_coverage == null ? [] : [item.source_span_coverage])),
      supportedFields: metrics.reduce((total, item) => total + item.supported_field_count, 0),
      exactCitations: metrics.reduce((total, item) => total + item.exact_citation_count, 0),
      unsupportedFields: metrics.reduce((total, item) => total + item.unsupported_field_count, 0),
    };
  };
  const oneShot = summarize("structured_one_shot");
  const threadline = summarize("full_threadline");

  return (
    <section className="prompt-lab-live shell" aria-labelledby="prompt-live-title">
      <div className="prompt-lab-heading">
        <div><p className="eyebrow">Same-model live comparison</p><h2 className="section-title" id="prompt-live-title">A live claim appears only when a locked comparable artifact exists.</h2></div>
        <p>Recorded deterministic cases and archived extraction runs remain separate evidence tracks. Neither is relabeled as a live head-to-head run.</p>
      </div>
      {complete ? (
        <article className="prompt-lab-live__available">
          <header><div><span>LIVE MODEL PERFORMANCE / {complete.evaluation_label} / {complete.spec_id}</span><h3>{complete.provider.model} / {complete.completed_system_runs} of {complete.expected_system_runs} system runs complete</h3></div><StatusPill tone="amber">Same input + config verified</StatusPill></header>
          <div>
            <dl><div><dt>One-shot comparable runs</dt><dd>{oneShot.runs}</dd></div><div><dt>Schema-valid</dt><dd>{oneShot.schemaValid} / {oneShot.runs}</dd></div><div><dt>Coverage / mean</dt><dd>{oneShot.sourceSpanCoverage == null ? "Not measured" : percent(oneShot.sourceSpanCoverage)}</dd></div><div><dt>Supported / total · mean</dt><dd>{oneShot.supportedFields} · {(oneShot.supportedFields / oneShot.runs).toFixed(2)}</dd></div><div><dt>Unsupported / total · mean</dt><dd>{oneShot.unsupportedFields} · {(oneShot.unsupportedFields / oneShot.runs).toFixed(2)}</dd></div><div><dt>Exact citations / total · mean</dt><dd>{oneShot.exactCitations} · {(oneShot.exactCitations / oneShot.runs).toFixed(2)}</dd></div></dl>
            <dl><div><dt>THREADLINE comparable runs</dt><dd>{threadline.runs}</dd></div><div><dt>Schema-valid</dt><dd>{threadline.schemaValid} / {threadline.runs}</dd></div><div><dt>Coverage / mean</dt><dd>{threadline.sourceSpanCoverage == null ? "Not measured" : percent(threadline.sourceSpanCoverage)}</dd></div><div><dt>Supported / total · mean</dt><dd>{threadline.supportedFields} · {(threadline.supportedFields / threadline.runs).toFixed(2)}</dd></div><div><dt>Unsupported / total · mean</dt><dd>{threadline.unsupportedFields} · {(threadline.unsupportedFields / threadline.runs).toFixed(2)}</dd></div><div><dt>Exact citations / total · mean</dt><dd>{threadline.exactCitations} · {(threadline.exactCitations / threadline.runs).toFixed(2)}</dd></div></dl>
          </div>
          <div className="prompt-lab-live__runs" role="region" aria-label="Measured live comparison case outcomes" tabIndex={0}>{complete.cases.map((item) => <LiveRunDisclosure item={item} key={`${item.case_id}-${item.repetition}`} />)}</div>
          <p>{complete.limitations.join(" ")} Artifact SHA-256 {compactHash(complete.artifact_sha256)} · spec {compactHash(complete.spec_sha256)} · recorder {compactHash(complete.recorder_artifact_sha256)}.</p>
        </article>
      ) : liveEvaluation.state === "incomplete" ? (
        <aside className="prompt-lab-live__unavailable" data-state="incomplete" role="note">
          <div><span>INCOMPLETE / {liveEvaluation.artifact.status}</span><strong>Measured comparison remains withheld.</strong></div>
          <p>{liveEvaluation.message} Progress: {liveEvaluation.artifact.completed_system_runs} completed, {liveEvaluation.artifact.failed_system_runs} failed, {liveEvaluation.artifact.expected_system_runs} expected.</p>
        </aside>
      ) : liveEvaluation.state === "invalid" ? (
        <aside className="prompt-lab-live__unavailable" data-state="invalid" role="alert">
          <div><span>ARTIFACT INVALID</span><strong>Measured comparison remains withheld.</strong></div>
          <p>{liveEvaluation.message} No partial metrics or model outputs are displayed.</p>
        </aside>
      ) : (
        <aside className="prompt-lab-live__unavailable" role="note">
          <div><span>NOT MEASURED</span><strong>No locked same-model live one-shot versus workflow artifact is present.</strong></div>
          <p>{stateMessage} The case laboratory above uses deterministic replays, while the Prompt V1/V2/V3 section uses separately archived provider extraction runs. THREADLINE does not merge those evidence tracks into a comparison they cannot support.</p>
        </aside>
      )}
    </section>
  );
}

function SystemDisclosures({ system, workflow }: { system: PromptLabSystem; workflow: boolean }) {
  return (
    <div className="prompt-lab-disclosures">
      <details className="prompt-lab-disclosure">
        <summary>Prompt and model configuration</summary>
        <div className="prompt-lab-disclosure__body">
          <dl>
            <div><dt>Template</dt><dd>{system.prompt.template_id} / {system.prompt.version}</dd></div>
            <div><dt>Prompt SHA-256</dt><dd title={system.prompt.sha256}>{compactHash(system.prompt.sha256)}</dd></div>
            <div><dt>Provider</dt><dd>{system.model_config.provider}</dd></div>
            <div><dt>Model</dt><dd>{system.model_config.model}</dd></div>
            <div><dt>Temperature</dt><dd>{system.model_config.temperature}</dd></div>
            <div><dt>Network required</dt><dd>{system.model_config.network_required ? "Yes" : "No — recorded deterministic replay"}</dd></div>
          </dl>
          <pre className="prompt-lab-code">{system.prompt.text}</pre>
        </div>
      </details>
      <details className="prompt-lab-disclosure">
        <summary>Raw model or replay output</summary>
        <div className="prompt-lab-disclosure__body"><JsonBlock value={system.raw_provider_output ?? { note: "No separate raw provider payload exists for this deterministic workflow replay." }} /></div>
      </details>
      <details className="prompt-lab-disclosure">
        <summary>Validated structured output</summary>
        <div className="prompt-lab-disclosure__body"><JsonBlock value={system.validated_structured_output} /></div>
      </details>
      <details className="prompt-lab-disclosure">
        <summary>{workflow ? "Deterministic comparison and evidence contract" : "Citation and audit boundary"}</summary>
        <div className="prompt-lab-disclosure__body">
          <JsonBlock value={workflow ? {
            candidate: "candidate" in system ? system.candidate : null,
            evidence_contract: "evidence_contract" in system ? system.evidence_contract : null,
            workflow_trace: "workflow_trace" in system ? system.workflow_trace : [],
          } : {
            metrics: system.metrics,
            cited_evidence: system.cited_evidence,
            limitation: "A parsed single response has no independent deterministic conflict gate.",
          }} />
        </div>
      </details>
    </div>
  );
}

function PromptIteration({ run, artifact }: { run: PromptRun; artifact: ReveriePromptLabArtifact }) {
  const version = run.prompt_version as keyof typeof artifact.prompt_iterations.prompt_summaries;
  const promotion = artifact.prompt_iterations.promotion_decision;
  const isProduction = run.prompt_version === promotion.production_version;
  const notPromoted = run.prompt_version === promotion.not_promoted;

  return (
    <article className="prompt-lab-iteration">
      <div className="prompt-lab-iteration__head">
        <div>
          <span className="prompt-lab-iteration__cohort">{run.run_id}</span>
          <h4>Prompt {run.prompt_version.toUpperCase()}</h4>
        </div>
        <StatusPill tone={notPromoted ? "red" : isProduction ? "amber" : "slate"}>
          {notPromoted ? "Not promoted" : isProduction ? "Production" : "Historical"}
        </StatusPill>
      </div>
      <dl>
        <div><dt>Extraction success</dt><dd>{run.extraction_quality.records_ok} / {run.extraction_quality.records_total}</dd></div>
        <div><dt>Precision</dt><dd>{percent(run.extraction_quality.micro_precision)}</dd></div>
        <div><dt>Recall</dt><dd>{percent(run.extraction_quality.micro_recall)}</dd></div>
        <div><dt>Micro-F1</dt><dd>{percent(run.extraction_quality.micro_f1)}</dd></div>
        <div><dt>False-positive fields</dt><dd>{run.extraction_quality.total_fp}</dd></div>
        <div><dt>False merges</dt><dd>{run.decision_metrics.false_merge_count}</dd></div>
        <div><dt>Conflict recall</dt><dd>{percent(run.decision_metrics.blocked_conflict_recall)}</dd></div>
        <div><dt>Records</dt><dd>{run.record_count}</dd></div>
        <div><dt>Temperature</dt><dd>{run.temperature}</dd></div>
      </dl>
      <p className="prompt-lab-iteration__change">{artifact.prompt_iterations.prompt_summaries[version]}</p>
    </article>
  );
}

export function PromptLab({ artifact, liveEvaluation }: { artifact: ReveriePromptLabArtifact; liveEvaluation: ReverieLiveEvaluationState }) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const tabsRef = useRef<Array<HTMLButtonElement | null>>([]);
  const activeCase = artifact.cases[selectedIndex];
  const decision = decisionCopy(activeCase);

  function selectTab(index: number, focus = false) {
    const next = (index + artifact.cases.length) % artifact.cases.length;
    setSelectedIndex(next);
    if (focus) tabsRef.current[next]?.focus();
  }

  function onTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.key === "ArrowRight") {
      event.preventDefault();
      selectTab(index + 1, true);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      selectTab(index - 1, true);
    } else if (event.key === "Home") {
      event.preventDefault();
      selectTab(0, true);
    } else if (event.key === "End") {
      event.preventDefault();
      selectTab(artifact.cases.length - 1, true);
    }
  }

  return (
    <>
      <section className="prompt-lab-hero shell" aria-labelledby="prompt-lab-title">
        <div className="prompt-lab-hero__copy">
          <p className="eyebrow">Prompt engineering / same input / visible boundary</p>
          <h1 className="page-title" id="prompt-lab-title">One record pair. Two reasoning paths. No hidden advantage.</h1>
          <p className="body-large">Compare a reasonable single call with THREADLINE&apos;s source-cited workflow. The model extracts evidence; deterministic rules decide when the system must stop.</p>
        </div>
        <aside className="prompt-lab-guardrail" role="note" aria-label="Prompt Lab evidence boundary">
          <StatusPill tone="amber">Synthetic research evidence</StatusPill>
          <strong>Every displayed result resolves to a locked artifact.</strong>
          <p>{artifact.safety_scope} The three case comparisons are recorded deterministic replays, not claims about live-model performance.</p>
        </aside>
      </section>

      <dl className="prompt-lab-artifact-rail shell" aria-label="Prompt Lab provenance">
        <div><dt>Artifact</dt><dd>{artifact.artifact_id}</dd></div>
        <div><dt>Schema</dt><dd>{artifact.schema_version}</dd></div>
        <div><dt>Evidence timestamp</dt><dd>{artifact.generated_at}</dd></div>
        <div><dt>Source artifacts</dt><dd>{Object.keys(artifact.source_artifacts).length} locked files</dd></div>
      </dl>

      <section className="prompt-lab-workbench shell" aria-labelledby="case-comparison-title">
        <div className="prompt-lab-heading">
          <div><p className="eyebrow">Reproducible case laboratory</p><h2 className="section-title" id="case-comparison-title">Where a single answer ends, the review boundary begins.</h2></div>
          <p>Each tab uses the exact same record text and available evidence for both systems. Open the technical layers only when you need them.</p>
        </div>

        <div className="prompt-lab-case-tabs" role="tablist" aria-label="Prompt comparison cases">
          {artifact.cases.map((item, index) => (
            <button
              className="prompt-lab-case-tab"
              id={`prompt-case-tab-${index}`}
              key={item.case_id}
              ref={(node) => { tabsRef.current[index] = node; }}
              role="tab"
              type="button"
              aria-controls={`prompt-case-panel-${index}`}
              aria-selected={selectedIndex === index}
              tabIndex={selectedIndex === index ? 0 : -1}
              onClick={() => selectTab(index)}
              onKeyDown={(event) => onTabKeyDown(event, index)}
            >
              <span>Case {String(index + 1).padStart(2, "0")} / {titleCase(item.kind)}</span>
              <strong>{item.title}</strong>
            </button>
          ))}
        </div>

        <div
          className="prompt-lab-case-panel"
          id={`prompt-case-panel-${selectedIndex}`}
          key={activeCase.case_id}
          role="tabpanel"
          aria-labelledby={`prompt-case-tab-${selectedIndex}`}
          tabIndex={0}
        >
          <div className="prompt-lab-case-intro">
            <div>
              <p className="prompt-lab-meta">{activeCase.case_id} / fixture {activeCase.fixture_incident_id}</p>
              <h3>{activeCase.title}</h3>
            </div>
            <p className="prompt-lab-question">{activeCase.question}</p>
          </div>

          <div className="prompt-lab-trace" aria-label="Source to workflow to review boundary">
            <span>01 / Same source records</span><span>02 / Two reasoning paths</span><span>03 / Deterministic boundary</span>
          </div>

          <div className="prompt-lab-records" aria-label="Exact synthetic input records">
            {activeCase.records.map((record) => (
              <article className="prompt-lab-record" key={record.record_id}>
                <header>
                  <div><p className="prompt-lab-meta">{record.record_id}</p><h4>{titleCase(record.source_type)}</h4></div>
                  <span>{record.language}<br />{record.timestamp}</span>
                </header>
                <blockquote lang={record.language === "Arabic" ? "ar" : "en"} dir={record.language === "Arabic" ? "rtl" : "ltr"}>{record.text}</blockquote>
              </article>
            ))}
          </div>

          <article className="prompt-lab-comparison">
            <header>
              <h4>Measured comparison</h4>
              <p>{activeCase.systems.one_shot.evaluation_label} Identical input digest verified: {activeCase.identical_input_verified ? "yes" : "no"}.</p>
            </header>
            <div className="prompt-lab-table-wrap" role="region" aria-label={`${activeCase.title} measured comparison`} tabIndex={0}>
              <table className="prompt-lab-table">
                <thead><tr><th scope="col">Evaluation dimension</th><th scope="col">One-shot baseline</th><th scope="col">THREADLINE workflow</th></tr></thead>
                <tbody>
                  {Object.entries(activeCase.comparison_dimensions).map(([key, values]) => (
                    <tr key={key}>
                      <th scope="row">{titleCase(key)}</th>
                      <td>{formatComparisonValue(key, values.one_shot)}</td>
                      <td>{formatComparisonValue(key, values.threadline)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>

          <div className="prompt-lab-system-grid">
            {([activeCase.systems.one_shot, activeCase.systems.threadline] as const).map((system, index) => (
              <article className="prompt-lab-system" key={system.system_id}>
                <div className="prompt-lab-system__header">
                  <div><span className="prompt-lab-system__meta">Path {index + 1} / {system.prompt.template_id} {system.prompt.version}</span><h4>{system.system_name}</h4></div>
                  <ConnectionState state={index === 0 ? "partial" : connectionState(activeCase)} label={index === 0 ? "Single response without independent policy gate" : decision.title} announce />
                </div>
                <p className="prompt-lab-system__outcome">{titleCase(index === 0 ? system.classification : activeCase.decision.state)}</p>
                <p className="prompt-lab-system__note">{index === 0 ? "One parsed response can cite the source, but it has no independent rule that can stop a plausible recommendation." : "The workflow keeps extraction, comparison, conflict policy, and human disposition as separate accountable stages."}</p>
                <SystemDisclosures system={system} workflow={index === 1} />
              </article>
            ))}
          </div>

          <section className="prompt-lab-evidence" aria-labelledby={`source-spans-${selectedIndex}`}>
            <div className="prompt-lab-heading">
              <div><p className="eyebrow">Exact claim-to-source lineage</p><h4 className="section-title" id={`source-spans-${selectedIndex}`}>The source text remains the evidence.</h4></div>
              <p>Normalized values and model output never overwrite these exact quotes and character offsets.</p>
            </div>
            <div className="prompt-lab-source-spans">
              {activeCase.source_spans.map((span) => (
                <article className="prompt-lab-source-span" key={span.span_id}>
                  <span className="prompt-lab-source-span__coordinates">{span.record_id} / chars {span.start}–{span.end}</span>
                  <h5>{span.field} / {span.certainty}</h5>
                  <blockquote>“{span.quote}”</blockquote>
                </article>
              ))}
            </div>
          </section>

          <aside className="prompt-lab-decision" data-state={decision.state} aria-live="polite">
            <div>
              <span className="prompt-lab-decision__label">Deterministic disposition / {activeCase.decision.reason_codes.join(" · ")}</span>
              <h4>{decision.title}</h4>
            </div>
            <div><StatusPill tone={decision.tone}>{activeCase.decision.release_allowed_for_authorized_review ? "Authorized review only" : "Release withheld"}</StatusPill><p>{decision.body} {activeCase.decision.safety_notice}</p></div>
          </aside>
        </div>
      </section>

      <LiveComparisonPanel liveEvaluation={liveEvaluation} />

      <section className="prompt-lab-iterations shell" aria-labelledby="prompt-iterations-title">
        <div className="prompt-lab-heading">
          <div><p className="eyebrow">Prompt iteration / live-provider archives</p><h2 className="section-title" id="prompt-iterations-title">A newer prompt did not earn promotion.</h2></div>
          <p>{artifact.prompt_iterations.headline}</p>
        </div>

        <div className="prompt-lab-iteration-groups">
          {artifact.prompt_iterations.cohorts.map((cohort) => {
            const fullCohort = cohort.comparable_versions.includes("v2") && cohort.comparable_versions.includes("v3");
            const v2 = fullCohort ? cohort.runs.find((run) => run.prompt_version === "v2") : undefined;
            const v3 = fullCohort ? cohort.runs.find((run) => run.prompt_version === "v3") : undefined;
            return (
              <article className="prompt-lab-iteration-group" key={cohort.cohort_id}>
                <header>
                  <div><span className="prompt-lab-iteration__cohort">Comparable cohort / {cohort.cohort_id}</span><h3>{cohort.runs[0].record_count} records / Prompt {cohort.comparable_versions.map((value) => value.toUpperCase()).join(" vs ")}</h3></div>
                  <p>{cohort.interpretation}</p>
                </header>
                <div className="prompt-lab-iteration-grid">
                  {cohort.runs.map((run) => <PromptIteration artifact={artifact} key={run.run_id} run={run} />)}
                </div>
                {v2 && v3 ? (
                  <aside className="prompt-lab-v3-tradeoff" role="note" aria-label="Prompt V3 promotion tradeoff">
                    <div><span>V3 TRADEOFF / PRECISION REGRESSION</span><strong>Recall rose {((v3.extraction_quality.micro_recall - v2.extraction_quality.micro_recall) * 100).toFixed(2)} points. Precision fell {((v2.extraction_quality.micro_precision - v3.extraction_quality.micro_precision) * 100).toFixed(2)} points.</strong></div>
                    <dl><div><dt>Micro-F1</dt><dd>{percent(v2.extraction_quality.micro_f1)} → {percent(v3.extraction_quality.micro_f1)}</dd></div><div><dt>False-positive fields</dt><dd>{v2.extraction_quality.total_fp} → {v3.extraction_quality.total_fp}</dd></div><div><dt>Promotion</dt><dd>Withheld</dd></div></dl>
                  </aside>
                ) : null}
                <PromptDiff artifact={artifact} cohort={cohort} />
                <details className="prompt-lab-disclosure">
                  <summary>Open full prompt comparison / complete texts</summary>
                  <div className="prompt-lab-disclosure__body prompt-lab-iteration-grid">
                    {cohort.comparable_versions.map((version) => {
                      const prompt = artifact.prompt_iterations.prompts[version as keyof typeof artifact.prompt_iterations.prompts];
                      return <div className="prompt-lab-iteration" key={version}><p className="prompt-lab-meta">Prompt {version.toUpperCase()} / {prompt.sha256}</p><pre className="prompt-lab-code">{prompt.text}</pre></div>;
                    })}
                  </div>
                </details>
              </article>
            );
          })}
        </div>

        <aside className="prompt-lab-promotion" role="note">
          <div><span className="eyebrow">Promotion decision / {artifact.prompt_iterations.promotion_decision.reason_code}</span><strong>Prompt V2 remains production. Prompt V3 was not promoted.</strong></div>
          <p>On the shared 58-record cohort, precision moved from {percent(artifact.prompt_iterations.promotion_decision.v2_precision)} to {percent(artifact.prompt_iterations.promotion_decision.v3_precision)} and F1 from {percent(artifact.prompt_iterations.promotion_decision.v2_f1)} to {percent(artifact.prompt_iterations.promotion_decision.v3_f1)}. False-positive fields increased from {artifact.prompt_iterations.promotion_decision.v2_false_positive_fields} to {artifact.prompt_iterations.promotion_decision.v3_false_positive_fields}. {artifact.prompt_iterations.comparison_limit}</p>
        </aside>
      </section>

      <aside className="prompt-lab-limitations shell" aria-labelledby="prompt-lab-limitations-title">
        <div><p className="eyebrow">Evidence boundary</p><h2 id="prompt-lab-limitations-title">What these artifacts do not prove</h2></div>
        <ul>{artifact.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
      </aside>
    </>
  );
}
