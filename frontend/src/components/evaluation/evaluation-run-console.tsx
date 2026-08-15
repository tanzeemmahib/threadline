"use client";

import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { StatusPill } from "@/components/status-pill";
import { ThreadButton, ThreadLoader } from "@/components/thread-motion";
import {
  ApiRequestError,
  FALLBACK_NOTICE,
  MEASURED_EVALUATION_LABEL,
  MOCK_EVALUATION_LABEL,
  threadlineService,
} from "@/lib/api/client";
import type { EvaluationSuiteResult, ExportManifest, JobStatus, ProviderMode, StoredResultSummary } from "@/types";

export function EvaluationRunConsole() {
  const [identities, setIdentities] = useState(6);
  const [recordsPerIdentity, setRecordsPerIdentity] = useState(3);
  const [seedText, setSeedText] = useState("104, 205, 306, 407, 508");
  const [providerMode, setProviderMode] = useState<ProviderMode>("mock");
  const [job, setJob] = useState<JobStatus | null>(null);
  const [result, setResult] = useState<EvaluationSuiteResult | null>(null);
  const [resultId, setResultId] = useState<string | null>(null);
  const [storedResults, setStoredResults] = useState<StoredResultSummary[]>([]);
  const [message, setMessage] = useState("Ready to queue a durable multi-seed evaluation.");
  const [requestId, setRequestId] = useState<string | null>(null);
  const [exporting, setExporting] = useState<ExportManifest["format"] | null>(null);
  const pollTimer = useRef<number | null>(null);

  const refreshStored = useCallback(async () => {
    try {
      const values = await threadlineService.listStoredResults();
      setStoredResults(values.filter((item) => item.result_type === "benchmark_suite"));
    } catch {
      setStoredResults([]);
    }
  }, []);

  useEffect(() => {
    const initialTimer = window.setTimeout(() => void refreshStored(), 0);
    return () => {
      window.clearTimeout(initialTimer);
      if (pollTimer.current !== null) window.clearTimeout(pollTimer.current);
    };
  }, [refreshStored]);

  async function loadResult(resultId: string) {
    try {
      const stored = await threadlineService.getStoredResult(resultId);
      const parsed = stored.payload as unknown as EvaluationSuiteResult;
      if (!parsed.multi_seed || !Array.isArray(parsed.multi_seed.metrics)) throw new Error("Stored result has an incompatible schema.");
      setResult(parsed);
      setResultId(resultId);
      setMessage(`Reloaded persisted result ${resultId}.`);
    } catch (reason) {
      reportError(reason);
    }
  }

  async function poll(jobId: string) {
    try {
      const status = await threadlineService.getJob(jobId);
      setJob(status);
      setMessage(`${status.stage} · ${status.completed_cases}/${status.total_cases} cases`);
      if (status.state === "completed" && status.result_id) {
        await loadResult(status.result_id);
        await refreshStored();
        return;
      }
      if (status.state === "failed" || status.state === "cancelled") {
        setMessage(status.error ?? `Job ${status.state}.`);
        return;
      }
      pollTimer.current = window.setTimeout(() => void poll(jobId), 600);
    } catch (reason) {
      reportError(reason);
    }
  }

  async function startJob() {
    const seeds = seedText.split(",").map((value) => Number(value.trim())).filter(Number.isFinite);
    setRequestId(null);
    setResult(null);
    setResultId(null);
    setMessage("Queuing evaluation job…");
    try {
      const status = await threadlineService.createBenchmarkJob({
        configuration: { seed: seeds[0] ?? 104, identities, records_per_identity: recordsPerIdentity },
        seeds,
        provider_mode: providerMode,
        candidate_k: 5,
        include_risk_coverage: true,
        include_adaptive_router: true,
      });
      setJob(status);
      await poll(status.job_id);
    } catch (reason) {
      reportError(reason);
    }
  }

  async function cancelJob() {
    if (!job) return;
    if (pollTimer.current !== null) window.clearTimeout(pollTimer.current);
    try {
      const cancelled = await threadlineService.cancelJob(job.job_id);
      setJob(cancelled);
      setMessage("Evaluation job cancelled; completed artifacts remain preserved.");
    } catch (reason) {
      reportError(reason);
    }
  }

  async function exportResult(format: ExportManifest["format"]) {
    if (!resultId) return;
    setExporting(format);
    try {
      const manifest = await threadlineService.exportResultManifest(resultId, format);
      const blob = new Blob([manifest.content], { type: manifest.content_type });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = manifest.filename;
      anchor.click();
      URL.revokeObjectURL(url);
      setMessage(`Exported ${manifest.filename} · hash ${manifest.content_sha256.slice(0, 12)}…`);
    } catch (reason) {
      reportError(reason);
    } finally {
      setExporting(null);
    }
  }

  function reportError(reason: unknown) {
    if (reason instanceof ApiRequestError) {
      setMessage(reason.message);
      setRequestId(reason.requestId);
    } else setMessage(FALLBACK_NOTICE);
  }

  const active = job?.state === "queued" || job?.state === "running";
  return (
    <section className="research-lab-section research-lab-section--dark" id="run-console" aria-labelledby="run-console-title">
      <div className="shell">
        <header className="research-section-heading"><div><p className="eyebrow">Persistent evaluation console</p><h2 className="section-title" id="run-console-title">Multi-seed evidence, not a single lucky run.</h2></div><p>Jobs persist progress and results in SQLite. Fixed-seed bootstrap intervals, review-priority risk–coverage, and adaptive routing all use actual stored outputs.</p></header>
        <div className="evaluation-console-grid">
          <form className="dataset-controls" aria-busy={active} onSubmit={(event) => event.preventDefault()}>
            <div className="range-control-grid"><label><span><strong>Fictional identities</strong><output>{identities}</output></span><input type="range" min="2" max="50" value={identities} onChange={(event) => setIdentities(Number(event.target.value))} /></label><label><span><strong>Records per identity</strong><output>{recordsPerIdentity}</output></span><input type="range" min="2" max="8" value={recordsPerIdentity} onChange={(event) => setRecordsPerIdentity(Number(event.target.value))} /></label></div>
            <label className="seed-field"><span>Fixed seeds</span><input value={seedText} onChange={(event) => setSeedText(event.target.value)} /></label>
            <label className="seed-field"><span>Provider</span><select value={providerMode} onChange={(event) => setProviderMode(event.target.value as ProviderMode)}><option value="mock">Deterministic mock provider</option><option value="openai_compatible">Connected model provider</option></select></label>
            <div className="dataset-export-actions"><ThreadButton variant="primary" type="button" disabled={active} onClick={() => void startJob()}>{active ? <><ThreadLoader compact announce={false} />Queue multi-seed job</> : "Queue multi-seed job"}</ThreadButton>{active ? <ThreadButton variant="danger" type="button" onClick={() => void cancelJob()}>Cancel job</ThreadButton> : null}</div>
            <div className="job-progress" role="status" aria-live="polite"><div><span style={{ "--thread-progress": job?.progress ?? 0 } as CSSProperties} /></div><strong>{job?.state ?? "idle"}</strong><p>{message}{requestId ? ` · request ${requestId}` : ""}</p></div>
            <label className="seed-field"><span>Reload stored result</span><select defaultValue="" onChange={(event) => { if (event.target.value) void loadResult(event.target.value); }}><option value="">Select a persisted benchmark suite</option>{storedResults.map((item) => <option key={item.result_id} value={item.result_id}>{item.result_id} · {new Date(item.created_at).toLocaleString()}</option>)}</select></label>
          </form>
          <div className="evaluation-console-results" aria-busy={exporting !== null}>
            <div className="evaluation-console-label"><StatusPill tone={providerMode === "mock" ? "amber" : "teal"}>{providerMode === "mock" ? MOCK_EVALUATION_LABEL : MEASURED_EVALUATION_LABEL}</StatusPill></div>
            {result ? <>
              <dl className="console-summary"><div><dt>Successful seeds</dt><dd>{result.multi_seed.successful_runs}</dd></div><div><dt>Failed seeds</dt><dd>{result.multi_seed.failed_runs}</dd></div><div><dt>Cases</dt><dd>{result.multi_seed.total_cases}</dd></div><div><dt>Model calls</dt><dd>{result.multi_seed.model_calls}</dd></div></dl>
              <div className="console-table-wrap"><table className="operations-table"><caption>Multi-seed aggregate with fixed-seed bootstrap 95% intervals</caption><thead><tr><th>Metric</th><th>Mean</th><th>Std.</th><th>Min–max</th><th>95% CI</th></tr></thead><tbody>{result.multi_seed.metrics.map((metric) => <tr key={metric.metric_id}><th>{metric.metric_id.replaceAll("_", " ")}</th><td>{metric.mean.toFixed(2)}</td><td>{metric.standard_deviation.toFixed(2)}</td><td>{metric.minimum.toFixed(2)}–{metric.maximum.toFixed(2)}</td><td>{metric.confidence_interval.lower.toFixed(2)}–{metric.confidence_interval.upper.toFixed(2)}</td></tr>)}</tbody></table></div>
              <div className="console-table-wrap"><table className="operations-table"><caption>Risk–coverage policies based on observable review-priority scores, not probabilities</caption><thead><tr><th>Policy</th><th>Threshold</th><th>Coverage</th><th>Selective risk</th><th>Reviewed</th></tr></thead><tbody>{result.risk_coverage.map((point) => <tr key={point.policy}><th>{point.policy}</th><td>{point.review_priority_threshold.toFixed(2)}</td><td>{(point.coverage * 100).toFixed(1)}%</td><td>{(point.selective_risk * 100).toFixed(1)}%</td><td>{point.reviewed_cases}/{point.total_cases}</td></tr>)}</tbody></table></div>
              {result.adaptive_router ? <div className="adaptive-summary"><h3>Adaptive router comparison</h3><p>Full workflow: {result.adaptive_router.full_model_calls} calls / {result.adaptive_router.full_duration_ms.toFixed(1)} ms. Adaptive: {result.adaptive_router.adaptive_model_calls} calls / {result.adaptive_router.adaptive_duration_ms.toFixed(1)} ms.</p><ul>{result.adaptive_router.decisions.map((decision) => <li key={decision.case_id}><strong>{decision.case_id}</strong><span>{decision.profile.replaceAll("_", " ")} · {decision.observable_signals.join(", ")}</span></li>)}</ul></div> : null}
              <div className="dataset-export-actions">{(["json", "csv", "markdown"] as const).map((format) => <ThreadButton variant="secondary" type="button" key={format} disabled={!resultId || exporting !== null} onClick={() => void exportResult(format)}>{exporting === format ? <><ThreadLoader compact announce={false} />Preparing…</> : `Export ${format.toUpperCase()}`}</ThreadButton>)}</div>
            </> : <div className="trial-empty-state"><strong>No persisted evaluation loaded</strong><p>Queue a job or select a stored result to inspect multi-seed statistics, risk–coverage, and adaptive routing.</p></div>}
          </div>
        </div>
      </div>
    </section>
  );
}
