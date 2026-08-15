"use client";

import { useMemo, useRef, useState } from "react";
import { ThreadButton, ThreadLoader } from "@/components/thread-motion";
import { defaultBenchmarkConfig } from "@/lib/benchmark/generator";
import { FALLBACK_NOTICE, MEASURED_EVALUATION_LABEL, MOCK_EVALUATION_LABEL, threadlineService } from "@/lib/api/client";
import type { AblationNodeId, BackendAblationRunResponse, ProviderMode } from "@/types";

const nodeOptions: Array<{ id: AblationNodeId; backendId: string; label: string }> = [
  { id: "quarantine", backendId: "quarantine", label: "Evidence quarantine" },
  { id: "normalization", backendId: "normalize", label: "Multilingual normalization" },
  { id: "timeline", backendId: "timeline", label: "Timeline reconstruction" },
  { id: "prosecutor", backendId: "prosecutor", label: "Contradiction prosecutor" },
  { id: "rivals", backendId: "rivals", label: "Rival-candidate test" },
  { id: "adjudication", backendId: "adjudicate", label: "Independent adjudication" },
  { id: "privacy", backendId: "privacy", label: "Privacy gate" },
];

type MetricId = "candidate_recall" | "false_link_rate" | "correct_abstentions" | "evidence_faithfulness";
const metricMeta: Array<{ id: MetricId; backendId: string; label: string; description: string; full: number; better: "higher" | "lower" }> = [
  { id: "candidate_recall", backendId: "candidate_recall_at_k", label: "Candidate recall", description: "Reference-positive pairs included in the human review set.", full: 82, better: "higher" },
  { id: "false_link_rate", backendId: "false_link_rate", label: "False-link rate", description: "Different-identity cases incorrectly routed as positive candidates.", full: 8, better: "lower" },
  { id: "correct_abstentions", backendId: "correct_abstention_rate", label: "Correct abstentions", description: "Ambiguous cases where the workflow safely stopped.", full: 81, better: "higher" },
  { id: "evidence_faithfulness", backendId: "evidence_faithfulness", label: "Evidence faithfulness", description: "Structured claims supported by valid source spans.", full: 91, better: "higher" },
];

const illustrativeEffects: Record<AblationNodeId, Partial<Record<MetricId, number>>> = {
  quarantine: { evidence_faithfulness: -7 }, normalization: { candidate_recall: -23, evidence_faithfulness: -3 }, timeline: { false_link_rate: 8, correct_abstentions: -12 }, prosecutor: { false_link_rate: 15, correct_abstentions: -29, evidence_faithfulness: -17 }, rivals: { false_link_rate: 10, correct_abstentions: -20 }, adjudication: { false_link_rate: 7, correct_abstentions: -23, evidence_faithfulness: -14 }, privacy: {},
};

