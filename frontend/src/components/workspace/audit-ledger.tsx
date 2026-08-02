"use client";

import { useMemo, useState } from "react";
import { formatTimestamp } from "@/lib/formatting";
import type { AuditEvent } from "@/types";

export function AuditLedger({ events }: { events: AuditEvent[] }) {
  const [origin, setOrigin] = useState<"all" | "human" | "machine">("all");
  const [eventType, setEventType] = useState("all");
  const [query, setQuery] = useState("");
  const eventTypes = [...new Set(events.map((event) => event.event_type ?? event.action))];
  const filtered = useMemo(() => events.filter((event) => {
    const searchText = `${event.event_id} ${event.action} ${event.actor} ${event.source_record_ids?.join(" ")}`.toLowerCase();
    return (origin === "all" || event.origin === origin)
      && (eventType === "all" || (event.event_type ?? event.action) === eventType)
      && (!query.trim() || searchText.includes(query.trim().toLowerCase()));
  }), [eventType, events, origin, query]);

  return (
    <section className="audit-ledger" aria-labelledby="ledger-title">
      <header className="research-panel-header">
        <div><span className="panel-kicker">Complete provenance record</span><h2 id="ledger-title">Case audit ledger</h2><p>Chronological, source-linked events for the synthetic workflow and human checkpoint.</p></div>
        <span>{filtered.length} / {events.length} events</span>
      </header>
      <form className="ledger-filters" onSubmit={(event) => event.preventDefault()}>
        <label><span>Search</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Record, actor, event" /></label>
        <label><span>Event type</span><select value={eventType} onChange={(event) => setEventType(event.target.value)}><option value="all">All event types</option>{eventTypes.map((type) => <option value={type} key={type}>{type}</option>)}</select></label>
        <label><span>Origin</span><select value={origin} onChange={(event) => setOrigin(event.target.value as typeof origin)}><option value="all">Human and machine</option><option value="machine">Machine</option><option value="human">Human</option></select></label>
      </form>
      <ol className="ledger-list" aria-live="polite">
        {filtered.map((event, index) => {
          const day = event.timestamp.slice(0, 10);
          const previousDay = filtered[index - 1]?.timestamp.slice(0, 10);
          return (
            <li key={event.event_id}>
              {day !== previousDay && <h3>{day} · synthetic incident time</h3>}
              <article>
                <div className="ledger-event__rail"><span>{formatTimestamp(event.timestamp)}</span><i aria-hidden="true" /></div>
                <div className="ledger-event__body">
                  <header><div><span>{event.event_id}</span><h4>{event.event_type ?? event.action}</h4></div><span className={`origin-label origin-label--${event.origin ?? "machine"}`}>{event.origin ?? "machine"}</span></header>
                  <p>{event.detail}</p>
                  <dl>
                    <div><dt>Actor</dt><dd>{event.actor}</dd></div>
                    <div><dt>Workflow / prompt</dt><dd>{event.workflow_version ?? "Synthetic trace"}<br />{event.prompt_version ?? "Not applicable"}</dd></div>
                    <div><dt>Source records</dt><dd>{event.source_record_ids?.join(", ") || "No source record"}</dd></div>
                    <div><dt>Reason</dt><dd>{event.reason ?? event.detail}</dd></div>
                  </dl>
                  {(event.before_value || event.after_value) && <div className="ledger-diff"><div><span>Before</span><p>{event.before_value}</p></div><div><span>After</span><p>{event.after_value}</p></div></div>}
                </div>
              </article>
            </li>
          );
        })}
      </ol>
      {filtered.length === 0 && <div className="workspace-empty"><strong>No audit events match.</strong><span>Clear a filter to restore the chronological ledger.</span></div>}
    </section>
  );
}

