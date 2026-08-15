import type { CSSProperties } from "react";
import { workflowNodes } from "@/data/mock-data";

const landingStages = [
  { id: "quarantine", label: "Ingest", signal: "Source retained" },
  { id: "extract", label: "Extract", signal: "Fields + spans" },
  { id: "normalize", label: "Normalize", signal: "Originals preserved" },
  { id: "retrieve", label: "Retrieve", signal: "Candidate set" },
  { id: "hypothesis", label: "Compare", signal: "Support assembled" },
  { id: "adjudicate", label: "Policy", signal: "Abstention valid" },
  { id: "review", label: "Review", signal: "Human decision" },
] as const;

export function WorkflowStrip() {
  const nodes = landingStages.map((stage) => ({ stage, node: workflowNodes.find((node) => node.node_id === stage.id) })).filter((item) => item.node !== undefined);

  return (
    <ol className="workflow-strip" aria-label="THREADLINE evidence workflow from ingestion through authorized review">
      {nodes.map(({ stage, node }, index) => (
        <li key={stage.id} style={{ "--workflow-order": index } as CSSProperties}>
          <details className="workflow-step">
            <summary>
              <span className="workflow-step__index">{String(index + 1).padStart(2, "0")}</span>
              <span className="workflow-step__name">{stage.label}</span>
              <span className="workflow-step__marker" aria-hidden="true">+</span>
            </summary>
            <small className="workflow-step__signal">{stage.signal}</small>
            <div className="workflow-step__detail">
              <span>{node?.category}</span>
              <p>{node?.purpose}</p>
              <small>{node?.method}</small>
            </div>
          </details>
          {index < nodes.length - 1 && <span className="workflow-step__connector" aria-hidden="true">→</span>}
        </li>
      ))}
    </ol>
  );
}
