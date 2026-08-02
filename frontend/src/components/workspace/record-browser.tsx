"use client";

import { useMemo, useState } from "react";
import { formatTimestamp, sourceTypeLabels } from "@/lib/formatting";
import type { CandidateConnection, CandidateStatus, SourceRecord, SourceType } from "@/types";

const sourceOptions: Array<{ value: "all" | SourceType; label: string }> = [
  { value: "all", label: "All records" },
  { value: "family_report", label: "Family reports" },
  { value: "shelter_record", label: "Shelter records" },
  { value: "hospital_intake", label: "Hospital intake" },
  { value: "evacuation_log", label: "Evacuation logs" },
  { value: "translated_phone_submission", label: "Phone submissions" },
  { value: "volunteer_note", label: "Volunteer notes" },
];

const statusOptions: Array<{ value: "all" | CandidateStatus; label: string }> = [
  { value: "all", label: "All statuses" },
  { value: "unresolved", label: "Unresolved" },
  { value: "candidate", label: "Candidate connections" },
  { value: "conflicting", label: "Conflicting evidence" },
  { value: "insufficient", label: "Insufficient evidence" },
  { value: "quarantined", label: "Quarantined" },
];

export function RecordBrowser({
  records,
  candidates,
  selectedRecordIds,
  selectedRecordId,
  selectedCandidateId,
  onSelectCandidate,
  onSelectRecord,
  onOpenEvidence,
}: {
  records: SourceRecord[];
  candidates: CandidateConnection[];
  selectedRecordIds: Set<string>;
  selectedRecordId: string;
  selectedCandidateId: string;
  onSelectCandidate: (id: string) => void;
  onSelectRecord: (id: string) => void;
  onOpenEvidence: (spanId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState<"all" | SourceType>("all");
  const [status, setStatus] = useState<"all" | CandidateStatus>("all");
  const [language, setLanguage] = useState("all");

  const languages = useMemo(() => [...new Set(records.map((record) => record.language))].sort(), [records]);
  const filtered = useMemo(() => records.filter((record) => {
    const normalizedQuery = query.trim().toLowerCase();
    const matchesQuery = !normalizedQuery || `${record.record_id} ${record.display_name} ${record.text}`.toLowerCase().includes(normalizedQuery);
    return matchesQuery && (source === "all" || record.source_type === source) && (status === "all" || record.status === status) && (language === "all" || record.language === language);
  }), [language, query, records, source, status]);

  return (
    <div className="record-browser">
      <header className="workspace-panel-header">
        <div><span className="panel-kicker">Source stream</span><h1>Records</h1></div>
        <span>{filtered.length} shown</span>
      </header>

      <div className="candidate-switcher" aria-label="Candidate selection">
        {candidates.map((candidate) => (
          <button
            type="button"
            key={candidate.candidate_id}
            aria-pressed={selectedCandidateId === candidate.candidate_id}
            onClick={() => onSelectCandidate(candidate.candidate_id)}
          >
            <span>{candidate.candidate_id}</span>
            <small>{candidate.label}</small>
          </button>
        ))}
      </div>

      <form className="record-filters" onSubmit={(event) => event.preventDefault()}>
        <label className="search-field">
          <span className="sr-only">Search records</span>
          <svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5"/><path d="m13 13 4 4"/></svg>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search records" type="search" />
        </label>
        <div className="filter-grid">
          <label><span>Source</span><select value={source} onChange={(event) => setSource(event.target.value as "all" | SourceType)}>{sourceOptions.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label>
          <label><span>Status</span><select value={status} onChange={(event) => setStatus(event.target.value as "all" | CandidateStatus)}>{statusOptions.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label>
          <label><span>Language</span><select value={language} onChange={(event) => setLanguage(event.target.value)}><option value="all">All languages</option>{languages.map((item) => <option value={item} key={item}>{item}</option>)}</select></label>
        </div>
      </form>

      <div className="record-list" aria-live="polite">
        {filtered.length === 0 ? (
          <div className="workspace-empty"><strong>No records match these filters.</strong><span>Clear a filter or broaden the search text.</span></div>
        ) : filtered.map((record) => (
          <article className={`record-row ${selectedRecordIds.has(record.record_id) ? "is-related" : ""} ${record.record_id === selectedRecordId ? "is-selected" : ""} ${record.quarantined ? "is-quarantined" : ""}`} key={record.record_id}>
            <button className="record-row__select" type="button" onClick={() => onSelectRecord(record.record_id)} aria-pressed={record.record_id === selectedRecordId}>
              <span className="record-row__line"><strong>{record.record_id}</strong><span className={`record-status record-status--${record.status}`}>{record.status.replaceAll("_", " ")}</span></span>
              <span className="record-row__name">{record.display_name}</span>
              <span className="record-row__meta"><span>{sourceTypeLabels[record.source_type]}</span><span>{record.language}</span><span>{formatTimestamp(record.timestamp)}</span></span>
              {record.quarantined && <span className="record-row__quarantine">⊘ Embedded instruction quarantined</span>}
              {record.translation_warning && <span className="record-row__translation-warning">! Translation loss flagged</span>}
            </button>
            {record.evidence_spans[0] && <button className="record-row__evidence" type="button" onClick={() => onOpenEvidence(record.evidence_spans[0].span_id)}>Open evidence ↗</button>}
          </article>
        ))}
      </div>
    </div>
  );
}
