"use client";

import { useEffect, useRef, useState } from "react";
import { StatusPill } from "@/components/status-pill";
import { ConnectionState, ThreadButton, ThreadLink, ThreadLoader } from "@/components/thread-motion";
import { v1HeldOutEvidence } from "@/data/v1-evaluation";
import { certaintyLabels, formatTimestamp, sourceTypeLabels, statusLabels } from "@/lib/formatting";
import type {
  AuditEvent,
  AuditIntegrityResult,
  CandidateConnection,
  CounterfactualCertificate,
  EvidenceContract,
  ReplayCertificate,
  ReplayManifest,
  ReviewOutcome,
  SourceRecord,
} from "@/types";

const actionOptions: Array<{ outcome: ReviewOutcome; label: string; tone?: "danger" }> = [
  { outcome: "additional_evidence_required", label: "Additional evidence required" },
  { outcome: "candidate_thread_remains_plausible", label: "Thread remains plausible" },
  { outcome: "escalate_to_authorized_case_process", label: "Escalate to authorized process" },
  { outcome: "candidate_thread_not_supported", label: "Thread not supported", tone: "danger" },
];

export function ReviewPanel({
  candidate,
  records,
  auditEvents,
  evidenceContract,
  auditIntegrity,
  replayManifest,
  replayCertificate,
  counterfactualCertificates,
  savedMessage,
  onOpenEvidence,
  onOpenReview,
  onReplay,
  onCounterfactual,
  onExportContract,
}: {
  candidate: CandidateConnection;
  records: SourceRecord[];
  auditEvents: AuditEvent[];
  evidenceContract?: EvidenceContract;
  auditIntegrity?: AuditIntegrityResult | null;
  replayManifest?: ReplayManifest | null;
  replayCertificate?: ReplayCertificate | null;
  counterfactualCertificates?: CounterfactualCertificate[];
  savedMessage: string;
  onOpenEvidence: (spanId: string) => void;
  onOpenReview: (outcome?: ReviewOutcome) => void;
  onReplay?: () => Promise<void>;
  onCounterfactual?: () => Promise<void>;
  onExportContract?: (contract: EvidenceContract) => Promise<void>;
}) {
  const [operation, setOperation] = useState<"replay" | "counterfactual" | "export" | null>(null);
  const [operationMessage, setOperationMessage] = useState("");
  const recordA = records.find((record) => record.record_id === candidate.record_a_id);
  const recordB = records.find((record) => record.record_id === candidate.record_b_id);

  if (!recordA || !recordB) return null;

  const releaseBlocked = !evidenceContract || !evidenceContract.release_allowed;
  async function runOperation(
    kind: "replay" | "counterfactual" | "export",
    action: (() => Promise<void>) | undefined,
  ) {
    if (!action) return;
    setOperation(kind);
    setOperationMessage("");
    try {
      await action();
      setOperationMessage(kind === "replay" ? "Replay certificate recorded." : kind === "counterfactual" ? "Counterfactual certificate recorded." : "Certificate exported and audit event appended.");
    } catch {
      setOperationMessage(`${kind} could not be completed. The existing decision state was not changed.`);
    } finally {
      setOperation(null);
    }
  }
  const recordSummary = (
    <div className="record-summary-pair">
      {[recordA, recordB].map((record, index) => (
        <article key={record.record_id}>
          <span>Record {index === 0 ? "A" : "B"}</span>
          <strong>{record.record_id}</strong>
          <h3>{record.display_name}</h3>
          <p>{sourceTypeLabels[record.source_type]} · {record.language}</p>
        </article>
      ))}
    </div>
  );

  if (releaseBlocked) {
    return (
      <div className="review-panel review-panel--withheld">
        <header className="review-panel__header review-panel__header--withheld" role="alert" aria-live="assertive">
          <StatusPill tone="red">Contract blocked</StatusPill>
          <ConnectionState state="interrupted" label="Evidence contract blocked; connection incomplete" />
          <h2>OUTPUT WITHHELD — EVIDENCE CONTRACT FAILED</h2>
          <p>No candidate classification was released</p>
        </header>
        {recordSummary}
        <DecisionEvidence candidate={candidate} />
        <ContractPanel contract={evidenceContract} onOpenEvidence={onOpenEvidence} onAuthorizedReview={() => onOpenReview("additional_evidence_required")} onExport={() => runOperation("export", evidenceContract && onExportContract ? () => onExportContract(evidenceContract) : undefined)} exporting={operation === "export"} />
        <section className="review-actions" id="authorized-review-actions" aria-labelledby="blocked-actions-title">
          <div className="review-section-heading"><h3 id="blocked-actions-title">Authorized human review</h3><span>Required by release state</span></div>
          <p>Open the blocked violation, inspect the conflicting spans and rival, then record a structured disposition. THREADLINE does not replace the authorized case process.</p>
          <div className="review-actions__grid">
            {actionOptions.map((action) => <ThreadButton variant={action.tone === "danger" ? "danger" : "secondary"} type="button" key={action.outcome} onClick={() => onOpenReview(action.outcome)}>{action.label}</ThreadButton>)}
          </div>
          <ThreadButton variant="primary" className="review-actions__primary" type="button" onClick={() => onOpenReview("additional_evidence_required")}>Record Authorized Decision</ThreadButton>
          <div className="review-live-message" aria-live="polite">{savedMessage}</div>
        </section>
        <IntegrityPanel auditIntegrity={auditIntegrity} replayManifest={replayManifest} replayCertificate={replayCertificate} counterfactualCertificates={counterfactualCertificates} onReplay={onReplay ? () => runOperation("replay", onReplay) : undefined} onCounterfactual={onCounterfactual ? () => runOperation("counterfactual", onCounterfactual) : undefined} operation={operation} operationMessage={operationMessage} />
        <AuditTrail auditEvents={auditEvents} titleId="withheld-audit-title" />
      </div>
    );
  }

  return (
    <div className="review-panel">
      <header className="review-panel__header">
        <StatusPill tone={candidate.label === "Conflicting evidence" ? "red" : candidate.label === "Insufficient evidence" ? "amber" : "cyan"}>{candidate.classification ?? candidate.label}</StatusPill>
        <ConnectionState state="partial" label="Candidate connection remains under human review" />
        <h2>{candidate.label}</h2>
        <p>Human verification required</p>
      </header>

      {recordSummary}

      <DecisionEvidence candidate={candidate} />

      <ContractPanel contract={evidenceContract} onOpenEvidence={onOpenEvidence} onAuthorizedReview={() => onOpenReview("additional_evidence_required")} onExport={() => runOperation("export", evidenceContract && onExportContract ? () => onExportContract(evidenceContract) : undefined)} exporting={operation === "export"} />

      <IntegrityPanel auditIntegrity={auditIntegrity} replayManifest={replayManifest} replayCertificate={replayCertificate} counterfactualCertificates={counterfactualCertificates} onReplay={onReplay ? () => runOperation("replay", onReplay) : undefined} onCounterfactual={onCounterfactual ? () => runOperation("counterfactual", onCounterfactual) : undefined} operation={operation} operationMessage={operationMessage} />

      {candidate.abstention_reasons && (
        <section className="abstention-outcome" aria-labelledby="abstention-title">
          <span className="panel-kicker">First-class abstention outcome</span>
          <h3 id="abstention-title">The workflow stopped before an unsupported link.</h3>
          <p>Abstention is the safer result when available evidence cannot distinguish this pair from plausible alternatives.</p>
          <ul>{candidate.abstention_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
        </section>
      )}

      <section className="field-comparison" aria-labelledby="comparison-title">
        <div className="review-section-heading"><h3 id="comparison-title">Field comparison</h3><span>{candidate.compatibility_factors.length} factors</span></div>
        <div className="comparison-rows">
          {candidate.compatibility_factors.map((factor) => (
            <article className={`comparison-row comparison-row--${factor.status}`} key={factor.factor_id}>
              <header>
                <span className={`factor-icon factor-icon--${factor.status}`} aria-hidden="true">{factor.status === "compatible" ? "✓" : factor.status === "hard_conflict" ? "×" : factor.status === "soft_conflict" ? "!" : "·"}</span>
                <strong>{factor.field}</strong>
                <span>{statusLabels[factor.status]}</span>
              </header>
              <div className="comparison-row__values">
                <div><span>Record A · {certaintyLabels[factor.certainty_a]}</span><p>{factor.record_a_value}</p></div>
                <div><span>Record B · {certaintyLabels[factor.certainty_b]}</span><p>{factor.record_b_value}</p></div>
              </div>
              <p className="comparison-row__interpretation">{factor.interpretation}</p>
              <div className="comparison-row__evidence">
                {factor.evidence_span_ids.map((spanId, index) => (
                  <button type="button" key={spanId} onClick={() => onOpenEvidence(spanId)}>Evidence {index + 1} <span aria-hidden="true">↗</span></button>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="verification-question" aria-labelledby="verification-title">
        <span className="panel-kicker">Next verification question</span>
        <h3 id="verification-title">{candidate.verification_question}</h3>
        <p>{candidate.verification_explanation}</p>
        <details>
          <summary>Two additional suggested questions</summary>
          <ol>{candidate.additional_questions.map((question) => <li key={question}>{question}</li>)}</ol>
        </details>
      </section>

      <section className="review-actions" id="authorized-review-actions" aria-labelledby="actions-title">
        <div className="review-section-heading"><h3 id="actions-title">Human review actions</h3><span>Audit recorded</span></div>
        <p>These actions record review workflow state. They do not determine identity.</p>
        <div className="review-actions__grid">
          {actionOptions.map((action) => (
            <ThreadButton variant={action.tone === "danger" ? "danger" : "secondary"} type="button" key={action.outcome} onClick={() => onOpenReview(action.outcome)}>{action.label}</ThreadButton>
          ))}
        </div>
        <ThreadButton variant="primary" className="review-actions__primary" type="button" onClick={() => onOpenReview()}>Record Authorized Decision</ThreadButton>
        <ThreadLink variant="bare" motion="quiet" arrow="external" className="button-quiet review-actions__primary" href={`/workspace/packet?candidate=${candidate.candidate_id}`} target="_blank">Export case packet</ThreadLink>
        <div className="review-live-message" aria-live="polite">{savedMessage}</div>
      </section>

      <AuditTrail auditEvents={auditEvents} titleId="audit-title" />
    </div>
  );
}

function ContractPanel({
  contract,
  onOpenEvidence,
  onAuthorizedReview,
  onExport,
  exporting,
}: {
  contract?: EvidenceContract;
  onOpenEvidence: (spanId: string) => void;
  onAuthorizedReview: () => void;
  onExport: () => void;
  exporting: boolean;
}) {
  const [validationState, setValidationState] = useState<"idle" | "validating" | "success" | "warning" | "failure">("idle");
  const validationTimer = useRef<number | null>(null);

  useEffect(() => () => {
    if (validationTimer.current !== null) window.clearTimeout(validationTimer.current);
  }, []);

  if (!contract) {
    return (
      <section className="evidence-contract evidence-contract--blocked" id="evidence-contract" aria-labelledby="contract-title">
        <span className="panel-kicker">Release gate</span>
        <h3 id="contract-title">Evidence contract unavailable</h3>
        <p>The output remains withheld until deterministic verification completes.</p>
        <ConnectionState state="interrupted" label="Evidence contract unavailable; connection incomplete" />
        <ThreadButton variant="primary" type="button" disabled>Run Evidence Contract</ThreadButton>
      </section>
    );
  }

  const statusLabel = contract.contract_status.replaceAll("_", " ");
  const runValidation = () => {
    if (validationState === "warning") {
      document.getElementById("contract-violations")?.scrollIntoView({ block: "center" });
      return;
    }
    if (validationState === "success") {
      onAuthorizedReview();
      return;
    }
    setValidationState("validating");
    if (validationTimer.current !== null) window.clearTimeout(validationTimer.current);
    validationTimer.current = window.setTimeout(() => {
      setValidationState(contract.contract_status === "verifier_error" ? "failure" : contract.release_allowed ? "success" : "warning");
      validationTimer.current = null;
    }, 800);
  };
  const actionLabel = validationState === "validating"
    ? "Validating Evidence…"
    : validationState === "success"
      ? "Send to Authorized Review"
      : validationState === "warning"
        ? "Resolve Contract Violations"
        : validationState === "failure"
          ? "Retry Evidence Contract"
          : "Run Evidence Contract";

  return (
    <section
      className={`evidence-contract evidence-contract--${contract.release_allowed ? "passed" : "blocked"}`}
      id="evidence-contract"
      aria-labelledby="contract-title"
    >
      <header className="evidence-contract__header">
        <div>
          <span className="panel-kicker">Deterministic release gate</span>
          <h3 id="contract-title">Evidence contract</h3>
        </div>
        <div>
          <StatusPill tone={contract.release_allowed ? "teal" : "red"}>{statusLabel}</StatusPill>
          <ConnectionState state={contract.release_allowed ? "partial" : "interrupted"} label={contract.release_allowed ? "Contract evaluated; human review remains required" : "Contract blocked; connection incomplete"} />
        </div>
      </header>

      <dl className="evidence-contract__summary">
        <div><dt>Contract</dt><dd>{contract.contract_id}</dd></div>
        <div><dt>Verifier</dt><dd>{contract.verifier_version}</dd></div>
        <div><dt>Claims</dt><dd>{contract.claims.length}</dd></div>
        <div><dt>Violations</dt><dd>{contract.violations.length}</dd></div>
        <div><dt>Passed</dt><dd>{contract.rule_results?.filter((item) => (item.status ?? (item.passed ? "pass" : "fail")) === "pass").length ?? 0}</dd></div>
        <div><dt>Warnings</dt><dd>{contract.rule_results?.filter((item) => item.status === "warn").length ?? 0}</dd></div>
        <div><dt>Blocking</dt><dd>{contract.rule_results?.filter((item) => item.status === "block").length ?? contract.violations.filter((item) => item.blocks_release).length}</dd></div>
      </dl>

      {contract.rule_results?.length ? (
        <div className="contract-rule-matrix" aria-label="Evidence contract rule results">
          {(["blocking", "review_required", "informational"] as const).map((ruleClass) => {
            const rules = contract.rule_results?.filter((item) => item.rule_class === ruleClass) ?? [];
            if (!rules.length) return null;
            return (
              <section key={ruleClass} aria-labelledby={`rules-${ruleClass}`}>
                <h4 id={`rules-${ruleClass}`}>{ruleClass.replaceAll("_", " ")} rules</h4>
                <ul>
                  {rules.map((rule) => (
                    <li key={rule.rule_id} className={rule.passed ? "rule-result--passed" : "rule-result--failed"}>
                      <strong>{rule.rule_id} · {rule.status ?? (rule.passed ? "pass" : "fail")}</strong>
                      <p>{rule.operator_explanation}</p>
                      {rule.reason_code ? <code>{rule.reason_code}</code> : null}
                      {!rule.passed ? <span>{rule.remediation_guidance}</span> : null}
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      ) : null}

      {contract.candidate_ledger ? (
        <section className="candidate-ledger-summary" aria-labelledby="candidate-ledger-title">
          <div className="review-section-heading"><h4 id="candidate-ledger-title">Candidate-scoped ledger</h4><span>{contract.candidate_ledger.ledger_id}</span></div>
          <dl className="evidence-contract__summary">
            <div><dt>Supporting</dt><dd>{contract.candidate_ledger.supporting_claim_ids.length}</dd></div>
            <div><dt>Contradictions</dt><dd>{contract.candidate_ledger.contradiction_claim_ids.length}</dd></div>
            <div><dt>Rival claims</dt><dd>{contract.candidate_ledger.rival_comparison_claim_ids.length}</dd></div>
            <div><dt>Missing</dt><dd>{contract.candidate_ledger.missing_evidence.length}</dd></div>
          </dl>
          {contract.candidate_ledger.required_follow_up_evidence.length ? <ul>{contract.candidate_ledger.required_follow_up_evidence.map((item) => <li key={item}>{item}</li>)}</ul> : null}
        </section>
      ) : null}

      {contract.violations.length > 0 ? (
        <div className="contract-violations" id="contract-violations" role="alert" aria-label="Evidence contract violations">
          <h4>Release-blocking violations</h4>
          <ul>
            {contract.violations.map((violation) => (
              <li key={violation.violation_id}>
                <strong>{violation.rule_id} · {violation.severity}</strong>
                <p>{violation.message}</p>
                <span>{violation.suggested_resolution}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="contract-claims">
        <div className="review-section-heading"><h4>Claim ledger</h4><span>Exact source spans</span></div>
        <ol>
          {contract.claims.map((claim) => (
            <li key={claim.claim_id} className={claim.supported ? "" : "contract-claim--unsupported"}>
              <details>
                <summary>
                  <span>{claim.claim_type.replaceAll("_", " ")}</span>
                  <strong>{claim.claim_text}</strong>
                </summary>
                <p>{claim.support_reason}</p>
                <dl>
                  <div><dt>Generated by</dt><dd>{claim.generated_by_node}</dd></div>
                  <div><dt>Support</dt><dd>{claim.supported ? "Supported" : "Unsupported"}</dd></div>
                </dl>
                <div className="contract-source-spans">
                  {claim.source_spans.length > 0 ? claim.source_spans.map((span) => (
                    <button type="button" key={span.span_id} onClick={() => onOpenEvidence(span.span_id)}>
                      <span>{span.record_id} [{span.start}, {span.end}) · {span.certainty}</span>
                      <q>{span.quote}</q>
                    </button>
                  )) : <span>No quoted span; deterministic workflow interpretation.</span>}
                </div>
              </details>
            </li>
          ))}
        </ol>
      </div>

      <p className="evidence-contract__notice">{contract.safety_notice}</p>
      <LineagePanel contract={contract} />
      <ThreadButton
        variant="primary"
        className={`evidence-contract__action is-${validationState}`}
        type="button"
        aria-busy={validationState === "validating"}
        disabled={validationState === "validating"}
        onClick={runValidation}
      >
        {validationState === "validating" ? <ThreadLoader label="Validating evidence" compact announce={false} /> : null}
        {actionLabel}
      </ThreadButton>
      <div className="review-live-message" role="status" aria-live="polite">
        {validationState === "success" ? "Evidence contract passed. Human authorization is still required." : null}
        {validationState === "warning" ? "Release remains blocked until the listed violations are resolved." : null}
        {validationState === "failure" ? "The verifier failed safely. No decision state was changed; retry is available." : null}
      </div>
      <ThreadButton variant="quiet" className="evidence-contract__export" type="button" aria-busy={exporting} disabled={exporting} onClick={() => { downloadContract(contract); onExport(); }}>
        {exporting ? <ThreadLoader label="Recording export" compact announce={false} /> : null}
        {exporting ? "Recording export…" : "Export certificate"}
      </ThreadButton>
    </section>
  );
}

function DecisionEvidence({ candidate }: { candidate: CandidateConnection }) {
  const strongest = candidate.compatibility_factors
    .filter((factor) => factor.status === "compatible")
    .slice(0, 3);
  return (
    <section className="decision-evidence" aria-labelledby="why-candidate-title">
      <div className="decision-evidence__column">
        <span className="panel-kicker">Why this candidate</span>
        <h3 id="why-candidate-title">Observable support</h3>
        {strongest.length ? (
          <ul>{strongest.map((factor) => <li key={factor.factor_id}><strong>{factor.field}</strong><span>{factor.interpretation}</span></li>)}</ul>
        ) : <p>No compatible factor is strong enough to summarize as support.</p>}
      </div>
      <div className="decision-evidence__column">
        <span className="panel-kicker">Why not the rivals</span>
        <h3>Specificity check</h3>
        {candidate.rivals.length ? (
          <ul>{candidate.rivals.slice(0, 3).map((rival) => <li key={rival.record_id}><strong>{rival.display_name}</strong><span>{rival.summary}</span></li>)}</ul>
        ) : <p>No nearby rival was retained for this candidate.</p>}
      </div>
    </section>
  );
}

function IntegrityPanel({
  auditIntegrity,
  replayManifest,
  replayCertificate,
  counterfactualCertificates = [],
  onReplay,
  onCounterfactual,
  operation,
  operationMessage,
}: {
  auditIntegrity?: AuditIntegrityResult | null;
  replayManifest?: ReplayManifest | null;
  replayCertificate?: ReplayCertificate | null;
  counterfactualCertificates?: CounterfactualCertificate[];
  onReplay?: () => void;
  onCounterfactual?: () => void;
  operation: "replay" | "counterfactual" | "export" | null;
  operationMessage: string;
}) {
  return (
    <section className="integrity-panel" aria-labelledby="integrity-title">
      <header>
        <div><span className="panel-kicker">Integrity</span><h3 id="integrity-title">Decision reproducibility</h3></div>
        <StatusPill tone={auditIntegrity?.valid ? "teal" : "red"}>{auditIntegrity?.status ?? "unverified"}</StatusPill>
      </header>
      <dl className="integrity-grid">
        <div><dt>Audit chain</dt><dd>{auditIntegrity?.valid ? `Valid · ${auditIntegrity.verified_event_count} events` : auditIntegrity?.status ?? "Unavailable"}</dd></div>
        <div><dt>Replay</dt><dd>{replayCertificate?.replay_status.replaceAll("_", " ") ?? (replayManifest ? "Manifest captured" : "Unavailable")}</dd></div>
        <div><dt>Counterfactuals</dt><dd>{counterfactualCertificates.length} certificate{counterfactualCertificates.length === 1 ? "" : "s"}</dd></div>
        <div><dt>Hash algorithm</dt><dd>{auditIntegrity?.hash_algorithm ?? "—"}</dd></div>
      </dl>
      {auditIntegrity?.terminal_hash ? <div className="integrity-hash"><span>Terminal chain hash</span><code>{auditIntegrity.terminal_hash}</code></div> : null}
      {!auditIntegrity?.valid && auditIntegrity ? (
        <div className="integrity-failure" role="alert">
          <strong>Integrity verification failed at sequence {auditIntegrity.first_invalid_sequence ?? "unknown"}.</strong>
          <p>Decision release must remain withheld until the chain verifies.</p>
        </div>
      ) : null}
      <div className="integrity-actions">
        <ThreadButton variant="secondary" type="button" aria-busy={operation === "replay"} disabled={!replayManifest || !onReplay || operation !== null} onClick={() => onReplay?.()}>
          {operation === "replay" ? <ThreadLoader label="Replaying deterministic decision" compact announce={false} /> : null}
          {operation === "replay" ? "Replaying…" : "Run deterministic replay"}
        </ThreadButton>
        <ThreadButton variant="secondary" type="button" aria-busy={operation === "counterfactual"} disabled={!onCounterfactual || operation !== null} onClick={() => onCounterfactual?.()}>
          {operation === "counterfactual" ? <ThreadLoader label="Testing evidence removal" compact announce={false} /> : null}
          {operation === "counterfactual" ? "Testing evidence…" : "Test first source removal"}
        </ThreadButton>
      </div>
      <div className="review-live-message" aria-live="polite" aria-atomic="true">{operationMessage}</div>
      {replayCertificate?.first_divergence ? <p className="integrity-divergence">Earliest replay divergence: <strong>{replayCertificate.first_divergence}</strong></p> : null}
      {counterfactualCertificates.length ? (
        <div className="decision-critical" aria-labelledby="decision-critical-title">
          <h4 id="decision-critical-title">Decision-critical evidence</h4>
          <ol>{counterfactualCertificates.map((item) => (
            <li key={item.certificate_id}>
              <strong>{item.decision_changed ? "Decision changed" : "Decision stable"} · {item.counterfactual_type.replaceAll("_", " ")}</strong>
              <span>{item.original_classification ?? "withheld"} → {item.counterfactual_classification ?? "withheld"}</span>
              <p>Rank {item.original_rank ?? "—"} → {item.counterfactual_rank ?? "—"}; score {item.original_score?.toFixed(3) ?? "—"} → {item.counterfactual_score?.toFixed(3) ?? "—"}. First changed node: {item.first_responsible_node}.</p>
            </li>
          ))}</ol>
        </div>
      ) : null}
      <div className="risk-bound-note">
        <strong>Held-out synthetic risk artifact</strong>
        <p>{v1HeldOutEvidence.label}</p>
        <span>{v1HeldOutEvidence.limitation}</span>
      </div>
      <p className="integrity-limitation">Tamper evidence detects persisted changes; it does not prevent offline modification.</p>
    </section>
  );
}

function LineagePanel({ contract }: { contract: EvidenceContract }) {
  const derivedClaims = contract.claims.filter((claim) => claim.parent_claim_ids?.length).slice(0, 8);
  return (
    <div className="claim-lineage" aria-labelledby="claim-lineage-title">
      <div className="review-section-heading"><h4 id="claim-lineage-title">Claim lineage</h4><span>Source → rule → decision</span></div>
      {derivedClaims.length ? <ol>{derivedClaims.map((claim) => (
        <li key={claim.claim_id}>
          <span>{claim.source_record_ids.join(", ")}</span>
          <span aria-hidden="true">→</span>
          <span>{claim.source_span_ids?.length ?? claim.source_spans.length} span{(claim.source_span_ids?.length ?? claim.source_spans.length) === 1 ? "" : "s"}</span>
          <span aria-hidden="true">→</span>
          <span>{claim.transformation_type?.replaceAll("_", " ") ?? claim.claim_type.replaceAll("_", " ")}</span>
          <span aria-hidden="true">→</span>
          <span>{claim.generated_by_node}</span>
          <span aria-hidden="true">→</span>
          <strong>{claim.violations.length ? "blocked/review" : "contract evaluated"}</strong>
        </li>
      ))}</ol> : <p>Direct extracted claims are retained; no derived lineage path is available.</p>}
    </div>
  );
}

function downloadContract(contract: EvidenceContract) {
  const blob = new Blob([JSON.stringify(contract, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${contract.contract_id}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function AuditTrail({ auditEvents, titleId }: { auditEvents: AuditEvent[]; titleId: string }) {
  return (
    <section className="audit-trail" aria-labelledby={titleId}>
      <div className="review-section-heading"><h3 id={titleId}>Audit trail</h3><span>{auditEvents.length} events</span></div>
      <ol>
        {[...auditEvents].reverse().slice(0, 5).map((event) => (
          <li key={event.event_id}>
            <span>{formatTimestamp(event.timestamp)}</span>
            <strong>{event.action}</strong>
            <p>{event.detail}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
