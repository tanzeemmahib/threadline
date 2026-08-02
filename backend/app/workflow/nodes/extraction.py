from __future__ import annotations

from app.prompts import load_prompt
from app.schemas.models import Certainty, ExtractionModelOutput, ValidationResult
from app.services.evidence_validation import validate_all_spans
from app.services.extraction import extract_record
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext


class StructuredExtractionNode(WorkflowNode):
    node_id, order = "extract", 3
    name, short_name = "Structured extraction", "Extract"
    category, purpose = (
        "LLM transformation",
        "Extract typed fields tied to exact original source spans.",
    )
    uses_llm, requires_human_input, can_disable = True, False, False
    input_schema, output_schema = "QuarantinedRecord[]", "ExtractionModelOutput[]"
    failure_condition = (
        "A non-missing field cannot be tied to an exact source span after one retry."
    )
    constraints = ("Schema-valid output", "Missing values remain missing", "Exact offsets required")

    async def run(self, context: WorkflowContext) -> NodeOutcome:
        template = load_prompt("extraction")
        all_validation: list[ValidationResult] = []
        metadata = []
        evidence_ids: list[str] = []
        warnings: list[str] = []
        source_by_id = {record.record_id: record for record in context.request.records}
        for normalized in context.records:
            source = source_by_id[normalized.record_id]
            fields, spans = extract_record(source)
            payload = ExtractionModelOutput(fields=fields, evidence_spans=spans).model_dump(
                mode="json"
            )
            result = await context.provider.generate_structured(
                template_id=template.template_id,
                template_version=template.version,
                system_prompt=template.content,
                user_prompt=f"<untrusted_evidence record_id={source.record_id!r}>\n{normalized.safe_text}\n</untrusted_evidence>",
                response_model=ExtractionModelOutput,
                mock_payload=payload,
            )
            context.model_calls += 1
            context.retries += result.metadata.attempts - 1
            metadata.append(result.metadata)
            output = result.output
            validations = validate_all_spans([source], output.evidence_spans)
            if not all(validation.passed for validation in validations):
                correction = "; ".join(
                    validation.detail for validation in validations if not validation.passed
                )
                retry = await context.provider.generate_structured(
                    template_id=template.template_id,
                    template_version=template.version,
                    system_prompt=template.content,
                    user_prompt=f"<untrusted_evidence record_id={source.record_id!r}>\n{normalized.safe_text}\n</untrusted_evidence>\nExact evidence validation error: {correction}",
                    response_model=ExtractionModelOutput,
                    mock_payload=payload,
                )
                context.model_calls += 1
                context.retries += 1 + retry.metadata.attempts - 1
                metadata.append(retry.metadata)
                output = retry.output
                validations = validate_all_spans([source], output.evidence_spans)
            invalid_ids = {
                span.span_id
                for span in output.evidence_spans
                if source.text[span.start : span.end] != span.quote
            }
            if invalid_ids:
                warnings.append(
                    f"{source.record_id}: unsupported fields removed after evidence retry."
                )
                for field in output.fields:
                    if field.source_span_id in invalid_ids:
                        field.value = None
                        field.normalized_value = None
                        field.certainty = Certainty.missing
                        field.source_span_id = None
                        field.unknown = True
                for span in output.evidence_spans:
                    if span.span_id in invalid_ids:
                        span.valid = False
                        span.validation_error = "Quote and offsets do not match original text."
            normalized.fields = output.fields
            normalized.evidence_spans.extend(output.evidence_spans)
            evidence_ids.extend(span.span_id for span in output.evidence_spans if span.valid)
            all_validation.extend(validations)
            context.audit.add(
                "field extracted",
                self.name,
                [source.record_id],
                "Unstructured narrative",
                f"{len(output.fields)} typed fields",
                "Every supported field retains an exact source-span reference.",
                prompt_version=f"{template.template_id}/{template.version}",
            )
            if source.translated_text:
                context.audit.add(
                    "translation created",
                    self.name,
                    [source.record_id],
                    "Original-language evidence",
                    "Reference translation retained",
                    "Translation is reviewer support; original-language evidence remains authoritative.",
                    prompt_version=f"{template.template_id}/{template.version}",
                )
        return NodeOutcome(
            summary=f"Extracted source-linked fields from {len(context.records)} records.",
            data={"field_count": sum(len(record.fields) for record in context.records)},
            validation_results=all_validation,
            evidence_span_ids=evidence_ids,
            warnings=warnings,
            provider_metadata=metadata,
        )
