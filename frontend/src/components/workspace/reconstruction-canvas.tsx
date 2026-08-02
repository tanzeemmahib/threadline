"use client";

import { StatusPill } from "@/components/status-pill";
import type { CandidateConnection, ReconstructionData, SourceRecord } from "@/types";

export interface ReconstructionSelection {
  recordId: string;
  factorId: string;
  eventId: string;
  locationId: string;
}

const kindLabels = {
  exact: "Exact timestamp",
  estimated: "Estimated timestamp",
  inferred: "Inferred movement",
  contradiction: "Contradiction",
  missing: "Missing information",
  verified: "Verified location",
  approximate: "Approximate location",
};

export function ReconstructionCanvas({
  candidate,
  records,
  data,
  selection,
  onSelectRecord,
  onSelectFactor,
  onSelectEvent,
  onSelectLocation,
  onOpenEvidence,
}: {
  candidate: CandidateConnection;
  records: SourceRecord[];
  data: ReconstructionData;
  selection: ReconstructionSelection;
  onSelectRecord: (recordId: string) => void;
  onSelectFactor: (factorId: string) => void;
  onSelectEvent: (eventId: string) => void;
  onSelectLocation: (locationId: string) => void;
  onOpenEvidence: (spanId: string) => void;
}) {
  const relatedRecordIds = new Set([
    candidate.record_a_id,
    candidate.record_b_id,
    ...data.events.flatMap((event) => event.record_ids),
  ]);
  const relatedRecords = records.filter((record) => relatedRecordIds.has(record.record_id));
  const selectedEvent = data.events.find((event) => event.event_id === selection.eventId) ?? data.events[0];
  const selectedLocation = data.locations.find((location) => location.location_id === selection.locationId) ?? data.locations[0];

  return (
    <div className="reconstruction-canvas">
      <header className="reconstruction-header">
        <div>
          <span className="panel-kicker">Synchronized case reconstruction</span>
          <h2>Evidence path, movement, and incident time</h2>
          <p>Selections are coordinated across all three layers. A plausible route is not proof of identity.</p>
        </div>
        <StatusPill tone="amber">Human verification required</StatusPill>
      </header>
      <ul className="reconstruction-legend" aria-label="Reconstruction evidence legend">
        <li className="legend-exact">Exact timestamp</li><li className="legend-estimated">Estimated timestamp</li><li className="legend-inferred">Inferred movement</li><li className="legend-verified">Verified location</li><li className="legend-approximate">Approximate location</li><li className="legend-contradiction">Contradiction</li><li className="legend-missing">Missing information</li>
      </ul>
      {candidate.candidate_id !== "MATCH-001" && <p className="reconstruction-context-warning" role="note">No candidate-specific route can be reconstructed for this pair. The district route remains visible only as canonical incident context and is not evidence linking these records.</p>}

      <section className="reconstruction-graph" aria-labelledby="record-graph-title">
        <div className="reconstruction-layer-heading">
          <div><span>Layer 01</span><h3 id="record-graph-title">Record relationship graph</h3></div>
          <p>{selection.recordId} selected</p>
        </div>
        <div className="record-graph" role="list" aria-label="Related records and evidence factors">
          <div className="record-graph__records">
            {relatedRecords.map((record) => (
              <button
                className={record.record_id === selection.recordId ? "is-selected" : ""}
                key={record.record_id}
                type="button"
                onClick={() => onSelectRecord(record.record_id)}
              >
                <span>{record.language}</span><strong>{record.record_id}</strong><small>{record.display_name}</small>
              </button>
            ))}
          </div>
          <div className="record-graph__factors">
            {candidate.compatibility_factors.slice(0, 6).map((factor) => (
              <button
                className={`factor-${factor.status} ${factor.factor_id === selection.factorId ? "is-selected" : ""}`}
                key={factor.factor_id}
                type="button"
                onClick={() => onSelectFactor(factor.factor_id)}
              >
                <span>{factor.field}</span><strong>{factor.status.replaceAll("_", " ")}</strong>
              </button>
            ))}
          </div>
        </div>
        <details className="reconstruction-fallback">
          <summary>Text alternative for record graph</summary>
          <p>{candidate.record_a_id} and {candidate.record_b_id} are connected by compatible name, language, location, and timeline factors. Age is a soft conflict; the shelter-only scar is missing from the family report and remains unresolved.</p>
        </details>
      </section>

      <div className="reconstruction-lower-grid">
        <section className="district-map-panel" aria-labelledby="district-map-title">
          <div className="reconstruction-layer-heading">
            <div><span>Layer 02</span><h3 id="district-map-title">Fictional district map</h3></div>
            <p>{data.estimated_travel_window} estimated window</p>
          </div>
          <div className="district-map">
            <svg viewBox="0 0 520 330" role="img" aria-label={data.text_alternative}>
              <desc>{data.text_alternative}</desc>
              <path className="district-road" d="M25 235 C120 210 164 238 230 198 S360 98 495 104" />
              <path className="district-road" d="M70 55 C150 105 232 82 300 122 S400 252 486 275" />
              <path className="district-route" d="M88 170 C160 156 220 110 292 92 S390 116 438 142" />
              <path className="district-route-window" d="M88 170 C160 156 220 110 292 92" />
              {data.locations.map((location) => (
                <g className={`map-location map-location--${location.kind} ${location.location_id === selectedLocation.location_id ? "is-selected" : ""}`} key={location.location_id}>
                  <circle cx={location.x} cy={location.y} r="9" />
                  <text x={location.x + 14} y={location.y + 4}>{location.label}</text>
                </g>
              ))}
            </svg>
            <div className="district-map__controls" aria-label="Select a fictional map location">
              {data.locations.map((location) => (
                <button
                  key={location.location_id}
                  type="button"
                  aria-pressed={location.location_id === selectedLocation.location_id}
                  onClick={() => onSelectLocation(location.location_id)}
                >{location.label}</button>
              ))}
            </div>
          </div>
          <div className="map-selection-detail" aria-live="polite">
            <span>{kindLabels[selectedLocation.kind]}</span><strong>{selectedLocation.label}</strong><p>{selectedLocation.description}</p>
          </div>
          <details className="reconstruction-fallback" open>
            <summary>Route text alternative</summary><p>{data.text_alternative}</p>
          </details>
        </section>

        <section className="incident-timeline-panel" aria-labelledby="incident-timeline-title">
          <div className="reconstruction-layer-heading">
            <div><span>Layer 03</span><h3 id="incident-timeline-title">Incident timeline</h3></div>
            <p>Exact / estimated / inferred</p>
          </div>
          <ol className="incident-timeline">
            {data.events.map((event) => (
              <li key={event.event_id}>
                <button className={event.event_id === selectedEvent.event_id ? "is-selected" : ""} type="button" onClick={() => onSelectEvent(event.event_id)}>
                  <span className={`timeline-kind timeline-kind--${event.timestamp_kind}`}>{event.time}</span>
                  <span><strong>{event.title}</strong><small>{kindLabels[event.timestamp_kind]}</small></span>
                </button>
              </li>
            ))}
          </ol>
          <article className="timeline-selection-detail" aria-live="polite">
            <span>{selectedEvent.time} · {kindLabels[selectedEvent.timestamp_kind]}</span>
            <h4>{selectedEvent.title}</h4><p>{selectedEvent.description}</p>
            <div>{selectedEvent.evidence_span_ids.map((spanId) => <button key={spanId} type="button" onClick={() => onOpenEvidence(spanId)}>{spanId} ↗</button>)}</div>
          </article>
        </section>
      </div>
    </div>
  );
}
