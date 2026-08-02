from app.schemas.models import Classification, ValidationResult
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext


class HumanReviewRouterNode(WorkflowNode):
    node_id, order = "review", 12
    name, short_name = "Human-review router", "Human review"
    category, purpose = (
        "Human decision",
        "Route candidate packets or abstentions to authorized human procedures.",
    )
    uses_llm, requires_human_input, can_disable = False, True, False
    input_schema, output_schema = "PrivacySafePacket", "HumanReviewRoute"
    failure_condition = (
        "An output implies autonomous identity determination or bypasses authorized review."
    )
    constraints = (
        "No final identity decision",
        "Authorized review required",
        "Abstention retained",
    )

    async def run(self, context: WorkflowContext) -> NodeOutcome:
        insufficient = [
            candidate
            for candidate in context.candidates
            if candidate.classification_code == Classification.insufficient_evidence
        ]
        for candidate in context.candidates:
            context.audit.add(
                "human review requested",
                self.name,
                [candidate.record_a_id, candidate.record_b_id],
                candidate.classification_code.value,
                "Authorized checkpoint open",
                "THREADLINE does not autonomously determine identity.",
            )
        return NodeOutcome(
            summary="All outputs routed to authorized human review; no identity decision was made.",
            data={
                "review_required": True,
                "candidate_packets": len(context.candidates),
                "abstentions": len(insufficient),
                "permitted_actions": [
                    "request_more_information",
                    "dismiss_candidate",
                    "escalate_authorized_review",
                    "mark_unrelated",
                ],
            },
            validation_results=[
                ValidationResult(
                    check="autonomous_identity_decision_blocked",
                    passed=True,
                    detail="The router exposes no confirm-match action.",
                )
            ],
            abstention_reason="The system refuses to select one candidate; human investigation may request more information."
            if insufficient
            else None,
        )
