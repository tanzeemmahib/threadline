"use client";

import { useCallback, useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type MouseEvent as ReactMouseEvent } from "react";
import { StatusPill } from "@/components/status-pill";
import { WorkflowExplorer } from "@/components/workflow-explorer";
import { AuditLedger } from "@/components/workspace/audit-ledger";
import { CandidateThread } from "@/components/workspace/candidate-thread";
import { ContradictionWorkspace } from "@/components/workspace/contradiction-workspace";
import { EvidenceDialog } from "@/components/workspace/evidence-dialog";
import { EvidenceLineage } from "@/components/workspace/evidence-lineage";
import { GuidedDemo, guidedDemoSteps } from "@/components/workspace/guided-demo";
import { RecordBrowser } from "@/components/workspace/record-browser";
import { ReconstructionCanvas, type ReconstructionSelection } from "@/components/workspace/reconstruction-canvas";
import { ReviewDialog } from "@/components/workspace/review-dialog";
import { ReviewPanel } from "@/components/workspace/review-panel";
import { mockCaseData } from "@/data/mock-data";
import { reconstructionData, workflowTraceDetails } from "@/data/research-data";
import { FALLBACK_NOTICE, MOCK_PROVIDER_LABEL, threadlineService } from "@/lib/api/client";
import type { AnalyzeRequest, AnalyzeResponse, AuditEvent, CaseData, EvidenceContract, ReconstructionData, ReviewOutcome, WorkflowNodeTrace } from "@/types";

type MobileTab = "records" | "reconstruction" | "review" | "workflow" | "audit";
type CenterView = "reconstruction" | "lineage" | "contradictions" | "reasoning" | "workflow" | "audit";

const mobileTabs: Array<{ id: MobileTab; label: string }> = [
  { id: "records", label: "Records" }, { id: "reconstruction", label: "Reconstruction" }, { id: "review", label: "Review" }, { id: "workflow", label: "Workflow" }, { id: "audit", label: "Audit" },
];

