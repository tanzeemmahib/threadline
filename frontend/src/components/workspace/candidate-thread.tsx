"use client";

import { StatusPill } from "@/components/status-pill";
import { sourceTypeLabels, statusLabels } from "@/lib/formatting";
import type { CandidateConnection, SourceRecord } from "@/types";

const comparisonLabels = {
  name: "Name",
  age: "Age",
  language: "Language",
  location: "Location",
  timeline: "Timeline",
  clothing: "Clothing",
  distinctive_features: "Distinctive features",
  hard_conflicts: "Hard conflicts",
};

export function CandidateThread({
  candidate,
  records,
  candidates,
  onSelectCandidate,
  onOpenEvidence,
}: {
  candidate: CandidateConnection;
  records: SourceRecord[];
  candidates: CandidateConnection[];
  onSelectCandidate: (id: string) => void;
  onOpenEvidence: (spanId: string) => void;
}) {
  const recordA = records.find((record) => record.record_id === candidate.record_a_id);
  const recordB = records.find((record) => record.record_id === candidate.record_b_id);
  const injectionRecord = records.find((record) => record.record_id === "PHONE-066");
  const hardConflict = candidate.compatibility_factors.some((factor) => factor.status === "hard_conflict");

  if (!recordA || !recordB) {
    return <div className="workspace-empty"><strong>Candidate records unavailable.</strong><span>Original records remain preserved. Select another candidate thread.</span></div>;
  }

  return (
    <div className="candidate-thread">
      <header className="candidate-thread__header">
        <div>
          <span className="panel-kicker">Selected evidence path</span>
          <h2>{candidate.label}</h2>
          <p>Human verification required</p>
        </div>
        <div className="candidate-thread__switcher" aria-label="Select candidate thread">
          {candidates.map((item) => (
            <button type="button" key={item.candidate_id} aria-pressed={item.candidate_id === candidate.candidate_id} onClick={() => onSelectCandidate(item.candidate_id)}>{item.candidate_id.replace("MATCH-", "")}</button>
          ))}
        </div>
      </header>

      <figure className={`relationship-map ${hardConflict ? "has-hard-conflict" : ""}`} aria-labelledby="relationship-caption">
        <div className="relationship-map__node relationship-map__node--a">
          <span>{sourceTypeLabels[recordA.source_type]}</span>
          <strong>{recordA.record_id}</strong>
          <small>{recordA.display_name}</small>
        </div>
        <div className="relationship-map__node relationship-map__node--b">
          <span>{sourceTypeLabels[recordB.source_type]}</span>
          <strong>{recordB.record_id}</strong>
          <small>{recordB.display_name}</small>
        </div>
        <div className="relationship-map__evidence relationship-map__evidence--name">Name variant</div>
        <div className="relationship-map__evidence relationship-map__evidence--timeline">Timeline</div>
        <div className="relationship-map__evidence relationship-map__evidence--missing">Missing detail</div>
        <div className="relationship-map__quarantined"><span>⊘</span><strong>PHONE-066</strong><small>Quarantined</small></div>
        <svg viewBox="0 0 860 350" role="img" aria-label={hardConflict ? "A hard conflict interrupts the evidence path between the selected source records." : "Compatibility factors form a candidate path between the selected source records; a missing detail appears as a faded segment and the quarantined record remains isolated."}>
          <path className="map-path map-path--main" d="M190 120 C300 120 300 80 430 80 S550 120 670 120" />
          <path className="map-path map-path--secondary" d="M190 150 C300 150 310 190 430 190 S560 150 670 150" />
          <path className="map-path map-path--missing" d="M430 190 C480 240 540 255 650 255" />
          <path className="map-path map-path--quarantine" d="M94 260 C150 260 172 240 220 240" />
          {hardConflict && <g className="break-mark"><path d="m406 68 18 24 18-24 18 24"/><circle cx="434" cy="80" r="21"/></g>}
        </svg>
        <figcaption id="relationship-caption">
          <span>Data-driven relationship view</span>
          <strong>{hardConflict ? "Hard conflict interrupts the path" : "Candidate path retains uncertainty"}</strong>
        </figcaption>
      </figure>

      <details className="relationship-list" open>
        <summary>List view fallback — same relationship evidence</summary>
        <ul>
          {candidate.compatibility_factors.map((factor) => (
            <li key={factor.factor_id}>
              <span className={`factor-icon factor-icon--${factor.status}`} aria-hidden="true">{factor.status === "compatible" ? "✓" : factor.status === "hard_conflict" ? "×" : factor.status === "soft_conflict" ? "!" : "·"}</span>
              <div><strong>{factor.field} — {statusLabels[factor.status]}</strong><p>{factor.interpretation}</p></div>
            </li>
          ))}
        </ul>
      </details>

      <div className="reasoning-pair">
        <section className="reasoning-case reasoning-case--support" aria-labelledby="match-hypothesis-title">
          <header><span aria-hidden="true">↗</span><div><p>Reasoning stage A</p><h3 id="match-hypothesis-title">Match hypothesis</h3></div></header>
          <p className="reasoning-purpose">Strongest evidence that these records may describe the same fictional person.</p>
          <ul>
            {candidate.compatibility_factors.filter((factor) => factor.status === "compatible").slice(0, 4).map((factor) => (
              <li key={factor.factor_id}>
                <strong>{factor.field}</strong>
                <p>{factor.interpretation}</p>
                <button type="button" onClick={() => onOpenEvidence(factor.evidence_span_ids[0])}>Open source evidence <span aria-hidden="true">↗</span></button>
              </li>
            ))}
            {!candidate.compatibility_factors.some((factor) => factor.status === "compatible") && <li><p>No sufficiently specific supporting factor was extracted.</p></li>}
          </ul>
        </section>

        <section className="reasoning-case reasoning-case--oppose" aria-labelledby="prosecutor-title">
          <header><span aria-hidden="true">⊣</span><div><p>Reasoning stage B</p><h3 id="prosecutor-title">Contradiction prosecutor</h3></div></header>
          <p className="reasoning-purpose">Strongest evidence that these records may describe different people.</p>
          <ul>
            {candidate.conflicts.map((conflict) => (
              <li key={conflict.conflict_id}>
                <strong>{conflict.field} · {conflict.severity} {conflict.severity === "hard" ? "conflict" : ""}</strong>
                <p>{conflict.explanation}</p>
                <button type="button" onClick={() => onOpenEvidence(conflict.evidence_span_ids[0])}>Open source evidence <span aria-hidden="true">↗</span></button>
              </li>
            ))}
            {candidate.conflicts.length === 0 && <li><p>No specific contradiction was available; missing critical information still prevents a useful connection.</p></li>}
          </ul>
        </section>
      </div>

      {candidate.rivals.length > 0 && (
        <section className="rival-section" aria-labelledby="rival-title">
          <div className="rival-section__heading">
            <div><span className="panel-kicker">Specificity check</span><h3 id="rival-title">Nearby rival candidates</h3></div>
            <p>Does this candidate match specifically, or only because the traits are common?</p>
          </div>
          <div className="rival-table-wrap">
            <table className="rival-table">
              <caption className="sr-only">Field-by-field comparison of three fictional shelter candidates.</caption>
              <thead><tr><th scope="col">Candidate</th>{Object.values(comparisonLabels).map((label) => <th scope="col" key={label}>{label}</th>)}</tr></thead>
              <tbody>{candidate.rivals.map((rival) => <tr key={rival.record_id}><th scope="row"><strong>{rival.display_name}</strong><span>{rival.age} · {rival.record_id}</span></th>{Object.keys(comparisonLabels).map((key) => { const value = rival.comparison[key as keyof typeof rival.comparison]; return <td key={key}><span className={`comparison-label comparison-label--${value}`}>{value === "stronger" ? "↑" : value === "weaker" ? "↓" : value === "conflicting" ? "×" : "·"} {value} evidence</span></td>; })}</tr>)}</tbody>
            </table>
          </div>
        </section>
      )}

      {injectionRecord && (
        <section className="injection-demo" aria-labelledby="injection-title">
          <div className="injection-demo__record">
            <StatusPill tone="red">Embedded instruction detected</StatusPill>
            <h3 id="injection-title">Prompt-injection test record</h3>
            <blockquote>{injectionRecord.evidence_spans[0].text}</blockquote>
            <ul><li>Record content preserved</li><li>Instruction quarantined</li><li>Excluded from downstream workflow control</li></ul>
          </div>
          <div className="injection-demo__comparison">
            <div><span>Generic single prompt</span><strong>The injected instruction affected the tested output.</strong></div>
            <div><span>THREADLINE structured workflow</span><strong>The tested instruction was quarantined.</strong></div>
            <p>The workflow resisted this tested injection case. This is not a claim of universal prompt-injection protection.</p>
          </div>
        </section>
      )}
    </div>
  );
}
