from app.schemas.models import ValidationResult
from app.services.timeline_rules import event_sort_key, minutes_from_text
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext


class TimelineReconstructionNode(WorkflowNode):
    node_id, order = "timeline", 5
    name, short_name = "Timeline reconstruction", "Reconstruct"
    category, purpose = (
        "Deterministic validation",
        "Order time/location evidence and validate chronology.",
    )
    uses_llm, requires_human_input, can_disable = False, False, True
    input_schema, output_schema = "NormalizedRecord[]", "TimelineEvent[]"
    failure_condition = "Chronology cannot be represented without converting uncertainty into fact."
    constraints = ("Approximate remains approximate", "Plausible route never proves identity")

    async def run(self, context: WorkflowContext) -> NodeOutcome:
        records = sorted(context.records, key=event_sort_key)
        for record in records:
            minutes = minutes_from_text(record.text)
            if minutes is None and record.timestamp is None:
                continue
            event = {
                "record_id": record.record_id,
                "minutes": minutes,
                "timestamp": record.timestamp.isoformat() if record.timestamp else None,
                "event_kind": "estimated"
                if any(
                    field.key == "timestamp" and field.certainty.value == "estimated"
                    for field in record.fields
                )
                else "exact",
                "identity_proof": False,
            }
            context.timeline_events.append(event)
            context.audit.add(
                "timeline event created",
                self.name,
                [record.record_id],
                "Unordered narrative time",
                str(event),
                "Chronology is represented with its original certainty label.",
            )
        return NodeOutcome(
            summary=f"Created {len(context.timeline_events)} ordered timeline events; plausibility is not identity proof.",
            data={"events": context.timeline_events},
            validation_results=[
                ValidationResult(
                    check="identity_inference_blocked",
                    passed=True,
                    detail="No timeline event is marked as identity proof.",
                )
            ],
            evidence_span_ids=[
                span.span_id
                for record in context.records
                for span in record.evidence_spans
                if span.field in {"Timeline", "Location"}
            ],
            warnings=[],
        )