export function WorkspaceShell({ initialCaseData = mockCaseData, initialReconstruction = reconstructionData, initialTraces = workflowTraceDetails, fixtureOnly = false }: { initialCaseData?: CaseData; initialReconstruction?: ReconstructionData; initialTraces?: WorkflowNodeTrace[]; fixtureOnly?: boolean }) {
  const [caseData, setCaseData] = useState<CaseData>(initialCaseData);
  const [traces, setTraces] = useState<WorkflowNodeTrace[]>(initialTraces);
  const [connectionState, setConnectionState] = useState<"loading" | "ready" | "fallback">(
    !fixtureOnly && threadlineService.configuredMode === "backend" ? "loading" : "fallback",
  );
  const [connectionMessage, setConnectionMessage] = useState(
    threadlineService.configuredMode === "backend" ? "Loading backend incident…" : `Fixture mode — ${MOCK_PROVIDER_LABEL}`,
  );
  const [candidateId, setCandidateId] = useState(initialCaseData.candidates[0]?.candidate_id ?? "");
  const [evidenceSpanId, setEvidenceSpanId] = useState<string | null>(null);
  const [mobileTab, setMobileTab] = useState<MobileTab>("reconstruction");
  const [centerView, setCenterView] = useState<CenterView>("reconstruction");
  const [reviewOutcome, setReviewOutcome] = useState<ReviewOutcome | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>(initialCaseData.audit_events);
  const [savedMessage, setSavedMessage] = useState("");
  const [selection, setSelection] = useState<ReconstructionSelection>({ recordId: initialCaseData.records[0]?.record_id ?? "", factorId: initialCaseData.candidates[0]?.compatibility_factors[0]?.factor_id ?? "", eventId: initialReconstruction.events[0]?.event_id ?? "", locationId: initialReconstruction.locations[0]?.location_id ?? "" });
  const [guidedActive, setGuidedActive] = useState(false);
  const [guidedStep, setGuidedStep] = useState(0);
  const guidedLauncherRef = useRef<HTMLElement | null>(null);

  const candidate = caseData.candidates.find((item) => item.candidate_id === candidateId) ?? caseData.candidates[0];
  const evidenceContract = caseData.evidence_contracts?.find(
    (contract) => contract.candidate_id === candidate.candidate_id,
  ) ?? (caseData.evidence_contract?.candidate_id === candidate.candidate_id ? caseData.evidence_contract : undefined);
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
    if (fixtureOnly || threadlineService.configuredMode !== "backend") return;
    setConnectionState("loading");
    setConnectionMessage("Loading backend incident…");
    try {
      const demo = await threadlineService.getDemoIncident({ signal });
      const requestedRunId = new URL(window.location.href).searchParams.get("run");
      setConnectionMessage(requestedRunId ? "Loading persisted decision package…" : "Running canonical analysis…");
      const analysis = requestedRunId
        ? await threadlineService.getWorkflowRun(requestedRunId, { signal })
        : await threadlineService.analyzeRecords(demo, { signal });
      setConnectionMessage("Verifying decision package…");
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
      setAuditEvents(initialCaseData.audit_events);
      setTraces(initialTraces);
      setConnectionState("fallback");
      setConnectionMessage(FALLBACK_NOTICE);
    }
  }, [fixtureOnly, initialCaseData, initialTraces]);

  useEffect(() => {
    if (fixtureOnly) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => void loadBackendCase(controller.signal), 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [fixtureOnly, loadBackendCase]);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("demo") === "guided") {
      const timer = window.setTimeout(() => {
        setGuidedActive(true);
        setGuidedStep(0);
        setCandidateId(initialCaseData.candidates[0]?.candidate_id ?? "");
        setMobileTab("records");
      }, 0);
      return () => window.clearTimeout(timer);
    }
  }, [initialCaseData.candidates]);

  useEffect(() => {
    if (!guidedActive) return;
    const step = guidedDemoSteps[guidedStep];
    if (!step) return;

    const targetIds = ["case-navigator", "candidate-thread", "evidence-lineage", "contradiction-workspace", "candidate-thread", "evidence-contract", "authorized-review-actions", "panel-center"];
    const timer = window.setTimeout(() => {
      const requestedTarget = document.getElementById(targetIds[guidedStep]);
      const mobileTarget = guidedStep === 0 && window.matchMedia("(max-width: 767px)").matches
        ? document.getElementById("panel-records")
        : null;
      (mobileTarget ?? requestedTarget)?.scrollIntoView({
        block: "center",
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      });
    }, 40);
    return () => window.clearTimeout(timer);
  }, [guidedActive, guidedStep]);

  function chooseCandidate(id: string) {
    const nextCandidate = caseData.candidates.find((item) => item.candidate_id === id);
    setCandidateId(id);
    setSavedMessage("");
    if (nextCandidate) setSelection((current) => ({ ...current, recordId: nextCandidate.record_a_id, factorId: nextCandidate.compatibility_factors[0]?.factor_id ?? "" }));
    setCenterView("reconstruction");
    setMobileTab("reconstruction");
  }

  function beginGuidedDemo(event: ReactMouseEvent<HTMLButtonElement>) {
    guidedLauncherRef.current = event.currentTarget;
    setGuidedActive(true);
    activateGuidedStep(0);
  }

  const exitGuidedDemo = useCallback(() => {
    setGuidedActive(false);
    window.setTimeout(() => {
      const previousLauncher = guidedLauncherRef.current;
      if (previousLauncher?.isConnected) {
        previousLauncher.focus();
        return;
      }
      document.getElementById("guided-demo-launcher")?.focus();
    }, 0);
  }, []);

  function activateGuidedStep(nextStep: number) {
    setGuidedStep(nextStep);
    if (nextStep === 0) {
      setCandidateId(initialCaseData.candidates[0]?.candidate_id ?? "");
      setMobileTab("records");
    } else if (nextStep === 1) {
      setCenterView("reasoning");
      setMobileTab("reconstruction");
    } else if (nextStep === 2) {
      setCenterView("lineage");
      setMobileTab("reconstruction");
    } else if (nextStep === 3) {
      setCenterView("contradictions");
      setMobileTab("reconstruction");
    } else if (nextStep === 4) {
      setCenterView("reasoning");
      setMobileTab("reconstruction");
    } else if (nextStep === 5 || nextStep === 6) {
      setMobileTab("review");
    } else if (nextStep === 7) {
      setCenterView("audit");
      setMobileTab("audit");
    }
  }

  function resetGuidedChallenge() {
    resetDemo();
    setGuidedActive(true);
    setGuidedStep(0);
    setMobileTab("records");
  }

  function viewGuidedTechnicalEvidence(currentStep: number) {
    activateGuidedStep(currentStep);
    const targetIds = ["panel-records", "candidate-thread", "evidence-lineage", "contradiction-workspace", "candidate-thread", "evidence-contract", "authorized-review-actions", "panel-center"];
    window.requestAnimationFrame(() => {
      document.getElementById(targetIds[currentStep] ?? "panel-center")?.scrollIntoView({
        block: "center",
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      });
    });
  }

  function selectRecord(recordId: string) {
    const event = initialReconstruction.events.find((item) => item.record_ids.includes(recordId));
    setSelection((current) => ({ ...current, recordId, eventId: event?.event_id ?? current.eventId, locationId: event?.location_id ?? current.locationId }));
  }

  function selectFactor(factorId: string) {
    const factor = candidate.compatibility_factors.find((item) => item.factor_id === factorId);
    const record = caseData.records.find((item) => item.evidence_spans.some((span) => factor?.evidence_span_ids.includes(span.span_id)));
    if (record) selectRecord(record.record_id);
    setSelection((current) => ({ ...current, factorId }));
  }

  function selectEvent(eventId: string) {
    const event = initialReconstruction.events.find((item) => item.event_id === eventId);
    if (!event) return;
    setSelection((current) => ({ ...current, eventId, locationId: event.location_id, recordId: event.record_ids[0] ?? current.recordId }));
  }

  function selectLocation(locationId: string) {
    const location = initialReconstruction.locations.find((item) => item.location_id === locationId);
    const event = initialReconstruction.events.find((item) => item.location_id === locationId);
    if (!location) return;
    setSelection((current) => ({ ...current, locationId, eventId: event?.event_id ?? current.eventId, recordId: location.record_ids[0] ?? current.recordId }));
  }

  function chooseMobileTab(tab: MobileTab) {
    setMobileTab(tab);
    if (tab === "reconstruction" || tab === "workflow" || tab === "audit") setCenterView(tab);
    if (!window.matchMedia("(max-width: 1180px)").matches) return;
    window.requestAnimationFrame(() => {
      const panelId = tab === "records" ? "panel-records" : tab === "review" ? "panel-review" : "panel-center";
      const panel = document.getElementById(panelId);
      const tabs = document.querySelector<HTMLElement>(".workspace-tabs");
      if (!panel) return;
      const top = Math.max(0, window.scrollY + panel.getBoundingClientRect().top - (tabs?.getBoundingClientRect().height ?? 0));
      window.scrollTo({ top, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    });
  }

  function handleMobileTabKeyDown(event: ReactKeyboardEvent<HTMLButtonElement>, tab: MobileTab) {
    const currentIndex = mobileTabs.findIndex((item) => item.id === tab);
    let nextIndex: number | null = null;

    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % mobileTabs.length;
    else if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + mobileTabs.length) % mobileTabs.length;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = mobileTabs.length - 1;
    if (nextIndex === null) return;

    event.preventDefault();
    const nextTab = mobileTabs[nextIndex];
    chooseMobileTab(nextTab.id);
    window.requestAnimationFrame(() => document.getElementById(`tab-${nextTab.id}`)?.focus());
  }

  async function saveReview(outcome: ReviewOutcome, notes: string, remainingUncertainty: string[], requestedEvidence: string[]) {
    const timestamp = new Date().toISOString();
    const decision = { decision_id: `DECISION-${auditEvents.length + 1}`, candidate_id: candidate.candidate_id, outcome, notes, remaining_uncertainty: remainingUncertainty, requested_evidence: requestedEvidence, workflow_run_id: caseData.workflow_run_id, contract_id: evidenceContract?.contract_id, referenced_artifact_ids: evidenceContract?.violations.flatMap((item) => item.evidence_span_ids ?? []) ?? [], reviewer_role: "Authorized demo reviewer", timestamp };
    if (threadlineService.configuredMode === "backend" && connectionState === "ready") {
      try {
        const receipt = await threadlineService.submitReviewOutcome(caseData.case_id, decision);
        const persisted = await threadlineService.getCaseAudit(caseData.case_id);
        setAuditEvents(persisted);
        setCaseData((current) => ({ ...current, release_state: receipt.release_state }));
        setSavedMessage("Review outcome persisted to the backend audit ledger.");
        setReviewOutcome(null);
        return;
      } catch {
        setSavedMessage("Review was not saved. Retry when the backend is available.");
        return;
      }
    }
    const event: AuditEvent = {
      event_id: `LEDGER-${String(auditEvents.length + 1).padStart(3, "0")}`, timestamp, actor: "Demo reviewer", action: "authorized disposition recorded", detail: `${outcome.replaceAll("_", " ")} — ${notes || "No additional note supplied."}`,
      event_type: "reviewer decision saved", workflow_version: "threadline-workflow/2.0.0-synthetic", prompt_version: "Not applicable", source_record_ids: [candidate.record_a_id, candidate.record_b_id], before_value: "Authorized checkpoint open", after_value: outcome.replaceAll("_", " "), reason: `${notes}. Remaining uncertainty: ${remainingUncertainty.join("; ")}. Requested evidence: ${requestedEvidence.join("; ") || "none"}.`, origin: "human",
    };
    setAuditEvents((current) => [...current, event]);
    setSavedMessage("Fixture mode: review outcome saved in this browser session only.");
    setCaseData((current) => ({
      ...current,
      release_state: { state: "authorized_disposition_recorded", contract_ids: current.evidence_contracts?.map((item) => item.contract_id) ?? [], review_id: decision.decision_id, reviewer_id: decision.reviewer_role, disposition: outcome },
      audit_integrity: current.audit_integrity
        ? {
            ...current.audit_integrity,
            verified_event_count: current.audit_integrity.verified_event_count + 1,
            status: "incomplete",
            valid: false,
            limitation: "The locally appended review event is session-only; backend mode persists and verifies the hash chain.",
          }
        : current.audit_integrity,
    }));
    setReviewOutcome(null);
  }

  function resetDemo() {
    setCaseData(initialCaseData);
    setTraces(initialTraces);
    setCandidateId(initialCaseData.candidates[0]?.candidate_id ?? "");
    setAuditEvents(initialCaseData.audit_events);
    setSelection({ recordId: initialCaseData.records[0]?.record_id ?? "", factorId: initialCaseData.candidates[0]?.compatibility_factors[0]?.factor_id ?? "", eventId: initialReconstruction.events[0]?.event_id ?? "", locationId: initialReconstruction.locations[0]?.location_id ?? "" });
    setEvidenceSpanId(null);
    setCenterView("reconstruction");
    setMobileTab("reconstruction");
    setReviewOutcome(null);
    setSavedMessage("Demo reset to its deterministic initial state.");
    setGuidedActive(false);
    setGuidedStep(0);
  }

  async function runReplay() {
    const certificate = await threadlineService.replayWorkflowRun(caseData.workflow_run_id);
    setCaseData((current) => ({ ...current, latest_replay_certificate: certificate }));
  }

  async function runCounterfactual() {
    const certificate = await threadlineService.runCounterfactual(caseData.workflow_run_id, {
      candidate_id: candidate.candidate_id,
      counterfactual_type: "remove_source_record",
      source_record_id: candidate.record_a_id,
    });
    setCaseData((current) => ({
      ...current,
      counterfactual_certificates: [...(current.counterfactual_certificates ?? []), certificate],
    }));
  }

  async function recordContractExport(contract: NonNullable<CaseData["evidence_contract"]>) {
    await threadlineService.exportEvidenceContract(caseData.workflow_run_id, contract.contract_id);
  }

  return (
    <>
      <section className="incident-strip" aria-label="Incident status">
        <div className="incident-strip__identity"><strong>{caseData.incident.name}</strong><StatusPill tone="teal">Synthetic data</StatusPill></div>
        <dl className="incident-strip__metrics"><div><dt>Records</dt><dd>{caseData.summary.records_processed}</dd></div><div><dt>Languages</dt><dd>{caseData.summary.languages_detected}</dd></div><div><dt>Candidate threads</dt><dd>{caseData.summary.candidate_connections}</dd></div><div><dt>Awaiting review</dt><dd>{caseData.summary.awaiting_human_review}</dd></div></dl>
        <div className="incident-strip__mode" role="status" aria-live="polite"><span className={`mode-dot mode-dot--${connectionState === "ready" ? "backend" : "mock"}`} aria-hidden="true" />{fixtureOnly ? "Deterministic fixture · 0 credits" : connectionMessage}{fixtureOnly ? <button className="button-quiet" type="button" onClick={resetDemo}>Reset demo</button> : connectionState === "fallback" && threadlineService.configuredMode === "backend" ? <button className="button-quiet" type="button" onClick={() => void loadBackendCase()}>Retry</button> : null}</div>
      </section>

      <h1 className="workspace-shell-title">{caseData.incident.name}: evidence resolution workspace</h1>

      <nav className="case-navigator" id="case-navigator" aria-label="Synthetic case navigator">
        <div className="case-navigator__intro">
          <span className="panel-kicker">Synthetic case navigator</span>
          <p>Compare candidate threads without collapsing uncertainty.</p>
        </div>
        <div className="case-navigator__threads">
          {caseData.candidates.map((item, index) => (
            <button
              className={item.candidate_id === candidate.candidate_id ? "is-active" : undefined}
              key={item.candidate_id}
              onClick={() => chooseCandidate(item.candidate_id)}
              type="button"
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{item.candidate_id}</strong>
              <StatusPill tone={item.candidate_id === candidate.candidate_id ? "cyan" : "slate"}>
                {item.classification ?? item.label}
              </StatusPill>
            </button>
          ))}
        </div>
        <button className="button-secondary" onClick={beginGuidedDemo} type="button">Start guided demo</button>
      </nav>

      <div className="workspace-tabs" role="tablist" aria-label="Workspace panels" aria-orientation="horizontal">
        {mobileTabs.map((tab) => <button id={`tab-${tab.id}`} key={tab.id} type="button" role="tab" tabIndex={mobileTab === tab.id ? 0 : -1} aria-selected={mobileTab === tab.id} aria-controls={tab.id === "records" ? "panel-records" : tab.id === "review" ? "panel-review" : "panel-center"} onClick={() => chooseMobileTab(tab.id)} onKeyDown={(event) => handleMobileTabKeyDown(event, tab.id)}>{tab.label}</button>)}
      </div>

      <div className="workspace-grid">
        <aside className={`workspace-column workspace-records ${mobileTab === "records" ? "is-mobile-active" : ""}`} id="panel-records" role="tabpanel" aria-labelledby="tab-records">
          <RecordBrowser records={caseData.records} candidates={caseData.candidates} selectedRecordIds={selectedIds} selectedRecordId={selection.recordId} selectedCandidateId={candidate.candidate_id} onSelectCandidate={chooseCandidate} onSelectRecord={selectRecord} onOpenEvidence={setEvidenceSpanId} />
        </aside>

        <section className={`workspace-column workspace-center ${["reconstruction", "workflow", "audit"].includes(mobileTab) ? "is-mobile-active" : ""}`} id="panel-center" role="tabpanel" aria-labelledby={`tab-${["reconstruction", "workflow", "audit"].includes(mobileTab) ? mobileTab : "reconstruction"}`}>
          <div className="center-toolbar">
            <div className="segmented-control" aria-label="Central workspace view">
              <button type="button" aria-pressed={centerView === "reconstruction"} onClick={() => setCenterView("reconstruction")}>Reconstruction</button>
              <button type="button" aria-pressed={centerView === "lineage"} onClick={() => setCenterView("lineage")}>Source lineage</button>
              <button type="button" aria-pressed={centerView === "contradictions"} onClick={() => setCenterView("contradictions")}>Contradictions</button>
              <button type="button" aria-pressed={centerView === "reasoning"} onClick={() => setCenterView("reasoning")}>Evidence reasoning</button>
              <button type="button" aria-pressed={centerView === "workflow"} onClick={() => setCenterView("workflow")}>Workflow</button>
              <button type="button" aria-pressed={centerView === "audit"} onClick={() => setCenterView("audit")}>Audit</button>
            </div>
            <StatusPill tone={centerView === "workflow" ? "slate" : centerView === "audit" ? "teal" : "cyan"}>{centerView === "workflow" ? caseData.workflow_run_id : centerView === "audit" ? `${auditEvents.length} events` : candidate.classification ?? candidate.label}</StatusPill>
          </div>
          {centerView === "reconstruction" && <ReconstructionCanvas candidate={candidate} records={caseData.records} data={initialReconstruction} selection={selection} onSelectRecord={selectRecord} onSelectFactor={selectFactor} onSelectEvent={selectEvent} onSelectLocation={selectLocation} onOpenEvidence={setEvidenceSpanId} />}
          {centerView === "lineage" && <EvidenceLineage candidate={candidate} records={caseData.records} contract={evidenceContract} selectedFactorId={selection.factorId} onSelectFactor={selectFactor} onOpenEvidence={setEvidenceSpanId} />}
          {centerView === "contradictions" && <ContradictionWorkspace candidate={candidate} records={caseData.records} onOpenEvidence={setEvidenceSpanId} />}
          {centerView === "reasoning" && <CandidateThread candidate={candidate} records={caseData.records} candidates={caseData.candidates} onSelectCandidate={chooseCandidate} onOpenEvidence={setEvidenceSpanId} />}
          {centerView === "workflow" && <WorkflowExplorer nodes={caseData.workflow_trace} traces={traces} />}
          {centerView === "audit" && <AuditLedger events={auditEvents} />}
        </section>

        <aside className={`workspace-column workspace-review ${mobileTab === "review" ? "is-mobile-active" : ""}`} id="panel-review" role="tabpanel" aria-labelledby="tab-review">
          <ReviewPanel candidate={candidate} records={caseData.records} auditEvents={auditEvents} evidenceContract={evidenceContract} auditIntegrity={caseData.audit_integrity} replayManifest={caseData.replay_manifest} replayCertificate={caseData.latest_replay_certificate} counterfactualCertificates={caseData.counterfactual_certificates} savedMessage={savedMessage} onOpenEvidence={setEvidenceSpanId} onOpenReview={(outcome) => setReviewOutcome(outcome ?? "additional_evidence_required")} onReplay={connectionState === "ready" ? runReplay : undefined} onCounterfactual={connectionState === "ready" ? runCounterfactual : undefined} onExportContract={connectionState === "ready" ? recordContractExport : undefined} />
        </aside>
      </div>

      <GuidedDemo active={guidedActive} step={guidedStep} onStart={beginGuidedDemo} onExit={exitGuidedDemo} onReset={resetGuidedChallenge} onStepChange={activateGuidedStep} onOpenSource={setEvidenceSpanId} onViewTechnicalEvidence={viewGuidedTechnicalEvidence} />

      <EvidenceDialog evidence={evidence} onClose={() => setEvidenceSpanId(null)} />
      <ReviewDialog candidateId={candidate.candidate_id} initialOutcome={reviewOutcome} onClose={() => setReviewOutcome(null)} onSave={saveReview} />
    </>
  );
}

function integrateCase(demo: AnalyzeRequest, analysis: AnalyzeResponse): CaseData {
  const contracts = (analysis.evidence_contracts ?? []).filter(isSafeContract);
  const primaryContract = isSafeContract(analysis.evidence_contract) ? analysis.evidence_contract : contracts[0];
  const candidates = analysis.candidates.map((candidate) => {
    return { ...candidate, label: "Output withheld" as const, classification: null, classification_code: null };
  });
  return {
    ...analysis,
    candidates,
    evidence_contract: primaryContract,
    evidence_contracts: contracts,
    contract_release_status: analysis.contract_release_status ?? "withheld",
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

function isSafeContract(value: unknown): value is EvidenceContract {
  if (!value || typeof value !== "object") return false;
  const contract = value as Partial<EvidenceContract>;
  return (
    typeof contract.contract_id === "string"
    && typeof contract.candidate_id === "string"
    && typeof contract.release_allowed === "boolean"
    && Array.isArray(contract.claims)
    && Array.isArray(contract.violations)
    && typeof contract.safety_notice === "string"
  );
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
