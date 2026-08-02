"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { StatusPill } from "@/components/status-pill";
import {
  ApiRequestError,
  CONNECTED_PROVIDER_LABEL,
  FALLBACK_NOTICE,
  MEASURED_EVALUATION_LABEL,
  MOCK_EVALUATION_LABEL,
  MOCK_PROVIDER_LABEL,
  threadlineService,
} from "@/lib/api/client";
import type {
  ExportManifest,
  MutationType,
  ProviderMode,
  TrialCase,
  TrialCreateRequest,
  TrialPreview,
  TrialRunResponse,
} from "@/types";

type TrialTab = "configure" | "diff" | "results" | "divergence" | "trace" | "export";
type ActionState = "idle" | "loading" | "previewed" | "running" | "complete" | "error" | "cancelled";

const mutations: Array<{ id: MutationType; label: string; description: string }> = [
  { id: "transliteration_corruption", label: "Transliteration corruption", description: "Alter a cross-script name form without changing truth." },
  { id: "spelling_corruption", label: "Spelling corruption", description: "Remove a deterministic character from a name." },
  { id: "missing_surname", label: "Missing surname", description: "Retain only the given name." },
  { id: "estimated_age_shift", label: "Estimated age shift", description: "Move an estimated age within a seeded range." },
  { id: "missing_location", label: "Missing location", description: "Replace a known location with an explicit gap." },
  { id: "changed_location", label: "Changed location", description: "Substitute a plausible location change." },
  { id: "impossible_timeline", label: "Impossible timeline", description: "Add a physically irreconcilable travel claim." },
  { id: "conflicting_distinctive_feature", label: "Conflicting feature", description: "Contradict a high-value distinctive feature." },
  { id: "translation_detail_loss", label: "Translation detail loss", description: "Remove a potentially distinguishing translated detail." },
  { id: "common_name_collision", label: "Common-name collision", description: "Add an observationally similar common-name record." },
  { id: "duplicate_submission", label: "Duplicate submission", description: "Add a traceable duplicate with a unique record ID." },
  { id: "equally_plausible_rivals", label: "Equally plausible rivals", description: "Add a rival that should trigger abstention." },
  { id: "prompt_injection", label: "Prompt injection", description: "Embed an instruction-like string in untrusted evidence." },
  { id: "source_reliability_noise", label: "Reliability noise", description: "Replace source metadata with conflicting reliability language." },
  { id: "contradictory_relative_information", label: "Contradictory relative", description: "Add a conflicting claim from a relative." },
];

const mobileTabs: Array<{ id: TrialTab; label: string }> = [
  { id: "configure", label: "Configure" },
  { id: "diff", label: "Mutation diff" },
  { id: "results", label: "Results" },
  { id: "divergence", label: "Divergence" },
  { id: "trace", label: "Trace" },
  { id: "export", label: "Export" },
];

