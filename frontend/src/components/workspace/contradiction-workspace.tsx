"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import { StatusPill } from "@/components/status-pill";
import { ConnectionState, ThreadButton } from "@/components/thread-motion";
import type { CandidateConnection, SourceRecord } from "@/types";

export function ContradictionWorkspace({
  candidate,
  records,
  onOpenEvidence,
}: {
  candidate: CandidateConnection;
  records: SourceRecord[];
  onOpenEvidence: (spanId: string) => void;
}) {
  const [conflictId, setConflictId] = useState(candidate.conflicts[0]?.conflict_id ?? "");
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const conflict = candidate.conflicts.find((item) => item.conflict_id === conflictId) ?? candidate.conflicts[0];
  const activeTabIndex = Math.max(candidate.conflicts.findIndex((item) => item.conflict_id === conflict?.conflict_id), 0);
  const sources = conflict?.evidence_span_ids.flatMap((spanId) => {
    for (const record of records) {
      const span = record.evidence_spans.find((item) => item.span_id === spanId);
      if (span) return [{ record, span }];
    }
    return [];
  }) ?? [];

  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") nextIndex = (index + 1) % candidate.conflicts.length;
    if (event.key === "ArrowLeft" || event.key === "ArrowUp") nextIndex = (index - 1 + candidate.conflicts.length) % candidate.conflicts.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = candidate.conflicts.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    const nextConflict = candidate.conflicts[nextIndex];
    if (!nextConflict) return;
    setConflictId(nextConflict.conflict_id);
    tabRefs.current[nextIndex]?.focus();
  }

  return (
    <div className="contradiction-workspace" id="contradiction-workspace" aria-labelledby="contradiction-workspace-title">
      <header className="contradiction-workspace__header">
        <div>
          <span className="panel-kicker">Contradiction workspace</span>
          <h2 id="contradiction-workspace-title">Opposing evidence stays visible.</h2>
          <p>Compare source spans side by side. Absence remains an unresolved gap, not a contradiction.</p>
        </div>
        <div>
          <StatusPill tone={conflict?.severity === "hard" ? "red" : "amber"}>{conflict?.severity ?? "unresolved"}</StatusPill>
          <ConnectionState state={conflict?.severity === "hard" ? "interrupted" : "partial"} label={conflict?.severity === "hard" ? "Hard contradiction interrupts this candidate connection" : "Candidate connection remains unresolved"} />
        </div>
      </header>

      {candidate.conflicts.length ? (
        <>
          <div className="contradiction-tabs" role="tablist" aria-label="Candidate contradictions">
            {candidate.conflicts.map((item, index) => (
              <button
                type="button"
                role="tab"
                key={item.conflict_id}
                id={`contradiction-tab-${index}`}
                ref={(node) => { tabRefs.current[index] = node; }}
                aria-selected={item.conflict_id === conflict?.conflict_id}
                aria-controls="contradiction-comparison"
                tabIndex={item.conflict_id === conflict?.conflict_id ? 0 : -1}
                onClick={() => setConflictId(item.conflict_id)}
                onKeyDown={(event) => handleTabKeyDown(event, index)}
              >
                <span>{item.conflict_id}</span>
                <strong>{item.field}</strong>
              </button>
            ))}
          </div>

          <section id="contradiction-comparison" role="tabpanel" aria-labelledby={`contradiction-tab-${activeTabIndex}`} className="contradiction-comparison">
            <header>
              <span>{conflict.field}</span>
              <h3>{conflict.explanation}</h3>
            </header>
            <div className="contradiction-source-grid">
              {sources.map(({ record, span }) => (
                <article key={span.span_id}>
                  <div><span>{record.record_id}</span><strong>{record.language}</strong></div>
                  <q lang={record.language === "Arabic" ? "ar" : undefined} dir={record.language === "Arabic" ? "rtl" : undefined}>{span.quote}</q>
                  <dl>
                    <div><dt>Offsets</dt><dd>[{span.start}, {span.end})</dd></div>
                    <div><dt>Certainty</dt><dd>{span.certainty}</dd></div>
                  </dl>
                  <ThreadButton variant="secondary" type="button" onClick={() => onOpenEvidence(span.span_id)}>Inspect source span</ThreadButton>
                </article>
              ))}
              {sources.length < 2 ? (
                <article className="contradiction-gap">
                  <div><span>Unresolved gap</span><strong>No paired source span</strong></div>
                  <p>The compared record does not contain this field. THREADLINE preserves the missing value instead of inferring agreement or conflict.</p>
                </article>
              ) : null}
            </div>
          </section>
        </>
      ) : (
        <div className="workspace-empty"><strong>No specific contradiction retained.</strong><span>Missing discriminating evidence still prevents a stronger candidate thread.</span></div>
      )}
    </div>
  );
}
