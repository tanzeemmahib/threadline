"use client";

import { useEffect, useRef } from "react";
import { StatusPill } from "@/components/status-pill";
import { certaintyLabels, formatTimestamp, sourceTypeLabels } from "@/lib/formatting";
import type { OriginalEvidenceSpan, SourceRecord } from "@/types";

export function EvidenceDialog({
  evidence,
  onClose,
}: {
  evidence: { record: SourceRecord; span: OriginalEvidenceSpan } | null;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (evidence && dialog && !dialog.open) dialog.showModal();
  }, [evidence]);

  if (!evidence) return null;
  const { record, span } = evidence;
  const field = record.fields.find((item) => item.source_span_id === span.span_id);
  const before = record.text.slice(0, span.start);
  const highlighted = record.text.slice(span.start, span.end);
  const after = record.text.slice(span.end);

  return (
    <dialog className="evidence-dialog" ref={dialogRef} onCancel={onClose} onClose={onClose} aria-labelledby="evidence-dialog-title">
      <div className="dialog-shell">
        <header className="dialog-header">
          <div>
            <span className="panel-kicker">Original source evidence</span>
            <h2 id="evidence-dialog-title">{record.record_id} · {span.field}</h2>
          </div>
          <button className="dialog-close" type="button" onClick={() => dialogRef.current?.close()} aria-label="Close evidence viewer">×</button>
        </header>

        <div className="evidence-metadata">
          <StatusPill tone={record.quarantined ? "red" : "slate"}>{record.quarantined ? "Quarantined" : span.extraction_status.replaceAll("_", " ")}</StatusPill>
          <span>{sourceTypeLabels[record.source_type]}</span><span>{record.language}</span><span>{formatTimestamp(record.timestamp)}</span>
        </div>

        <section className="source-evidence" aria-labelledby="source-text-title">
          <h3 id="source-text-title">Original text</h3>
          <p lang={record.language === "Arabic" ? "ar" : undefined} dir={record.language === "Arabic" ? "rtl" : undefined}>
            {before}<mark>{highlighted || span.text}</mark>{after}
          </p>
        </section>

        {record.translated_text && (
          <section className="translation-note"><h3>Reference translation</h3><p>{record.translated_text}</p>{record.translation_provenance && <small>{record.translation_provenance}</small>}{record.translation_warning && <div className="translation-warning" role="note"><strong>Translation loss flagged</strong><p>{record.translation_warning}</p></div>}</section>
        )}

        <dl className="extraction-detail">
          <div><dt>Extracted field</dt><dd>{field?.label ?? span.field}: {field?.value ?? span.text}</dd></div>
          <div><dt>Extraction status</dt><dd>{span.extraction_status.replaceAll("_", " ")}</dd></div>
          <div><dt>Certainty label</dt><dd>{field ? certaintyLabels[field.certainty] : "Review required"}</dd></div>
          <div><dt>Normalized candidate representation</dt><dd>{field?.normalized_value ?? "No normalized value supplied"}</dd></div>
        </dl>

        <div className="normalization-callout">
          <strong>Interpretation</strong>
          <p>{span.normalization_note ?? "Original evidence preserved without a normalization note."}</p>
        </div>

        <footer className="dialog-footer"><button className="button-secondary" type="button" onClick={() => dialogRef.current?.close()}>Close evidence</button></footer>
      </div>
    </dialog>
  );
}
