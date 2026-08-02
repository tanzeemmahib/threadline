from app.schemas.models import NormalizedRecord, ValidationResult
from app.services.quarantine import detect_embedded_instructions, safe_evidence_text
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext


class EvidenceQuarantineNode(WorkflowNode):
    node_id, order = "quarantine", 2
    name, short_name = "Evidence quarantine", "Quarantine"
    category, purpose = (
        "Privacy/safety",
        "Treat source narratives as untrusted evidence and isolate tested instruction patterns.",
    )
    uses_llm, requires_human_input, can_disable = False, False, True
    input_schema, output_schema = "RecordInput[]", "QuarantinedRecord[]"
    failure_condition = (
        "Original content cannot be preserved while producing a downstream-safe representation."
    )
    constraints = ("Original text immutable", "Record content never enters system messages")

    async def run(self, context: WorkflowContext) -> NodeOutcome:
        evidence_ids: list[str] = []
        detected_count = 0
        for source in context.request.records:
            detected = detect_embedded_instructions(source)
            detected_count += len(detected)
            evidence_ids.extend(span.span_id for span in detected)
            if detected:
                context.audit.add(
                    "injection quarantined",
                    self.name,
                    [source.record_id],
                    "Untrusted source text",
                    "Original preserved; instruction isolated",
                    "The structured workflow quarantined this tested instruction pattern.",
                )
            translation_warning = None
            if (
                source.translated_text
                and any(marker in source.text.lower() for marker in ("boiter", "limp"))
                and "limp" not in source.translated_text.lower()
            ):
                translation_warning = (
                    "Meaningful detail may be lost: a gait detail in the original is absent "
                    "from the reference translation; original-language review is required."
                )
            context.records.append(
                NormalizedRecord(
                    record_id=source.record_id,
                    source_type=source.source_type,
                    language=source.language,
                    text=source.text,
                    timestamp=source.timestamp,
                    display_name=source.display_name or source.record_id,
                    status="quarantined" if detected else "unresolved",
                    quarantined=bool(detected),
                    quarantine_reason="Embedded instruction detected and excluded from workflow control."
                    if detected
                    else None,
                    safe_text=safe_evidence_text(source, detected),
                    detected_instructions=detected,
                    evidence_spans=list(detected),
                    translated_text=source.translated_text,
                    translation_warning=translation_warning,
                    source_reliability_metadata=source.source_reliability_metadata,
                    reliability_note=source.source_reliability_metadata,
                )
            )
        return NodeOutcome(
            summary=f"Preserved {len(context.records)} records and quarantined {detected_count} tested instruction pattern(s).",
            data={
                "records_preserved": len(context.records),
                "instructions_detected": detected_count,
            },
            validation_results=[
                ValidationResult(
                    check="original_content_preserved",
                    passed=all(
                        source.text == normalized.text
                        for source, normalized in zip(
                            context.request.records, context.records, strict=True
                        )
                    ),
                    detail="Original record text remains byte-for-byte unchanged.",
                )
            ],
            evidence_span_ids=evidence_ids,
            warnings=[]
            if detected_count == 0
            else [
                "Pattern-based quarantine is a tested boundary, not universal prompt-injection protection."
            ],
        )
