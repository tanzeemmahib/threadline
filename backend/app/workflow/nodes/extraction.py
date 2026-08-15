from __future__ import annotations

from app.prompts import load_prompt
from app.providers.openai_compatible import _format_schema_for_prompt
from app.schemas.models import Certainty, ExtractionModelOutput, ValidationResult
from app.services.evidence_validation import validate_all_spans
from app.services.extraction import extract_record
from app.services.field_key_normalizer import (
    NormalizationStatus,
    format_canonical_keys_for_prompt,
    normalize_field_key,
)
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext

# Prompt V2 is the latest promoted prompt with a complete measured live-provider
# benchmark. V3 remains experimental until its safety and extraction gates pass.
PRODUCTION_EXTRACTION_PROMPT_VERSION = "v2"


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
    constraints = ("Schema-valid output", "Missing values remain missing", "Exact offsets required",
                   "Canonical field keys enforced")

    async def run(self, context: WorkflowContext) -> NodeOutcome:
        template = load_prompt("extraction", PRODUCTION_EXTRACTION_PROMPT_VERSION)
        schema_block = _format_schema_for_prompt(ExtractionModelOutput.model_json_schema())
        canonical_keys_block = format_canonical_keys_for_prompt()
        enriched_system_prompt = f"{template.content}\n\n{canonical_keys_block}\n\n{schema_block}"
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
                system_prompt=enriched_system_prompt,
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
                    system_prompt=enriched_system_prompt,
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

            # ── Normalize field keys to canonical form ──
            normalized_fields = []
            for field in output.fields:
                if field.value is None or field.unknown:
                    normalized_fields.append(field)
                    continue
                nk = normalize_field_key(field.key)
                if nk.status in (NormalizationStatus.canonical, NormalizationStatus.normalized_by_alias,
                                 NormalizationStatus.relationship_key):
                    field.key = nk.canonical_key.value
                    if nk.relationship_type and hasattr(field, "__dict__"):
                        object.__setattr__(
                            field, "label", f"{field.label} ({nk.relationship_type})"
                        )
                    normalized_fields.append(field)
                elif nk.status == NormalizationStatus.unknown_review_required:
                    # Sensitive unknown key: mark for human review
                    warnings.append(
                        f"{source.record_id}: unknown field key '{field.key}' looks like an identifier "
                        f"but does not match a canonical key. Field routed to review."
                    )
                    # Preserve the field but it won't participate in scoring
                    field.unknown = True
                    normalized_fields.append(field)
                else:
                    # Harmless unknown: retain but exclude from scoring
                    warnings.append(
                        f"{source.record_id}: non-canonical field key '{field.key}' excluded from comparison."
                    )
                    field.unknown = True
                    normalized_fields.append(field)

            output.fields = normalized_fields
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
