"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { StatusPill } from "@/components/status-pill";
import { ThreadButton, ThreadLoader } from "@/components/thread-motion";
import type { WorkflowInspectorTab, WorkflowNode, WorkflowNodeTrace } from "@/types";

const inspectorTabs: WorkflowInspectorTab[] = ["Overview", "Input", "Prompt", "Output", "Validation", "Evidence", "Diff"];

export function WorkflowExplorer({ nodes, traces = [] }: { nodes: WorkflowNode[]; traces?: WorkflowNodeTrace[] }) {
  const [selectedId, setSelectedId] = useState(nodes.at(-1)?.node_id ?? "");
  const [activeIndex, setActiveIndex] = useState(nodes.length - 1);
  const [replaying, setReplaying] = useState(false);
  const [tab, setTab] = useState<WorkflowInspectorTab>("Overview");
  const inspectorTabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const selectedIndex = Math.max(0, nodes.findIndex((node) => node.node_id === selectedId));
  const selected = nodes[selectedIndex] ?? nodes[0];
  const trace = useMemo(() => traces.find((item) => item.node_id === selected?.node_id), [selected?.node_id, traces]);

  useEffect(() => {
    if (!replaying) return;
    const timer = window.setTimeout(() => {
      const nextIndex = activeIndex + 1;
      if (nextIndex >= nodes.length) {
        setReplaying(false);
        setActiveIndex(nodes.length - 1);
        return;
      }
      setActiveIndex(nextIndex);
      if (nodes[nextIndex]) setSelectedId(nodes[nextIndex].node_id);
    }, 420);
    return () => window.clearTimeout(timer);
  }, [activeIndex, nodes, replaying]);

  function selectIndex(index: number) {
    setReplaying(false);
    setActiveIndex(index);
    setSelectedId(nodes[index]?.node_id ?? selectedId);
  }

  function replay() {
    setActiveIndex(0);
    setSelectedId(nodes[0]?.node_id ?? "");
    setReplaying(true);
  }

  function handleInspectorTabKeyDown(event: ReactKeyboardEvent<HTMLButtonElement>, index: number) {
    let nextIndex: number | undefined;

    if (event.key === "ArrowRight") nextIndex = (index + 1) % inspectorTabs.length;
    if (event.key === "ArrowLeft") nextIndex = (index - 1 + inspectorTabs.length) % inspectorTabs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = inspectorTabs.length - 1;
    if (nextIndex === undefined) return;

    event.preventDefault();
    const nextTab = inspectorTabs[nextIndex];
    if (!nextTab) return;
    setTab(nextTab);
    inspectorTabRefs.current[nextIndex]?.focus();
  }

  if (!selected) return null;

  return (
    <div className="workflow-explorer print-page" aria-busy={replaying}>
      <header className="workflow-explorer__header">
        <div>
          <span className="panel-kicker">RUN-001 · Synthetic trace</span>
          <h2>Workflow run inspector</h2>
          <p>Inspect each node’s inputs, prompt boundary, structured output, validation, evidence, and state change.</p>
        </div>
        <div className="workflow-explorer__actions no-print">
          <ThreadButton variant="secondary" motion="connect" type="button" onClick={replay} disabled={replaying}>{replaying ? "Replaying trace…" : "Replay node by node"}</ThreadButton>
          <ThreadButton variant="quiet" motion="quiet" type="button" onClick={() => window.print()}>Print workflow</ThreadButton>
        </div>
      </header>

      {replaying && <div className="workflow-processing" role="status" aria-live="polite" aria-atomic="true"><ThreadLoader compact announce={false} /><div><strong>Workflow processing</strong><span>Replaying deterministic UI state. No model calls are being made.</span></div></div>}

      <div className="workflow-scrubber">
        <label htmlFor="workflow-scrubber"><span>Workflow scrubber</span><strong>{String(activeIndex + 1).padStart(2, "0")} / {String(nodes.length).padStart(2, "0")} · {nodes[activeIndex]?.short_name}</strong></label>
        <input id="workflow-scrubber" type="range" min="0" max={Math.max(0, nodes.length - 1)} value={activeIndex} onChange={(event) => selectIndex(Number(event.target.value))} />
        <div aria-hidden="true">{nodes.map((node, index) => <span className={index <= activeIndex ? "is-complete" : ""} key={node.node_id} />)}</div>
      </div>

      <ol className="workflow-node-grid" aria-label="Twelve-stage THREADLINE workflow">
        {nodes.map((node, index) => {
          const state = index < activeIndex ? "complete" : index === activeIndex ? "active" : "pending";
          return (
            <li key={node.node_id}>
              <button type="button" className={`workflow-node workflow-node--${state} workflow-category--${node.category.toLowerCase().replaceAll(" ", "-").replaceAll("/", "-")}`} aria-pressed={selected.node_id === node.node_id} onClick={() => selectIndex(index)}>
                <span className="workflow-node__top"><span>{String(node.order).padStart(2, "0")}</span><span>{state}</span></span>
                <strong>{node.name}</strong><small>{node.category}</small>
              </button>
              {index < nodes.length - 1 && <span className="workflow-node__connector" aria-hidden="true">↓</span>}
            </li>
          );
        })}
      </ol>

      <article className="workflow-node-detail" aria-live="polite">
        <header>
          <div><span>{selected.node_id} · {trace?.node_version ?? "Synthetic trace"}</span><h3>{selected.name}</h3></div>
          <StatusPill tone={selected.category.includes("Human") ? "amber" : selected.category.includes("LLM") ? "cyan" : "teal"}>{selected.category}</StatusPill>
        </header>
        <div className="inspector-tabs" role="tablist" aria-label="Node inspector sections">
          {inspectorTabs.map((item, index) => <button
            id={`inspector-tab-${item}`}
            key={item}
            ref={(element) => { inspectorTabRefs.current[index] = element; }}
            type="button"
            role="tab"
            tabIndex={tab === item ? 0 : -1}
            aria-selected={tab === item}
            aria-controls="node-inspector-panel"
            onClick={() => setTab(item)}
            onKeyDown={(event) => handleInspectorTabKeyDown(event, index)}
          >{item}</button>)}
        </div>
        <div id="node-inspector-panel" className="node-inspector-panel" role="tabpanel" aria-labelledby={`inspector-tab-${tab}`}>
          {tab === "Overview" && <dl className="inspector-definition-grid">
            <div><dt>Node identifier</dt><dd>{selected.node_id}</dd></div><div><dt>Category</dt><dd>{selected.category}</dd></div><div><dt>Node version</dt><dd>{trace?.node_version ?? "Synthetic trace"}</dd></div><div><dt>Configured model</dt><dd>{trace?.configured_model ?? (selected.method === "Configured LLM" ? "Configured LLM" : "Not applicable")}</dd></div><div><dt>Next node</dt><dd>{trace?.next_node ?? "End of workflow"}</dd></div><div><dt>Human-review requirement</dt><dd>{trace?.human_review_requirement ?? selected.human_input_requirement}</dd></div><div><dt>Duration</dt><dd>{trace?.duration.label ?? "Synthetic trace"} · no value</dd></div><div><dt>Token usage</dt><dd>{trace?.token_usage.label ?? "Synthetic trace"} · no value</dd></div><div><dt>Estimated cost</dt><dd>{trace?.estimated_cost.label ?? "Synthetic trace"} · no value</dd></div>
          </dl>}
          {tab === "Input" && <div className="inspector-stack"><section><h4>Input records</h4><p>{trace?.input_record_ids.join(", ") || "Synthetic trace"}</p></section><section><h4>Input schema</h4><pre>{trace?.input_schema ?? selected.input}</pre></section><section><h4>Input purpose</h4><p>{selected.input}</p></section></div>}
          {tab === "Prompt" && <div className="inspector-stack"><section><h4>Prompt template</h4><pre>{trace?.prompt_template ?? "Synthetic trace"}</pre></section><section><h4>Prompt variables</h4><pre>{JSON.stringify(trace?.prompt_variables ?? {}, null, 2)}</pre></section><p className="synthetic-value-note">No model name is assumed. The frontend only displays “Configured LLM” when a model-backed node is configured.</p></div>}
          {tab === "Output" && <div className="inspector-stack"><section><h4>Structured output</h4><pre>{trace?.structured_output ?? selected.output}</pre></section><section><h4>Output schema</h4><pre>{trace?.output_schema ?? selected.output}</pre></section><section><h4>Abstention reason</h4><p>{trace?.abstention_reason ?? "No abstention recorded for this node."}</p></section></div>}
          {tab === "Validation" && <div className="inspector-stack"><section><h4>Deterministic checks</h4><ul>{(trace?.deterministic_checks ?? selected.constraints).map((check) => <li key={check}>{check}</li>)}</ul></section><section><h4>Warnings</h4>{trace?.warnings.length ? <ul>{trace.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul> : <p>No warning in this synthetic trace.</p>}</section><section><h4>Failure conditions</h4><ul>{(trace?.failure_conditions ?? [selected.failure_condition]).map((condition) => <li key={condition}>{condition}</li>)}</ul></section></div>}
          {tab === "Evidence" && <div className="inspector-stack"><section><h4>Evidence spans referenced</h4><ul className="evidence-chip-list">{(trace?.evidence_span_ids ?? []).map((spanId) => <li key={spanId}>{spanId}</li>)}</ul></section><p>Span identifiers resolve to immutable original-language evidence in the case workspace.</p></div>}
          {tab === "Diff" && <div className="node-state-diff"><div><span>Before {selected.short_name.toLowerCase()}</span><pre>{trace?.before_state ?? selected.input}</pre></div><div><span>After {selected.short_name.toLowerCase()}</span><pre>{trace?.after_state ?? selected.output}</pre></div><p>State changes add structured representations; original evidence is never replaced.</p></div>}
        </div>
      </article>

      <div className="workflow-state-note" role="note"><strong>Partial-stage failure behaviour</strong><p>Original records remain preserved. A stage may be retried or the case can continue with a visible warning and reduced evidence.</p></div>
    </div>
  );
}
