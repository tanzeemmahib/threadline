from app.schemas.models import ValidationResult
from app.services.candidate_scoring import retrieve_candidates
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext


class CandidateRetrievalNode(WorkflowNode):
    node_id, order = "retrieve", 6
    name, short_name = "Candidate retrieval", "Retrieve"
    category, purpose = (
        "Retrieval",
        "Retrieve broad candidate pairs with deterministic ranking signals.",
    )
    uses_llm, requires_human_input, can_disable = False, False, False
    input_schema, output_schema = "NormalizedRecord[]", "CandidateConnection[]"
    failure_condition = "No discriminating fields are available; explicit abstention remains valid."
    constraints = (
        "Favor recall",
        "Score is not probability",
        "Missing fields do not automatically discard",
    )

    async def run(self, context: WorkflowContext) -> NodeOutcome:
        context.candidates = retrieve_candidates(
            context.records,
            context.request.options.candidate_limit,
            use_timeline="timeline" not in context.disabled_nodes,
        )
        for candidate in context.candidates:
            context.audit.add(
                "candidate retrieved",
                self.name,
                [candidate.record_a_id, candidate.record_b_id],
                "No candidate pair",
                candidate.candidate_id,
                "Broad deterministic retrieval produced a ranking signal, not an identity probability.",
            )
        abstention = (
            "No discriminating candidate pair was available." if not context.candidates else None
        )
        return NodeOutcome(
            summary=f"Retrieved {len(context.candidates)} candidate pair(s) for review-safe reasoning.",
            data={
                "candidate_ids": [candidate.candidate_id for candidate in context.candidates],
                "ranking_signal_only": True,
            },
            validation_results=[
                ValidationResult(
                    check="no_probability_exposed",
                    passed=True,
                    detail="Scores are explicitly retrieval ranking signals only.",
                )
            ],
            evidence_span_ids=[
                span.span_id for record in context.records for span in record.evidence_spans
            ],
            abstention_reason=abstention,
        )
