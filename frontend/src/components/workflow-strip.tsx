import { workflowNodes } from "@/data/mock-data";

const landingNodeIds = [
  "quarantine",
  "extract",
  "normalize",
  "timeline",
  "retrieve",
  "hypothesis",
  "prosecutor",
  "rivals",
  "adjudicate",
  "review",
];

export function WorkflowStrip() {
  const nodes = landingNodeIds.map((id) => workflowNodes.find((node) => node.node_id === id)).filter((node) => node !== undefined);

  return (
    <ol className="workflow-strip">
      {nodes.map((node, index) => (
        <li key={node.node_id}>
          <details className="workflow-step">
            <summary>
              <span className="workflow-step__index">{String(index + 1).padStart(2, "0")}</span>
              <span className="workflow-step__name">{node.short_name}</span>
              <span className="workflow-step__marker" aria-hidden="true">+</span>
            </summary>
            <div className="workflow-step__detail">
              <span>{node.category}</span>
              <p>{node.purpose}</p>
              <small>{node.method}</small>
            </div>
          </details>
          {index < nodes.length - 1 && <span className="workflow-step__connector" aria-hidden="true">→</span>}
        </li>
      ))}
    </ol>
  );
}

