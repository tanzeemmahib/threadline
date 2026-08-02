# Workflow trace schema

Every full analysis returns two synchronized arrays.

`workflow_trace` is the compact frontend-compatible 12-node definition: ID, order, names, category, input, purpose, output summary, method, failure condition, human requirement, constraints, downstream consumer, and nullable demo duration.

`workflow_trace_details` is the executed trace. Every element contains:

- stable node ID/version/name/category and `completed`, `skipped`, or `failed` status;
- model-use and human-input flags;
- start/completion timestamps and measured duration (`null` in deterministic mock traces);
- provider/model and prompt template ID/version where applicable;
- source record IDs and typed input/output schema names;
- structured input/output snapshots;
- deterministic validation results, checks, evidence-span IDs, warnings, failure conditions, and abstention reason;
- actual token usage when the provider reports it, otherwise `null`; estimated cost remains `null`;
- next node, human-review requirement, and before/after state summary.

## Invariants

- Nodes appear exactly in registry order: `incident`, `quarantine`, `extract`, `normalize`, `timeline`, `retrieve`, `hypothesis`, `prosecutor`, `rivals`, `adjudicate`, `privacy`, `review`.
- Record text is quoted untrusted evidence in user prompts and never inserted into system prompts.
- Evidence claims resolve to immutable original text and exact offsets.
- Translation/normalization add representations and never replace originals.
- Mock node latency, token usage, and cost are not invented.
- Disabled nodes are explicit `skipped` traces with an ablation warning.
- The terminal router exposes authorized review actions and no confirm-match shortcut.

Workflow traces are stored inside analysis results and inside the full-system trial output. `workflow_run_id` resolves through the persistence API after restart. Trial evaluation truth and mutation truth metadata are not present in `structured_input`, prompts, or node outputs.
