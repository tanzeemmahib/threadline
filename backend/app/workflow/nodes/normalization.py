from __future__ import annotations

from app.prompts import load_prompt
from app.schemas.models import NormalizationItem, NormalizationModelOutput, ValidationResult
from app.services.normalization import name_variants, normalize_name, normalize_name_fields
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext


class MultilingualNormalizationNode(WorkflowNode):
    node_id, order = "normalize", 4
    name, short_name = "Multilingual normalization", "Normalize"
    category, purpose = (
        "LLM transformation",
        "Add comparable representations without replacing source-language values.",
    )
    uses_llm, requires_human_input, can_disable = True, False, True
    input_schema, output_schema = "ExtractionModelOutput[]", "NormalizationModelOutput[]"
    failure_condition = "A representation loses its original form or evidence link."
    constraints = (
        "Original form preserved",
        "No equivalence claim",
        "Translation-loss warnings retained",
    )

    async def run(self, context: WorkflowContext) -> NodeOutcome:
        template = load_prompt("normalization")
        metadata = []
        validations: list[ValidationResult] = []
        evidence_ids: list[str] = []
        for record in context.records:
            name_field = next(
                (
                    field
                    for field in record.fields
                    if field.key == "name" and isinstance(field.value, str)
                ),
                None,
            )
            if name_field is None:
                continue
            original = str(name_field.value)
            variants = name_variants(original)
            item = NormalizationItem(
                record_id=record.record_id,
                original_form=original,
                normalized_comparison_form=normalize_name(original),
                candidate_variants=variants,
                language=record.language,
                method="deterministic Unicode and transliteration candidates",
                evidence_span_ids=[name_field.source_span_id] if name_field.source_span_id else [],
                compatibility="unresolved",
                warning=record.translation_warning if record.translation_warning else None,
            )
            payload = NormalizationModelOutput(items=[item]).model_dump(mode="json")
            result = await context.provider.generate_structured(
                template_id=template.template_id,
                template_version=template.version,
                system_prompt=template.content,
                user_prompt=f"Original form and source metadata: {item.model_dump_json()}",
                response_model=NormalizationModelOutput,
                mock_payload=payload,
            )
            context.model_calls += 1
            context.retries += result.metadata.attempts - 1
            metadata.append(result.metadata)
            output_item = result.output.items[0]
            preserved = output_item.original_form == original
            validations.append(
                ValidationResult(
                    check="original_form_preserved",
                    passed=preserved,
                    detail=f"Original form for {record.record_id} {'preserved' if preserved else 'changed'}.",
                )
            )
            if preserved:
                record.normalized_names = normalize_name_fields(record.fields)
                record.normalized_names.extend(
                    value
                    for value in output_item.candidate_variants
                    if value not in record.normalized_names
                )
                evidence_ids.extend(output_item.evidence_span_ids)
                context.audit.add(
                    "normalization variant added",
                    self.name,
                    [record.record_id],
                    original,
                    "; ".join(record.normalized_names),
                    "Comparison forms added without replacing original evidence.",
                    prompt_version=f"{template.template_id}/{template.version}",
                )
        return NodeOutcome(
            summary="Multilingual comparison forms added with original values preserved.",
            data={
                "normalized_records": sum(
                    bool(record.normalized_names) for record in context.records
                )
            },
            validation_results=validations,
            evidence_span_ids=evidence_ids,
            warnings=["Candidate transliterations are comparison aids, not equivalence claims."],
            provider_metadata=metadata,
        )