export function AblationLab() {
  const [enabled, setEnabled] = useState<Set<AblationNodeId>>(new Set(nodeOptions.map((node) => node.id)));
  const [benchmark, setBenchmark] = useState("Crisis benchmark v2 / seed 41027");
  const [providerMode, setProviderMode] = useState<ProviderMode>("mock");
  const [runState, setRunState] = useState("Ready to evaluate the selected configuration.");
  const [selectedMetric, setSelectedMetric] = useState<MetricId>("false_link_rate");
  const [response, setResponse] = useState<BackendAblationRunResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const disabledNodes = nodeOptions.filter((node) => !enabled.has(node.id));
  const fullConfiguration = response?.configurations.find((item) => item.configuration_id === "full");
  const selectedConfiguration = response?.configurations.at(-1);
  const results = useMemo(() => metricMeta.map((metric) => {
    const fullMeasured = fullConfiguration?.metrics.find((item) => item.metric_id === metric.backendId)?.value;
    const configuredMeasured = selectedConfiguration?.metrics.find((item) => item.metric_id === metric.backendId)?.value;
    const illustrative = Math.max(0, Math.min(100, metric.full + disabledNodes.reduce((sum, node) => sum + (illustrativeEffects[node.id][metric.id] ?? 0), 0)));
    return { ...metric, full: fullMeasured ?? metric.full, configured: configuredMeasured ?? illustrative };
  }), [disabledNodes, fullConfiguration, selectedConfiguration]);
  const affected = selectedConfiguration?.affected_case_ids ?? [];

  function toggleNode(id: AblationNodeId) {
    setEnabled((current) => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; });
    setResponse(null);
    setRunState("Configuration changed. Run evaluation to create a measured comparison.");
  }

  async function runEvaluation() {
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy(true);
    setRunState("Evaluating the full workflow and selected ablations on identical records…");
    try {
      const value = await threadlineService.runAblation({
        configuration: { ...defaultBenchmarkConfig, seed: benchmark.includes("41027") ? 41027 : defaultBenchmarkConfig.seed },
        disabled_nodes: disabledNodes.map((node) => node.backendId),
        provider_mode: providerMode,
      }, { signal: controller.signal });
      setResponse(value);
      setRunState(`${providerMode === "mock" ? MOCK_EVALUATION_LABEL : MEASURED_EVALUATION_LABEL} · ${value.ablation_run_id}`);
    } catch {
      setRunState(FALLBACK_NOTICE);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="research-lab-section shell" id="ablation-lab" aria-labelledby="ablation-lab-title" aria-busy={busy}>
      <header className="research-section-heading"><div><p className="eyebrow">Ablation laboratory</p><h2 className="section-title" id="ablation-lab-title">Remove a node. Inspect the errors it changes.</h2></div><p>Complete-workflow results remain visible as the comparison anchor.</p></header>
      <div className="ablation-config">
        <div className="ablation-run-controls"><label><span>Benchmark</span><select value={benchmark} onChange={(event) => setBenchmark(event.target.value)}><option>Crisis benchmark v2 / seed 41027</option><option>Multilingual hard cases / seed 41027</option><option>Injection safety slice / seed 41027</option></select></label><label><span>Evaluation source</span><select value={providerMode} onChange={(event) => setProviderMode(event.target.value as ProviderMode)}><option value="mock">Deterministic mock provider</option><option value="openai_compatible">Connected model provider</option></select></label><ThreadButton variant="primary" type="button" disabled={busy} onClick={() => void runEvaluation()}>{busy ? <><ThreadLoader compact announce={false} />Running…</> : "Run evaluation"}</ThreadButton></div>
        <fieldset><legend>Enabled workflow nodes</legend><div className="node-toggle-grid">{nodeOptions.map((node) => <label key={node.id}><input type="checkbox" checked={enabled.has(node.id)} onChange={() => toggleNode(node.id)} /><span><strong>{node.label}</strong><small>{enabled.has(node.id) ? "Enabled" : "Removed for this run"}</small></span></label>)}</div></fieldset>
        <p className="ablation-run-status" role="status" aria-live="polite">{runState}</p>{busy ? <ThreadButton variant="danger" type="button" onClick={() => abortRef.current?.abort()}>Cancel evaluation</ThreadButton> : null}
      </div>

      <div className="ablation-metrics-grid">{results.map((metric) => <button type="button" key={metric.id} aria-pressed={selectedMetric === metric.id} onClick={() => setSelectedMetric(metric.id)}><span>{metric.label}</span><div><strong>{metric.configured.toFixed(1)}%</strong><small>vs {metric.full.toFixed(1)}% complete</small></div><i style={{ width: `${Math.max(0, Math.min(100, metric.configured))}%` }} /><p>{metric.description} {metric.better === "higher" ? "Higher is better." : "Lower is better."}</p></button>)}</div>

      <div className="ablation-detail-grid">
        <figure className="ablation-comparison-graph" aria-labelledby="ablation-graph-title"><figcaption><span>Selected metric</span><h3 id="ablation-graph-title">{metricMeta.find((metric) => metric.id === selectedMetric)?.label}</h3></figcaption>{results.filter((metric) => metric.id === selectedMetric).map((metric) => <div key={metric.id}><div><span>Complete workflow</span><i><b style={{ width: `${Math.max(0, Math.min(100, metric.full))}%` }} /></i><strong>{metric.full.toFixed(1)}%</strong></div><div><span>Selected configuration</span><i><b style={{ width: `${Math.max(0, Math.min(100, metric.configured))}%` }} /></i><strong>{metric.configured.toFixed(1)}%</strong></div><p>{response ? "Actual backend comparison" : "Illustrative comparison"} on {benchmark}. Axis starts at zero; {metric.description}</p></div>)}</figure>
        <section className="affected-cases" aria-labelledby="affected-cases-title"><header><div><span>Metric drill-down</span><h3 id="affected-cases-title">Affected cases</h3></div><strong>{affected.length}</strong></header>{affected.length ? <article><h4>Changed classifications or errors</h4><p>These case IDs changed between the complete workflow and the selected configuration.</p><ul>{affected.map((caseId) => <li key={caseId}>{caseId}</li>)}</ul></article> : <p className="empty-research-state">{response ? "No case-level change is registered for this configuration." : "Run the backend evaluation to populate actual affected cases."}</p>}</section>
      </div>

      <div className="ablation-table-wrap"><table className="ablation-table"><caption>{response ? "Actual backend output with persisted run ID." : "Illustrative values — awaiting backend evaluation."}</caption><thead><tr><th>Metric</th><th>Complete workflow</th><th>Selected configuration</th><th>Difference</th><th>Interpretation</th></tr></thead><tbody>{results.map((metric) => <tr key={metric.id}><th>{metric.label}</th><td>{metric.full.toFixed(1)}%</td><td>{metric.configured.toFixed(1)}%</td><td>{metric.configured - metric.full > 0 ? "+" : ""}{(metric.configured - metric.full).toFixed(1)} points</td><td>{metric.description}</td></tr>)}</tbody></table></div>
      <div className="error-taxonomy"><h3>Error taxonomy for this configuration</h3>{selectedConfiguration?.newly_introduced_errors.length ? <ul>{selectedConfiguration.newly_introduced_errors.map((error) => <li key={error.error_id}><strong>{error.category.replaceAll("_", " ")}</strong><span>{error.case_id} · {error.severity}</span><p>{error.suggested_investigation}</p></li>)}</ul> : <p>{response ? "No newly introduced errors were measured." : "Backend error taxonomy appears after evaluation."}</p>}<small>Privacy exposure is reported as a safety event even where an aggregate quality metric cannot express the regression.</small></div>
      <p className="synthetic-value-note">{response ? `${providerMode === "mock" ? MOCK_EVALUATION_LABEL : MEASURED_EVALUATION_LABEL}. Metrics, differences, and affected case IDs came from the persisted backend output.` : "Illustrative values — awaiting backend evaluation. No displayed fixture percentage is a performance claim."}</p>
    </section>
  );
}
