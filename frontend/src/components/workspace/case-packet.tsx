import { mockCaseData } from "@/data/mock-data";
import { fullAuditLedger, reconstructionData } from "@/data/research-data";
import { formatTimestamp, sourceTypeLabels } from "@/lib/formatting";

export function CasePacket({ candidateId }: { candidateId: string }) {
  const candidate = mockCaseData.candidates.find((item) => item.candidate_id === candidateId) ?? mockCaseData.candidates[0];
  const recordIds = new Set([candidate.record_a_id, candidate.record_b_id, ...candidate.rivals.map((rival) => rival.record_id)]);
  const records = mockCaseData.records.filter((record) => recordIds.has(record.record_id));

  return (
    <article className="case-packet">
      <header className="case-packet__cover">
        <div><span>THREADLINE / case review packet</span><h1>{candidate.candidate_id}</h1><p>{mockCaseData.incident.name} · {mockCaseData.incident.incident_id}</p></div>
        <aside><strong>Synthetic data</strong><p>Fictional identities and deterministic records. Decision-support only; independent human verification is required.</p></aside>
      </header>

      <section><h2>Selected candidate</h2><dl className="packet-summary"><div><dt>Classification</dt><dd>{candidate.classification ?? candidate.label}</dd></div><div><dt>Records</dt><dd>{candidate.record_a_id} ↔ {candidate.record_b_id}</dd></div><div><dt>Review state</dt><dd>Human verification required</dd></div><div><dt>System boundary</dt><dd>No autonomous identity determination</dd></div></dl></section>

      <section><h2>Source records and original evidence</h2>{records.map((record) => <article className="packet-record" key={record.record_id}><header><strong>{record.record_id}</strong><span>{sourceTypeLabels[record.source_type]} · {record.language} · {formatTimestamp(record.timestamp)}</span></header><p lang={record.language === "Arabic" ? "ar" : undefined} dir={record.language === "Arabic" ? "rtl" : undefined}>{record.text}</p>{record.translated_text && <div><span>Reference translation · {record.translation_provenance ?? "Synthetic fixture"}</span><p>{record.translated_text}</p>{record.translation_warning && <strong className="packet-warning">Translation warning: {record.translation_warning}</strong>}</div>}<dl>{record.fields.map((field) => <div key={field.field_id}><dt>{field.label} · {field.certainty}</dt><dd>{field.value}{field.normalized_value ? ` → candidate representation: ${field.normalized_value}` : ""}</dd></div>)}</dl></article>)}</section>

      <section><h2>Timeline and geographic route</h2><ol className="packet-timeline">{reconstructionData.events.map((event) => <li key={event.event_id}><time>{event.time}</time><div><strong>{event.title}</strong><span>{event.timestamp_kind} · {event.location_id}</span><p>{event.description}</p></div></li>)}</ol><p className="packet-note">{reconstructionData.text_alternative}</p></section>

      <section className="packet-two-column"><article><h2>Supporting hypothesis</h2><p>{candidate.supporting_summary}</p><ul>{candidate.compatibility_factors.filter((factor) => factor.status === "compatible").map((factor) => <li key={factor.factor_id}><strong>{factor.field}:</strong> {factor.interpretation} <span>[{factor.evidence_span_ids.join(", ")}]</span></li>)}</ul></article><article><h2>Contradiction prosecutor</h2><p>{candidate.opposing_summary}</p><ul>{candidate.conflicts.map((conflict) => <li key={conflict.conflict_id}><strong>{conflict.field} · {conflict.severity}:</strong> {conflict.explanation} <span>[{conflict.evidence_span_ids.join(", ")}]</span></li>)}</ul></article></section>

      <section><h2>Rivals, missing information, and adjudication</h2><table><thead><tr><th>Rival</th><th>Summary</th></tr></thead><tbody>{candidate.rivals.map((rival) => <tr key={rival.record_id}><td>{rival.record_id} · {rival.display_name}</td><td>{rival.summary}</td></tr>)}</tbody></table>{candidate.abstention_reasons && <div className="packet-note"><strong>Abstention reasons</strong><ul>{candidate.abstention_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></div>}<p><strong>Adjudicator outcome:</strong> {candidate.classification ?? candidate.label}. The packet is routed to a human checkpoint and does not determine identity.</p></section>

      <section><h2>Suggested verification questions</h2><ol><li>{candidate.verification_question}</li>{candidate.additional_questions.map((question) => <li key={question}>{question}</li>)}</ol></section>

      <section><h2>Workflow audit trail</h2><table><thead><tr><th>Time</th><th>Event</th><th>Actor</th><th>Records</th><th>Reason</th></tr></thead><tbody>{fullAuditLedger.map((event) => <tr key={event.event_id}><td>{formatTimestamp(event.timestamp)}</td><td>{event.event_type}</td><td>{event.actor} · {event.origin}</td><td>{event.source_record_ids?.join(", ")}</td><td>{event.reason}</td></tr>)}</tbody></table></section>

      <section className="packet-review-notes"><h2>Reviewer notes</h2><div aria-label="Blank reviewer notes area" /><p>Authorized reviewer: ____________________ &nbsp;&nbsp; Date: ____________________</p></section>
      <footer><strong>Safety statement</strong><p>THREADLINE proposes candidate record connections for authorized review. It does not prove identity, replace independent verification, or authorize operational action.</p></footer>
    </article>
  );
}

