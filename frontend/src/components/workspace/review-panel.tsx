"use client";

import Link from "next/link";
import { StatusPill } from "@/components/status-pill";
import { certaintyLabels, formatTimestamp, sourceTypeLabels, statusLabels } from "@/lib/formatting";
import type { AuditEvent, CandidateConnection, ReviewOutcome, SourceRecord } from "@/types";

const actionOptions: Array<{ outcome: ReviewOutcome; label: string; tone?: "danger" }> = [
  { outcome: "request_more_information", label: "Request more information" },
  { outcome: "dismiss_candidate", label: "Dismiss candidate" },
  { outcome: "escalate_authorized_review", label: "Escalate for authorized review" },
  { outcome: "mark_unrelated", label: "Mark records as unrelated", tone: "danger" },
];

export function ReviewPanel({
  candidate,
  records,
  auditEvents,
  savedMessage,
  onOpenEvidence,
  onOpenReview,
}: {
  candidate: CandidateConnection;
  records: SourceRecord[];
  auditEvents: AuditEvent[];
  savedMessage: string;
  onOpenEvidence: (spanId: string) => void;
  onOpenReview: (outcome?: ReviewOutcome) => void;
}) {
  const recordA = records.find((record) => record.record_id === candidate.record_a_id);
  const recordB = records.find((record) => record.record_id === candidate.record_b_id);

  if (!recordA || !recordB) return null;

  return (
    <div className="review-panel">
      <header className="review-panel__header">
        <StatusPill tone={candidate.label === "Conflicting evidence" ? "red" : candidate.label === "Insufficient evidence" ? "amber" : "cyan"}>{candidate.classification ?? candidate.label}</StatusPill>
        <h2>{candidate.label}</h2>
        <p>Human verification required</p>
      </header>

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

      <section className="review-actions" aria-labelledby="actions-title">
        <div className="review-section-heading"><h3 id="actions-title">Human review actions</h3><span>Audit recorded</span></div>
        <p>These actions record review workflow state. They do not determine identity.</p>
        <div className="review-actions__grid">
          {actionOptions.map((action) => (
            <button className={action.tone === "danger" ? "button-danger" : "button-secondary"} type="button" key={action.outcome} onClick={() => onOpenReview(action.outcome)}>{action.label}</button>
          ))}
        </div>
        <button className="button-primary review-actions__primary" type="button" onClick={() => onOpenReview()}>Record authorized verification outcome</button>
        <Link className="button-quiet review-actions__primary" href={`/workspace/packet?candidate=${candidate.candidate_id}`} target="_blank">Export case packet ↗</Link>
        <div className="review-live-message" aria-live="polite">{savedMessage}</div>
      </section>

      <section className="audit-trail" aria-labelledby="audit-title">
        <div className="review-section-heading"><h3 id="audit-title">Audit trail</h3><span>{auditEvents.length} events</span></div>
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
    </div>
  );
}