export function TrialsLab() {
  const [cases, setCases] = useState<TrialCase[]>([]);
  const [caseId, setCaseId] = useState("TRIAL-001");
  const [selectedMutations, setSelectedMutations] = useState<MutationType[]>([]);
  const [seed, setSeed] = useState(104);
  const [providerMode, setProviderMode] = useState<ProviderMode>("mock");
  const [preview, setPreview] = useState<TrialPreview | null>(null);
  const [result, setResult] = useState<TrialRunResponse | null>(null);
  const [state, setState] = useState<ActionState>("loading");
  const [message, setMessage] = useState("Loading trial catalogue…");
  const [requestId, setRequestId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TrialTab>("configure");
  const [exporting, setExporting] = useState<ExportManifest["format"] | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const selectedCase = cases.find((item) => item.case_id === caseId);

  const loadCases = useCallback(async () => {
    const controller = new AbortController();
    abortRef.current = controller;
    setState("loading");
    setMessage("Loading trial catalogue…");
    setRequestId(null);
    try {
      const loaded = await threadlineService.getTrialCases({ signal: controller.signal });
      setCases(loaded);
      const initialCase = loaded[0];
      setCaseId(initialCase?.case_id ?? "");
      setSelectedMutations(initialCase?.default_mutations ?? []);
      setState("idle");
      setMessage("Eight deterministic trial fixtures loaded from the backend.");
    } catch (reason) {
      handleFailure(reason, setState, setMessage, setRequestId);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadCases(), 0);
    return () => { window.clearTimeout(timer); abortRef.current?.abort(); };
  }, [loadCases]);

  const payload = useMemo<TrialCreateRequest>(() => ({
    case_id: caseId,
    mutation_types: selectedMutations,
    seed,
    provider_mode: providerMode,
  }), [caseId, providerMode, seed, selectedMutations]);

  function toggleMutation(mutation: MutationType) {
    setSelectedMutations((current) => current.includes(mutation) ? current.filter((item) => item !== mutation) : [...current, mutation]);
  }

  function selectCase(nextCaseId: string) {
    const nextCase = cases.find((item) => item.case_id === nextCaseId);
    setCaseId(nextCaseId);
    setSelectedMutations(nextCase?.default_mutations ?? []);
    setPreview(null);
    setResult(null);
  }

  async function createPreview() {
    const controller = new AbortController();
    abortRef.current = controller;
    setState("loading");
    setMessage("Applying deterministic mutations…");
    setRequestId(null);
    try {
      const next = await threadlineService.createTrial(payload, { signal: controller.signal });
      setPreview(next);
      setResult(null);
      setState("previewed");
      setMessage(`${next.mutations.length} mutation record${next.mutations.length === 1 ? "" : "s"} generated with seed ${next.seed}.`);
      setActiveTab("diff");
    } catch (reason) {
      handleFailure(reason, setState, setMessage, setRequestId);
    }
  }

  async function runTrial() {
    const controller = new AbortController();
    abortRef.current = controller;
    setState("running");
    setMessage("Running four systems on the same mutated records…");
    setRequestId(null);
    try {
      const next = await threadlineService.runTrial(
        { ...payload, ...(preview ? { trial_id: preview.trial_id } : {}) },
        { signal: controller.signal },
      );
      setResult(next);
      setState("complete");
      setMessage(`Trial complete · ${next.trial_run_id}`);
      setActiveTab("results");
    } catch (reason) {
      handleFailure(reason, setState, setMessage, setRequestId);
    }
  }

  function cancel() {
    abortRef.current?.abort();
    setState("cancelled");
    setMessage("Request cancelled. No frontend result was substituted.");
  }

  async function exportResult(format: ExportManifest["format"]) {
    if (!result) return;
    setExporting(format);
    try {
      const manifest = await threadlineService.exportResultManifest(result.result_id, format);
      downloadManifest(manifest);
      setMessage(`Export verified · ${manifest.content_sha256.slice(0, 12)}…`);
    } catch (reason) {
      handleFailure(reason, setState, setMessage, setRequestId);
    } finally {
      setExporting(null);
    }
  }

  const systemTrace = result?.systems.find((item) => item.system_id === "threadline")?.output.workflow_trace_details;
  const modeLabel = providerMode === "mock" ? MOCK_PROVIDER_LABEL : CONNECTED_PROVIDER_LABEL;
  const evaluationLabel = providerMode === "mock" ? MOCK_EVALUATION_LABEL : MEASURED_EVALUATION_LABEL;

  return (
    <>
      <section className="trials-hero shell" aria-labelledby="trials-title">
        <div><p className="eyebrow">THREADLINE Trials / deterministic mutation research</p><h1 className="page-title" id="trials-title">Find the first place reasoning diverges.</h1><p className="body-large">Mutate fictional records without changing hidden evaluation truth, run the same inputs through four systems, and inspect the earliest observable failure.</p></div>
        <aside className="trials-safety" role="note"><StatusPill tone="amber">Human review required</StatusPill><p>Ground truth is stored separately and never enters model-visible prompts. Trial output proposes review candidates; it never confirms identity.</p></aside>
      </section>

      <div className="trials-mobile-tabs shell" role="tablist" aria-label="Trial laboratory sections">
        {mobileTabs.map((tab) => <button id={`trial-tab-${tab.id}`} key={tab.id} type="button" role="tab" aria-selected={activeTab === tab.id} aria-controls={`trial-panel-${tab.id}`} onClick={() => setActiveTab(tab.id)}>{tab.label}</button>)}
      </div>

      <section className="trials-status shell" aria-live="polite">
        <div><span className={`mode-dot mode-dot--${threadlineService.configuredMode}`} aria-hidden="true" /><strong>{threadlineService.configuredMode === "backend" ? modeLabel : FALLBACK_NOTICE}</strong><span>{evaluationLabel}</span></div>
        <div><StatusPill tone={state === "error" ? "red" : state === "complete" ? "teal" : state === "running" || state === "loading" ? "cyan" : "slate"}>{state}</StatusPill><p>{message}{requestId ? ` · request ${requestId}` : ""}</p>{(state === "loading" || state === "running") ? <button className="button-quiet" type="button" onClick={cancel}>Cancel</button> : null}{state === "error" ? <button className="button-quiet" type="button" onClick={() => void (cases.length ? createPreview() : loadCases())}>Retry</button> : null}</div>
      </section>

      <div className="trials-desktop-grid shell">
        <section className={`trials-column trials-config ${activeTab === "configure" ? "is-mobile-active" : ""}`} id="trial-panel-configure" role="tabpanel" aria-labelledby="trial-tab-configure">
          <header><p className="eyebrow">01 / Configure</p><h2>Trial controls</h2></header>
          <label className="trials-field" htmlFor="trial-case"><span>Fixture</span><select id="trial-case" value={caseId} onChange={(event) => selectCase(event.target.value)} disabled={!cases.length}>{cases.map((item) => <option key={item.case_id} value={item.case_id}>{item.case_id} · {item.title}</option>)}</select></label>
          {selectedCase ? <div className="trial-case-note"><strong>{selectedCase.challenge}</strong><p>{selectedCase.ground_truth.rationale}</p><small>Evaluation truth is visible to the researcher only; it is excluded from model requests.</small></div> : null}
          <fieldset className="mutation-selector"><legend>Mutations · {selectedMutations.length} selected</legend>{mutations.map((mutation) => <label key={mutation.id}><input type="checkbox" checked={selectedMutations.includes(mutation.id)} onChange={() => toggleMutation(mutation.id)} /><span><strong>{mutation.label}</strong><small>{mutation.description}</small></span></label>)}</fieldset>
          <div className="trial-control-pair"><label className="trials-field" htmlFor="trial-seed"><span>Fixed seed</span><input id="trial-seed" type="number" value={seed} onChange={(event) => setSeed(Number(event.target.value))} /></label><label className="trials-field" htmlFor="trial-provider"><span>Provider</span><select id="trial-provider" value={providerMode} onChange={(event) => setProviderMode(event.target.value as ProviderMode)}><option value="mock">Deterministic mock</option><option value="openai_compatible">Connected model</option></select></label></div>
          <div className="trial-actions"><button className="button-secondary" type="button" onClick={() => void createPreview()} disabled={!caseId || state === "loading" || state === "running"}>Preview mutation</button><button className="button-primary" type="button" onClick={() => void runTrial()} disabled={!caseId || state === "loading" || state === "running"}>Run trial</button></div>
        </section>

        <section className={`trials-column trials-diff ${activeTab === "diff" ? "is-mobile-active" : ""}`} id="trial-panel-diff" role="tabpanel" aria-labelledby="trial-tab-diff">
          <header><p className="eyebrow">02 / Mutation diff</p><h2>Truth-preserving changes</h2></header>
          {preview ? <div className="mutation-list">{preview.mutations.map((mutation) => <article key={mutation.mutation_id}><header><StatusPill tone={mutation.difficulty === "adversarial" || mutation.difficulty === "high" ? "red" : "amber"}>{mutation.difficulty}</StatusPill><strong>{mutation.mutation_type.replaceAll("_", " ")}</strong><small>{mutation.mutation_id}</small></header><div className="mutation-diff-grid"><div><span>Before</span><pre>{JSON.stringify(mutation.before, null, 2)}</pre></div><div><span>After</span><pre>{JSON.stringify(mutation.after, null, 2)}</pre></div></div><p>{mutation.safety_note}</p></article>)}</div> : <EmptyState title="No mutation preview yet" detail="Choose a fixture and create a preview. Every changed field will be recorded here." />}
        </section>

        <aside className={`trials-column trials-run ${activeTab === "results" ? "is-mobile-active" : ""}`} id="trial-panel-results" role="tabpanel" aria-labelledby="trial-tab-results">
          <header><p className="eyebrow">03 / Results</p><h2>System status</h2></header>
          {result ? <div className="trial-system-results">{result.systems.map((system) => <article key={system.system_id}><div><strong>{system.system_name}</strong><StatusPill tone={system.classification === "conflicting_evidence" ? "red" : system.classification === "insufficient_evidence" ? "amber" : "cyan"}>{system.classification.replaceAll("_", " ")}</StatusPill></div><dl><div><dt>Model calls</dt><dd>{system.model_calls}</dd></div><div><dt>Duration</dt><dd>{system.duration_ms.toFixed(1)} ms</dd></div><div><dt>Evidence spans</dt><dd>{system.cited_evidence.length}</dd></div></dl></article>)}</div> : <EmptyState title="No completed run" detail="Run the configured trial to compare all four systems on identical mutated records." />}
        </aside>
      </div>

      <section className={`trial-lower-panel shell ${activeTab === "divergence" ? "is-mobile-active" : ""}`} id="trial-panel-divergence" role="tabpanel" aria-labelledby="trial-tab-divergence">
        <header><div><p className="eyebrow">First divergence</p><h2 className="section-title">Where the output first left the accepted set.</h2></div>{result ? <StatusPill tone={result.divergence.category === "none" ? "teal" : "red"}>{result.divergence.category}</StatusPill> : null}</header>
        {result ? <dl className="divergence-grid"><div><dt>Expected</dt><dd>{result.divergence.expected}</dd></div><div><dt>Observed</dt><dd>{result.divergence.observed}</dd></div><div><dt>System</dt><dd>{result.divergence.first_divergent_system ?? "No divergence"}</dd></div><div><dt>Workflow node</dt><dd>{result.divergence.first_divergent_node ?? "Not applicable"}</dd></div><div className="divergence-explanation"><dt>Deterministic explanation</dt><dd>{result.divergence.explanation}</dd></div></dl> : <EmptyState title="Divergence pending" detail="A completed run is required before the expected and observed outputs can be compared." />}
      </section>

      <section className={`trial-lower-panel shell ${activeTab === "trace" ? "is-mobile-active" : ""}`} id="trial-panel-trace" role="tabpanel" aria-labelledby="trial-tab-trace">
        <header><div><p className="eyebrow">Trace</p><h2 className="section-title">Stored workflow evidence.</h2></div>{result?.workflow_run_id ? <StatusPill tone="slate">{result.workflow_run_id}</StatusPill> : null}</header>
        {systemTrace ? <pre className="trial-trace-json">{JSON.stringify(systemTrace, null, 2)}</pre> : <EmptyState title="Trace pending" detail="The full workflow trace appears after a completed trial run." />}
      </section>

      <section className={`trial-lower-panel trial-export shell ${activeTab === "export" ? "is-mobile-active" : ""}`} id="trial-panel-export" role="tabpanel" aria-labelledby="trial-tab-export">
        <header><div><p className="eyebrow">Export</p><h2 className="section-title">Portable, credential-free artifacts.</h2></div></header>
        <p>Each manifest includes result ID, provider mode, content hash, byte count, and an explicit assertion that credentials are absent.</p>
        <div>{(["json", "csv", "markdown"] as const).map((format) => <button className="button-secondary" type="button" key={format} disabled={!result || exporting !== null} onClick={() => void exportResult(format)}>{exporting === format ? `Preparing ${format}…` : `Export ${format.toUpperCase()}`}</button>)}</div>
      </section>
    </>
  );
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="trial-empty-state"><strong>{title}</strong><p>{detail}</p></div>;
}

function handleFailure(
  reason: unknown,
  setState: (state: ActionState) => void,
  setMessage: (message: string) => void,
  setRequestId: (requestId: string | null) => void,
) {
  if (reason instanceof DOMException && reason.name === "AbortError") {
    setState("cancelled");
    setMessage("Request cancelled. No frontend result was substituted.");
    return;
  }
  setState("error");
  if (reason instanceof ApiRequestError) {
    setMessage(reason.message);
    setRequestId(reason.requestId);
  } else {
    setMessage("The trial request failed before a result was returned.");
  }
}

function downloadManifest(manifest: ExportManifest) {
  const blob = new Blob([manifest.content], { type: manifest.content_type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = manifest.filename;
  link.click();
  URL.revokeObjectURL(url);
}
