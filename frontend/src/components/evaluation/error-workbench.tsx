"use client";

import { useMemo, useState } from "react";
import { useEvaluationSession } from "@/components/evaluation/evaluation-session";
import { errorAnalysisCases } from "@/data/research-data";
import type { BackendErrorAnalysisCase, ErrorAnalysisCase, ErrorCategory } from "@/types";

export function ErrorWorkbench() {
  const { benchmark } = useEvaluationSession();
  const measuredCases = useMemo(() => benchmark?.systems.flatMap((item) => item.errors.map((error) => toWorkbenchError(error, item.system_id))) ?? [], [benchmark]);
  const allCases = measuredCases.length ? measuredCases : errorAnalysisCases;
  const [system, setSystem] = useState("all");
  const [language, setLanguage] = useState("all");
  const [errorType, setErrorType] = useState<"all" | ErrorCategory>("all");
  const [configuration, setConfiguration] = useState("all");
  const [severity, setSeverity] = useState("all");
  const [selectedId, setSelectedId] = useState(errorAnalysisCases[0].error_id);
  const values = <T extends string>(items: T[]) => [...new Set(items)];
  const filtered = useMemo(() => allCases.filter((item) => (system === "all" || item.system_id === system) && (language === "all" || item.language === language) && (errorType === "all" || item.category === errorType) && (configuration === "all" || item.workflow_configuration === configuration) && (severity === "all" || item.severity === severity)), [allCases, configuration, errorType, language, severity, system]);
  const selected = filtered.find((item) => item.error_id === selectedId) ?? filtered[0];

  return (
    <section className="research-lab-section shell" id="error-workbench" aria-labelledby="error-workbench-title">
      <header className="research-section-heading"><div><p className="eyebrow">Error-analysis workbench</p><h2 className="section-title" id="error-workbench-title">Find the first place reasoning diverged.</h2></div><p>{measuredCases.length ? `Actual backend output · ${benchmark?.benchmark_run_id}` : "Synthetic example output · run Dataset lab benchmark to replace fixtures."} Every error retains expected output, actual output, evidence, configuration, and a review path.</p></header>
      <form className="error-filters" onSubmit={(event) => event.preventDefault()}>
        <label><span>System</span><select value={system} onChange={(event) => setSystem(event.target.value)}><option value="all">All systems</option>{values(allCases.map((item) => item.system_id)).map((value) => <option key={value}>{value}</option>)}</select></label>
        <label><span>Language</span><select value={language} onChange={(event) => setLanguage(event.target.value)}><option value="all">All languages</option>{values(allCases.map((item) => item.language)).map((value) => <option key={value}>{value}</option>)}</select></label>
        <label><span>Error type</span><select value={errorType} onChange={(event) => setErrorType(event.target.value as typeof errorType)}><option value="all">All error types</option>{values(allCases.map((item) => item.category)).map((value) => <option key={value}>{value}</option>)}</select></label>
        <label><span>Configuration</span><select value={configuration} onChange={(event) => setConfiguration(event.target.value)}><option value="all">All configurations</option>{values(allCases.map((item) => item.workflow_configuration)).map((value) => <option key={value}>{value}</option>)}</select></label>
        <label><span>Severity</span><select value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="all">All severities</option>{values(allCases.map((item) => item.severity)).map((value) => <option key={value}>{value}</option>)}</select></label>
      </form>
      <div className="error-workbench-grid">
        <div className="error-case-list"><header><span>{filtered.length} cases</span><strong>Filtered error set</strong></header>{filtered.map((item) => <button key={item.error_id} type="button" aria-pressed={selected?.error_id === item.error_id} onClick={() => setSelectedId(item.error_id)}><span><strong>{item.error_id}</strong><i className={`severity-dot severity-dot--${item.severity}`}>{item.severity}</i></span><h3>{item.category}</h3><small>{item.case_id} · {item.language} · {item.system_id}</small></button>)}</div>
        {selected ? <article className="error-case-detail" aria-live="polite"><header><div><span>{selected.error_id} / {selected.case_id}</span><h3>{selected.category}</h3></div><strong className={`severity-label severity-label--${selected.severity}`}>{selected.severity}</strong></header><dl><div><dt>Affected records</dt><dd>{selected.affected_records.join(", ")}</dd></div><div><dt>Workflow configuration</dt><dd>{selected.workflow_configuration}</dd></div><div><dt>Expected result</dt><dd>{selected.expected_result}</dd></div><div><dt>System result</dt><dd>{selected.system_result}</dd></div><div><dt>First divergence node</dt><dd>{selected.first_divergence_node}</dd></div><div><dt>Supporting evidence</dt><dd><ul>{selected.supporting_evidence.map((evidence) => <li key={evidence}>{evidence}</li>)}</ul></dd></div><div><dt>Possible correction</dt><dd>{selected.possible_correction}</dd></div><div><dt>Reviewer notes</dt><dd>{selected.reviewer_notes}</dd></div></dl></article> : <div className="empty-research-state"><strong>No errors match these filters.</strong><p>Broaden one filter to inspect a case.</p></div>}
      </div>
    </section>
  );
}

function toWorkbenchError(error: BackendErrorAnalysisCase, systemId: ErrorAnalysisCase["system_id"]): ErrorAnalysisCase {
  const categoryMap: Record<string, ErrorCategory> = {
    missed_true_candidate: "missed true candidate",
    incorrect_candidate_link: "incorrect candidate link",
    failed_abstention: "failed abstention",
    unsupported_evidence: "unsupported evidence",
    timeline_reasoning_failure: "timeline reasoning failure",
    transliteration_failure: "transliteration failure",
    rival_candidate_confusion: "rival-candidate confusion",
    prompt_injection_failure: "prompt-injection failure",
    privacy_exposure: "privacy exposure",
    extraction_error: "extraction error",
  };
  return {
    error_id: error.error_id,
    case_id: error.case_id,
    category: categoryMap[error.category] ?? "extraction error",
    severity: error.severity,
    system_id: systemId,
    language: "English",
    workflow_configuration: error.workflow_configuration,
    affected_records: error.record_ids,
    expected_result: error.expected_result,
    system_result: error.actual_result,
    first_divergence_node: error.first_divergent_node,
    supporting_evidence: error.evidence,
    possible_correction: error.suggested_investigation,
    reviewer_notes: "Backend-produced error record; authorized analyst review required.",
  };
}
