"use client";

import { useMemo, useState } from "react";
import { StatusPill } from "@/components/status-pill";
import { ConnectionState, ThreadButton } from "@/components/thread-motion";
import type { CandidateConnection, EvidenceContract, OriginalEvidenceSpan, SourceRecord } from "@/types";

const layers = [
  { id: "candidate", index: "01", label: "Candidate claim", help: "Reviewer-facing claim" },
  { id: "normalized", index: "02", label: "Normalized claim", help: "Comparable representation" },
  { id: "extracted", index: "03", label: "Extracted evidence", help: "Typed field with certainty" },
  { id: "source", index: "04", label: "Exact source span", help: "Immutable original text" },
] as const;

export function EvidenceLineage({
  candidate,
  records,
  contract,
  selectedFactorId,
  onSelectFactor,
  onOpenEvidence,
}: {
  candidate: CandidateConnection;
  records: SourceRecord[];
  contract?: EvidenceContract;
  selectedFactorId: string;
  onSelectFactor: (factorId: string) => void;
  onOpenEvidence: (spanId: string) => void;
}) {
  const [layerIndex, setLayerIndex] = useState(0);
  const factor = candidate.compatibility_factors.find((item) => item.factor_id === selectedFactorId)
    ?? candidate.compatibility_factors[0];

  const evidence = useMemo(() => factor.evidence_span_ids.flatMap((spanId) => {
    for (const record of records) {
      const span = record.evidence_spans.find((item) => item.span_id === spanId);
      if (!span) continue;
      const field = record.fields.find((item) => item.source_span_id === spanId);
      return [{ record, span, field }];
    }
    return [];
  }), [factor.evidence_span_ids, records]);

  const relatedClaims = contract?.claims.filter((item) =>
    item.source_spans.some((span) => factor.evidence_span_ids.includes(span.span_id)),
  ) ?? [];
  const normalizedClaim = relatedClaims.find((item) => item.claim_type === "normalized_representation")
    ?? relatedClaims.find((item) => item.claim_type === "compatibility_claim")
    ?? relatedClaims[0];
  const extractedClaims = relatedClaims.filter((item) => item.claim_type === "extracted_fact");

  const activeLayer = layers[layerIndex];
  const stateTone = factor.status === "compatible" ? "cyan" : factor.status === "hard_conflict" ? "red" : "amber";

  return (
    <div className="lineage-workspace" id="evidence-lineage" aria-labelledby="lineage-workspace-title">
      <header className="lineage-workspace__header">
        <div>
          <span className="panel-kicker">Reverse provenance</span>
          <h2 id="lineage-workspace-title">Travel from claim to original source.</h2>
          <p>Each layer is derived from the selected factor. Nothing in this path confirms identity.</p>
        </div>
        <StatusPill tone={stateTone}>{factor.status.replaceAll("_", " ")}</StatusPill>
      </header>

      <div className="lineage-factor-picker" aria-label="Choose a candidate claim">
        {candidate.compatibility_factors.slice(0, 7).map((item) => (
          <button
            type="button"
            key={item.factor_id}
            className={`lineage-factor lineage-factor--${item.status}`}
            aria-pressed={item.factor_id === factor.factor_id}
            onClick={() => {
              setLayerIndex(0);
              onSelectFactor(item.factor_id);
            }}
          >
            <span>{item.factor_id}</span>
            <strong>{item.field}</strong>
          </button>
        ))}
      </div>

      <ol className="lineage-rail" aria-label="Evidence lineage layers">
        {layers.map((layer, index) => (
          <li key={layer.id} className={index <= layerIndex ? "is-traced" : ""}>
            <button
              type="button"
              aria-current={index === layerIndex ? "step" : undefined}
              onClick={() => setLayerIndex(index)}
            >
              <span>{layer.index}</span>
              <strong>{layer.label}</strong>
              <small>{layer.help}</small>
            </button>
          </li>
        ))}
      </ol>

      <section className={`lineage-stage lineage-stage--${activeLayer.id}`} aria-live="polite" aria-atomic="true">
        <div className="lineage-stage__meta">
          <span>Layer {activeLayer.index}</span>
          <ConnectionState
            state={layerIndex === 0 ? "fragmented" : layerIndex === layers.length - 1 ? "connected" : "partial"}
            label={layerIndex === layers.length - 1 ? "Evidence path connected to the original source" : `Evidence path traced through ${layerIndex + 1} of ${layers.length} layers`}
            announce
          />
          <code>{factor.factor_id}</code>
        </div>

        {activeLayer.id === "candidate" ? (
          <article>
            <span>Candidate claim</span>
            <h3>{factor.field}: {factor.interpretation}</h3>
            <p>{candidate.supporting_summary}</p>
          </article>
        ) : null}

        {activeLayer.id === "normalized" ? (
          <article>
            <span>Normalized claim</span>
            <h3>{normalizedClaim?.claim_text ?? `${factor.record_a_value} ↔ ${factor.record_b_value}`}</h3>
            <dl className="lineage-pair">
              <div><dt>{candidate.record_a_id}</dt><dd>{factor.record_a_value}</dd></div>
              <div><dt>{candidate.record_b_id}</dt><dd>{factor.record_b_value}</dd></div>
            </dl>
            <p>{normalizedClaim?.support_reason ?? "Comparable values remain linked to their original source spans and certainty labels."}</p>
            {normalizedClaim ? <dl className="lineage-pair"><div><dt>Transformation</dt><dd>{normalizedClaim.transformation_type?.replaceAll("_", " ") ?? "direct extraction"} · v{normalizedClaim.transformation_version ?? "1.0.0"}</dd></div><div><dt>Certainty</dt><dd>{normalizedClaim.certainty_category ?? Object.values(normalizedClaim.certainty_basis)[0] ?? "inferred"} · no silent increase</dd></div></dl> : null}
          </article>
        ) : null}

        {activeLayer.id === "extracted" ? (
          <article>
            <span>Extracted evidence</span>
            <h3>{evidence.length} typed source field{evidence.length === 1 ? "" : "s"}</h3>
            <div className="lineage-extractions">
              {evidence.map(({ record, span, field }) => (
                <button type="button" key={span.span_id} onClick={() => onOpenEvidence(span.span_id)}>
                  <span>{record.record_id} · {span.certainty}</span>
                  <strong>{field?.label ?? span.field}: {field?.value ?? span.text}</strong>
                  <small>{field?.normalized_value ? `Normalized: ${field.normalized_value}` : "Original value retained"}</small>
                </button>
              ))}
            </div>
            {extractedClaims.length ? <p><strong>{extractedClaims.length} extracted parent claim{extractedClaims.length === 1 ? "" : "s"}</strong> · {extractedClaims.map((item) => item.claim_id).join(", ")}</p> : null}
          </article>
        ) : null}

        {activeLayer.id === "source" ? (
          <article>
            <span>Exact original source span</span>
            <h3>Verified half-open offsets</h3>
            <div className="lineage-spans">
              {evidence.map(({ record, span }) => (
                <SourceSpanCard key={span.span_id} record={record} span={span} onOpenEvidence={onOpenEvidence} />
              ))}
            </div>
            {normalizedClaim?.consumed_by_rule_ids?.length ? <p><strong>Consumed by contract rules:</strong> {normalizedClaim.consumed_by_rule_ids.join(", ")}</p> : null}
          </article>
        ) : null}

        <footer className="lineage-stage__controls">
          <ThreadButton variant="secondary" motion="connect" type="button" disabled={layerIndex === 0} onClick={() => setLayerIndex((current) => Math.max(0, current - 1))}>Forward one layer</ThreadButton>
          <span>{layerIndex + 1} / {layers.length}</span>
          <ThreadButton variant="primary" motion="signature" arrow="forward" type="button" disabled={layerIndex === layers.length - 1} onClick={() => setLayerIndex((current) => Math.min(layers.length - 1, current + 1))}>Trace back to source</ThreadButton>
        </footer>
      </section>
    </div>
  );
}

function SourceSpanCard({ record, span, onOpenEvidence }: { record: SourceRecord; span: OriginalEvidenceSpan; onOpenEvidence: (spanId: string) => void }) {
  const before = record.text.slice(Math.max(0, span.start - 34), span.start);
  const exact = record.text.slice(span.start, span.end) || span.quote;
  const after = record.text.slice(span.end, Math.min(record.text.length, span.end + 42));
  return (
    <button type="button" onClick={() => onOpenEvidence(span.span_id)}>
      <span>{record.record_id} · [{span.start}, {span.end}) · {span.certainty} · {span.validation_status ?? "valid"}</span>
      <q lang={record.language === "Arabic" ? "ar" : undefined} dir={record.language === "Arabic" ? "rtl" : undefined}>
        {before}<mark>{exact}</mark>{after}
      </q>
      <small>{span.content_hash ?? "Validation hash unavailable"} · Open exact source span</small>
    </button>
  );
}
