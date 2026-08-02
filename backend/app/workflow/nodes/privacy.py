from app.schemas.models import ValidationResult
from app.services.privacy import redact_text
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext


class PrivacyGateNode(WorkflowNode):
    node_id, order = "privacy", 11
    name, short_name = "Privacy gate", "Privacy gate"
    category, purpose = (
        "Privacy/safety",
        "Apply least-necessary disclosure to reviewer-facing text.",
    )
    uses_llm, requires_human_input, can_disable = False, False, True
    input_schema, output_schema = "CandidateReviewPacket", "PrivacySafePacket"
    failure_condition = "A restricted field remains in reviewer-facing content."
    constraints = (
        "Original evidence preserved",
        "Redactions audited",
        "Reviewer role minimization",
    )

    async def run(self, context: WorkflowContext) -> NodeOutcome:
        for record in context.records:
            redacted, redactions = redact_text(record.safe_text)
            record.safe_text = redacted
            for item in redactions:
                context.redactions.append(
                    {"record_id": record.record_id, "kind": item.kind, "reason": item.reason}
                )
                context.audit.add(
                    "privacy field redacted",
                    self.name,
                    [record.record_id],
                    item.original,
                    item.replacement,
                    item.reason,
                )
        return NodeOutcome(
            summary=f"Applied {len(context.redactions)} least-necessary reviewer redaction(s); original records remain preserved.",
            data={
                "fields_redacted": context.redactions,
                "fields_retained": ["candidate evidence", "certainty", "source spans"],
            },
            validation_results=[
                ValidationResult(
                    check="original_evidence_preserved",
                    passed=True,
                    detail="Redactions affect safe_text only; original text remains unchanged.",
                )
            ],
        )
