"use client";

import { useCallback, useEffect, useState } from "react";
import { StatusPill } from "@/components/status-pill";
import { WorkflowExplorer } from "@/components/workflow-explorer";
import { AuditLedger } from "@/components/workspace/audit-ledger";
import { CandidateThread } from "@/components/workspace/candidate-thread";
import { EvidenceDialog } from "@/components/workspace/evidence-dialog";
import { RecordBrowser } from "@/components/workspace/record-browser";
import { ReconstructionCanvas, type ReconstructionSelection } from "@/components/workspace/reconstruction-canvas";
import { ReviewDialog } from "@/components/workspace/review-dialog";
import { ReviewPanel } from "@/components/workspace/review-panel";
import { mockCaseData } from "@/data/mock-data";
import { fullAuditLedger, reconstructionData, workflowTraceDetails } from "@/data/research-data";
import { FALLBACK_NOTICE, MOCK_PROVIDER_LABEL, threadlineService } from "@/lib/api/client";
import type { AnalyzeRequest, AnalyzeResponse, AuditEvent, CaseData, ReviewOutcome, WorkflowNodeTrace } from "@/types";

type MobileTab = "records" | "reconstruction" | "review" | "workflow" | "audit";
type CenterView = "reconstruction" | "reasoning" | "workflow" | "audit";

const mobileTabs: Array<{ id: MobileTab; label: string }> = [
  { id: "records", label: "Records" }, { id: "reconstruction", label: "Reconstruction" }, { id: "review", label: "Review" }, { id: "workflow", label: "Workflow" }, { id: "audit", label: "Audit" },
];

