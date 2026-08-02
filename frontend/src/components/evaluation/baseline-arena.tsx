"use client";

import { useRef, useState } from "react";
import { StatusPill } from "@/components/status-pill";
import { mockCaseData } from "@/data/mock-data";
import { baselineResults, evidenceMatrixRows } from "@/data/research-data";
import { FALLBACK_NOTICE, MOCK_EVALUATION_LABEL, threadlineService } from "@/lib/api/client";
import type { BackendSystemOutput, BaselineCaseResult, CandidateClassification } from "@/types";

export function BaselineArena() {
  const [caseId, setCaseId] = useState("MATCH-001");
  const [selectedSystem, setSelectedSystem] = useState("threadline");
  const [actualResults, setActualResults] = useState<BaselineCaseResult[] | null>(null);
  const [runState, setRunState] = useState("Synthetic example output · run the backend comparison for measured outputs.");
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const displayedResults = actualResults ?? baselineResults;
  const candidate = mockCaseData.candidates.find((item) => item.candidate_id === caseId) ?? mockCaseData.candidates[0];
  const selected = displayedResults.find((result) => result.system_id === selectedSystem) ?? displayedResults[3];
  const caseClassification = actualResults ? selected.classification : selected.system_id === "threadline" ? candidate.classification ?? "Possible candidate" : candidate.classification === "Insufficient evidence" ? "Possible candidate" : selected.classification;

  async function runComparison() {
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy(true);
    setRunState("Running exact/fuzzy, generic, structured, and full THREADLINE systems…");
    try {
      const request = await threadlineService.getDemoIncident({ signal: controller.signal });
      const response = await threadlineService.runBaselines(request, { signal: controller.signal });
      setActualResults(response.systems.map(toDisplayResult));
      setRunState(`${MOCK_EVALUATION_LABEL} · ${response.run_id}`);
    } catch {
      setRunState(FALLBACK_NOTICE);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="research-lab-section research-lab-section--dark" id="baseline-arena" aria-labelledby="baseline-arena-title">
      <div className="shell">
        <header className="research-section-heading">
          <div><p className="eyebrow">Baseline arena</p><h2 className="section-title" id="baseline-arena-title">Same case. Four reasoning shapes.</h2><p className="ablation-run-status" role="status">{runState}</p><div className="dataset-export-actions"><button className="button-primary" type="button" disabled={busy} onClick={() => void runComparison()}>{busy ? "Running…" : "Run backend comparison"}</button>{busy ? <button className="button-quiet" type="button" onClick={() => abortRef.current?.abort()}>Cancel</button> : null}</div></div>
          <div className="arena-case-control"><label htmlFor="arena-case">Selected case</label><select id="arena-case" value={caseId} onChange={(event) => setCaseId(event.target.value)}>{mockCaseData.candidates.map((item) => <option value={item.candidate_id} key={item.candidate_id}>{item.candidate_id} · {item.classification ?? item.label}</option>)}</select></div>
        </header>
        <div className="arena-system-tabs" role="tablist" aria-label="Comparison systems">{displayedResults.map((item) => <button key={item.system_id} type="button" role="tab" aria-selected={selectedSystem === item.system_id} onClick={() => setSelectedSystem(item.system_id)}><span>{item.system_name}</span><small>{item.output_origin}</small></button>)}</div>
        <article className="arena-output" aria-live="polite">
          <header><div><span>{selected.system_name}</span><h3>{candidate.record_a_id} ↔ {candidate.record_b_id}</h3></div><div><StatusPill tone="slate">{selected.output_origin}</StatusPill><StatusPill tone={caseClassification === "Conflicting evidence" ? "red" : caseClassification === "Insufficient evidence" ? "amber" : "cyan"}>{caseClassification}</StatusPill></div></header>
          <dl className="arena-output-grid">
            <div><dt>Candidate output</dt><dd>{actualResults ? selected.candidate_output : caseId === "MATCH-001" ? selected.candidate_output : `${candidate.record_a_id} ↔ ${candidate.record_b_id}`}</dd></div>
            <div><dt>Supporting evidence</dt><dd><ul>{selected.supporting_evidence.map((item) => <li key={item}>{item}</li>)}</ul></dd></div>
            <div><dt>Contradictions found</dt><dd>{selected.contradictions_found.length ? <ul>{selected.contradictions_found.map((item) => <li key={item}>{item}</li>)}</ul> : "None returned"}</dd></div>
            <div><dt>Rivals considered</dt><dd>{selected.rival_candidates_considered.join(", ") || "None"}</dd></div>
            <div><dt>Abstention behaviour</dt><dd>{selected.system_id === "threadline" && candidate.abstention_reasons && !actualResults ? `Abstained: ${candidate.abstention_reasons.join("; ")}` : selected.abstention_behaviour}</dd></div>
            <div><dt>Unsupported claims</dt><dd>{selected.unsupported_claims.join("; ") || "None identified"}</dd></div>
            <div><dt>Injection behaviour</dt><dd>{selected.injection_behaviour}</dd></div>
            <div><dt>Human-review routing</dt><dd>{selected.human_review_routing}</dd></div>
          </dl>
        </article>
        <div className="evidence-matrix-wrap">
          <table className="evidence-matrix"><caption>Expected-behaviour evidence matrix · {actualResults ? "Actual backend output" : "Synthetic example output"}</caption><thead><tr><th scope="col">Expected behaviour</th>{displayedResults.map((item) => <th scope="col" key={item.system_id}>{item.system_name}</th>)}</tr></thead><tbody>{evidenceMatrixRows.map((row) => <tr key={row.behaviour}><th scope="row">{row.behaviour}</th>{row.values.map((value, index) => <td key={`${row.behaviour}-${displayedResults[index]?.system_id ?? index}`}><span className={`matrix-result matrix-result--${value === true ? "yes" : value === false ? "no" : "na"}`}>{value === true ? "Yes" : value === false ? "No" : "Not assessed"}</span></td>)}</tr>)}</tbody></table>
        </div>
        <p className="synthetic-value-note">Outputs are labeled “Synthetic example output” or “Actual backend output.” Backend runs report actual duration, call, retry, evidence, and classification fields; fixture prose remains explicitly illustrative.</p>
      </div>
    </section>
  );
}

function classificationLabel(value: BackendSystemOutput["classification"]): CandidateClassification {
  const labels: Record<BackendSystemOutput["classification"], CandidateClassification> = {
    strong_candidate_for_review: "Strong candidate for review",
    possible_candidate: "Possible candidate",
    insufficient_evidence: "Insufficient evidence",
    conflicting_evidence: "Conflicting evidence",
  };
  return labels[value];
}

function toDisplayResult(system: BackendSystemOutput): BaselineCaseResult {
  const injectionResisted = system.output.injection_resisted;
  return {
    system_id: system.system_id,
    system_name: system.system_name,
    output_origin: "Actual backend output",
    candidate_output: system.candidate_record_ids.join(" ↔ ") || "No candidate returned",
    classification: classificationLabel(system.classification),
    supporting_evidence: system.cited_evidence.map((span) => span.text).slice(0, 5),
    contradictions_found: [],
    rival_candidates_considered: [],
    abstention_behaviour: system.classification === "insufficient_evidence" ? "System abstained from proposing a stronger link." : "Candidate routed to authorized review.",
    unsupported_claims: [],
    injection_behaviour: injectionResisted === true ? "Embedded instructions quarantined." : injectionResisted === false ? "Injection resistance failed." : "Not assessed for this case.",
    human_review_routing: "Authorized human review required; no identity determination was made.",
  };
}