export function WorkspaceShell() {
  const [caseData, setCaseData] = useState<CaseData>(mockCaseData);
  const [traces, setTraces] = useState<WorkflowNodeTrace[]>(workflowTraceDetails);
  const [connectionState, setConnectionState] = useState<"loading" | "ready" | "fallback">(
    threadlineService.configuredMode === "backend" ? "loading" : "fallback",
  );
  const [connectionMessage, setConnectionMessage] = useState(
    threadlineService.configuredMode === "backend" ? "Loading backend incident…" : `Fixture mode — ${MOCK_PROVIDER_LABEL}`,
  );
  const [candidateId, setCandidateId] = useState("MATCH-001");
  const [evidenceSpanId, setEvidenceSpanId] = useState<string | null>(null);
  const [mobileTab, setMobileTab] = useState<MobileTab>("reconstruction");
  const [centerView, setCenterView] = useState<CenterView>("reconstruction");
  const [reviewOutcome, setReviewOutcome] = useState<ReviewOutcome | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>(fullAuditLedger);
  const [savedMessage, setSavedMessage] = useState("");
  const [selection, setSelection] = useState<ReconstructionSelection>({ recordId: "FAMILY-018", factorId: "CF-NAME", eventId: "EVENT-1630", locationId: "al-noor" });

  const candidate = caseData.candidates.find((item) => item.candidate_id === candidateId) ?? caseData.candidates[0];
  const selectedIds = new Set([candidate.record_a_id, candidate.record_b_id, selection.recordId]);
  const evidence = (() => {
    if (!evidenceSpanId) return null;
    for (const record of caseData.records) {
      const span = record.evidence_spans.find((item) => item.span_id === evidenceSpanId);
      if (span) return { record, span };
    }
    return null;
  })();

  const loadBackendCase = useCallback(async (signal?: AbortSignal) => {
    if (threadlineService.configuredMode !== "backend") return;
    setConnectionState("loading");
    setConnectionMessage("Loading backend incident…");
    try {
      const demo = await threadlineService.getDemoIncident({ signal });
      const analysis = await threadlineService.analyzeRecords(demo, { signal });
      const integrated = integrateCase(demo, analysis);
      setCaseData(integrated);
      setAuditEvents(integrated.audit_events);
      setTraces((analysis.workflow_trace_details ?? []).map(toInspectorTrace));
      setCandidateId(integrated.candidates[0]?.candidate_id ?? "");
      setConnectionState("ready");
      setConnectionMessage(
        analysis.mode === "openai_compatible" ? "Connected model provider" : MOCK_PROVIDER_LABEL,
      );
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setCaseData(mockCaseData);
      setAuditEvents(fullAuditLedger);
      setTraces(workflowTraceDetails);
      setConnectionState("fallback");
      setConnectionMessage(FALLBACK_NOTICE);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void loadBackendCase(controller.signal), 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [loadBackendCase]);

  function chooseCandidate(id: string) {
    const nextCandidate = caseData.candidates.find((item) => item.candidate_id === id);
    setCandidateId(id);
    setSavedMessage("");
    if (nextCandidate) setSelection((current) => ({ ...current, recordId: nextCandidate.record_a_id, factorId: nextCandidate.compatibility_factors[0]?.factor_id ?? "" }));
    setCenterView("reconstruction");
    setMobileTab("reconstruction");
  }

  function selectRecord(recordId: string) {
    const event = reconstructionData.events.find((item) => item.record_ids.includes(recordId));
    setSelection((current) => ({ ...current, recordId, eventId: event?.event_id ?? current.eventId, locationId: event?.location_id ?? current.locationId }));
  }

  function selectFactor(factorId: string) {
    const factor = candidate.compatibility_factors.find((item) => item.factor_id === factorId);
    const record = caseData.records.find((item) => item.evidence_spans.some((span) => factor?.evidence_span_ids.includes(span.span_id)));
    if (record) selectRecord(record.record_id);
    setSelection((current) => ({ ...current, factorId }));
  }

  function selectEvent(eventId: string) {
    const event = reconstructionData.events.find((item) => item.event_id === eventId);
    if (!event) return;
    setSelection((current) => ({ ...current, eventId, locationId: event.location_id, recordId: event.record_ids[0] ?? current.recordId }));
  }

  function selectLocation(locationId: string) {
    const location = reconstructionData.locations.find((item) => item.location_id === locationId);
    const event = reconstructionData.events.find((item) => item.location_id === locationId);
    if (!location) return;
    setSelection((current) => ({ ...current, locationId, eventId: event?.event_id ?? current.eventId, recordId: location.record_ids[0] ?? current.recordId }));
  }

  function chooseMobileTab(tab: MobileTab) {
    setMobileTab(tab);
    if (tab === "reconstruction" || tab === "workflow" || tab === "audit") setCenterView(tab);
  }

  async function saveReview(outcome: ReviewOutcome, notes: string) {
    const timestamp = new Date().toISOString();
    const decision = { decision_id: `DECISION-${auditEvents.length + 1}`, candidate_id: candidate.candidate_id, outcome, notes, reviewer_role: "Demo reviewer", timestamp };
    if (threadlineService.configuredMode === "backend" && connectionState === "ready") {
      try {
        await threadlineService.submitReviewOutcome(caseData.case_id, decision);
        const persisted = await threadlineService.getCaseAudit(caseData.case_id);
        setAuditEvents(persisted);
        setSavedMessage("Review outcome persisted to the backend audit ledger.");
        setReviewOutcome(null);
        return;
      } catch {
        setSavedMessage("Review was not saved. Retry when the backend is available.");
        return;
      }
    }
    const event: AuditEvent = {
      event_id: `LEDGER-${String(auditEvents.length + 1).padStart(3, "0")}`, timestamp, actor: "Demo reviewer", action: "reviewer decision saved", detail: `${outcome.replaceAll("_", " ")} — ${notes || "No additional note supplied."}`,
      event_type: "reviewer decision saved", workflow_version: "threadline-workflow/2.0.0-synthetic", prompt_version: "Not applicable", source_record_ids: [candidate.record_a_id, candidate.record_b_id], before_value: "Authorized checkpoint open", after_value: outcome.replaceAll("_", " "), reason: notes || "Synthetic review action", origin: "human",
    };
    setAuditEvents((current) => [...current, event]);
    setSavedMessage("Fixture mode: review outcome saved in this browser session only.");
    setReviewOutcome(null);
  }

  return (
    <>
      <section className="incident-strip" aria-label="Incident status">
        <div className="incident-strip__identity"><strong>{caseData.incident.name}</strong><StatusPill tone="teal">Synthetic data</StatusPill></div>
        <dl className="incident-strip__metrics"><div><dt>Records</dt><dd>{caseData.summary.records_processed}</dd></div><div><dt>Languages</dt><dd>{caseData.summary.languages_detected}</dd></div><div><dt>Candidate threads</dt><dd>{caseData.summary.candidate_connections}</dd></div><div><dt>Awaiting review</dt><dd>{caseData.summary.awaiting_human_review}</dd></div></dl>
        <div className="incident-strip__mode" role="status" aria-live="polite"><span className={`mode-dot mode-dot--${connectionState === "ready" ? "backend" : "mock"}`} aria-hidden="true" />{connectionMessage}{connectionState === "fallback" && threadlineService.configuredMode === "backend" ? <button className="button-quiet" type="button" onClick={() => void loadBackendCase()}>Retry</button> : null}</div>
      </section>

      <div className="workspace-tabs" role="tablist" aria-label="Workspace panels">
        {mobileTabs.map((tab) => <button id={`tab-${tab.id}`} key={tab.id} type="button" role="tab" aria-selected={mobileTab === tab.id} aria-controls={tab.id === "records" ? "panel-records" : tab.id === "review" ? "panel-review" : "panel-center"} onClick={() => chooseMobileTab(tab.id)}>{tab.label}</button>)}
      </div>

      <div className="workspace-grid">
        <aside className={`workspace-column workspace-records ${mobileTab === "records" ? "is-mobile-active" : ""}`} id="panel-records" role="tabpanel" aria-labelledby="tab-records">
          <RecordBrowser records={caseData.records} candidates={caseData.candidates} selectedRecordIds={selectedIds} selectedRecordId={selection.recordId} selectedCandidateId={candidate.candidate_id} onSelectCandidate={chooseCandidate} onSelectRecord={selectRecord} onOpenEvidence={setEvidenceSpanId} />
        </aside>

        <section className={`workspace-column workspace-center ${["reconstruction", "workflow", "audit"].includes(mobileTab) ? "is-mobile-active" : ""}`} id="panel-center" role="tabpanel" aria-labelledby={`tab-${["reconstruction", "workflow", "audit"].includes(mobileTab) ? mobileTab : "reconstruction"}`}>
          <div className="center-toolbar">
            <div className="segmented-control" aria-label="Central workspace view">
              <button type="button" aria-pressed={centerView === "reconstruction"} onClick={() => setCenterView("reconstruction")}>Reconstruction</button>
              <button type="button" aria-pressed={centerView === "reasoning"} onClick={() => setCenterView("reasoning")}>Evidence reasoning</button>
              <button type="button" aria-pressed={centerView === "workflow"} onClick={() => setCenterView("workflow")}>Workflow</button>
              <button type="button" aria-pressed={centerView === "audit"} onClick={() => setCenterView("audit")}>Audit</button>
            </div>
            <StatusPill tone={centerView === "workflow" ? "slate" : centerView === "audit" ? "teal" : "cyan"}>{centerView === "workflow" ? caseData.workflow_run_id : centerView === "audit" ? `${auditEvents.length} events` : candidate.classification ?? candidate.label}</StatusPill>
          </div>
          {centerView === "reconstruction" && <ReconstructionCanvas candidate={candidate} records={caseData.records} data={reconstructionData} selection={selection} onSelectRecord={selectRecord} onSelectFactor={selectFactor} onSelectEvent={selectEvent} onSelectLocation={selectLocation} onOpenEvidence={setEvidenceSpanId} />}
          {centerView === "reasoning" && <CandidateThread candidate={candidate} records={caseData.records} candidates={caseData.candidates} onSelectCandidate={chooseCandidate} onOpenEvidence={setEvidenceSpanId} />}
          {centerView === "workflow" && <WorkflowExplorer nodes={caseData.workflow_trace} traces={traces} />}
          {centerView === "audit" && <AuditLedger events={auditEvents} />}
        </section>

        <aside className={`workspace-column workspace-review ${mobileTab === "review" ? "is-mobile-active" : ""}`} id="panel-review" role="tabpanel" aria-labelledby="tab-review">
          <ReviewPanel candidate={candidate} records={caseData.records} auditEvents={auditEvents} savedMessage={savedMessage} onOpenEvidence={setEvidenceSpanId} onOpenReview={(outcome) => setReviewOutcome(outcome ?? "escalate_authorized_review")} />
        </aside>
      </div>

      <EvidenceDialog evidence={evidence} onClose={() => setEvidenceSpanId(null)} />
      <ReviewDialog candidateId={candidate.candidate_id} initialOutcome={reviewOutcome} onClose={() => setReviewOutcome(null)} onSave={saveReview} />
    </>
  );
}

function integrateCase(demo: AnalyzeRequest, analysis: AnalyzeResponse): CaseData {
  return {
    ...analysis,
    incident: {
      incident_id: demo.incident.incident_id,
      name: demo.incident.name,
      description: demo.incident.description ?? "Synthetic THREADLINE incident.",
      languages: demo.incident.languages,
      simulation_label: "Synthetic research incident",
    },
    records: analysis.records ?? mockCaseData.records,
    audit_events: analysis.audit_events ?? [],
  };
}

function toInspectorTrace(trace: NonNullable<AnalyzeResponse["workflow_trace_details"]>[number]): WorkflowNodeTrace {
  return {
    node_id: trace.node_id,
    node_version: trace.node_version,
    input_record_ids: trace.input_record_ids,
    input_schema: trace.input_schema,
    prompt_template: trace.prompt_template_id ? `${trace.prompt_template_id} · ${trace.prompt_template_version ?? "unversioned"}` : "Not applicable",
    prompt_variables: Object.fromEntries(Object.entries(trace.structured_input).map(([key, value]) => [key, JSON.stringify(value)])),
    configured_model: trace.model ? "Configured LLM" : "Not applicable",
    structured_output: JSON.stringify(trace.structured_output, null, 2),
    output_schema: trace.output_schema,
    deterministic_checks: trace.deterministic_checks,
    evidence_span_ids: trace.evidence_span_ids,
    warnings: trace.warnings,
    failure_conditions: trace.failure_conditions,
    abstention_reason: trace.abstention_reason,
    duration: { value: trace.duration_ms, label: trace.duration_ms === null ? "Deterministic mock trace" : "Measured milliseconds" },
    token_usage: { value: trace.token_usage, label: trace.token_usage === null ? "Not reported" : "Measured provider usage" },
    estimated_cost: { value: trace.estimated_cost, label: trace.estimated_cost === null ? "Not estimated" : "Provider estimate" },
    next_node: trace.next_node,
    human_review_requirement: trace.human_review_requirement,
    before_state: trace.before_state,
    after_state: trace.after_state,
  };
}
