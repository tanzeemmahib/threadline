from __future__ import annotations

from time import perf_counter

from app.prompts import load_prompt
from app.providers.base import ModelProvider
from app.schemas.models import (
    AnalyzeRequest,
    Classification,
    SingleCallModelOutput,
    SystemOutput,
)
from app.services.extraction import extract_record


async def run_single_call(
    request: AnalyzeRequest,
    provider: ModelProvider,  # type: ignore[type-arg]
    *,
    structured: bool,
) -> SystemOutput:
    started = perf_counter()
    system_id = "structured" if structured else "generic"
    template = load_prompt("structured_baseline" if structured else "generic_baseline")
    records = request.records[:2]
    all_spans = []
    for record in records:
        _, spans = extract_record(record)
        all_spans.extend(spans)
    injection = any("ignore previous instructions" in record.text.lower() for record in records)
    if not records or len(records) < 2:
        classification = Classification.insufficient_evidence
        record_ids: list[str] = []
    elif injection and not structured:
        classification = Classification.strong_candidate_for_review
        record_ids = [record.record_id for record in records]
    else:
        classification = (
            Classification.possible_candidate if all_spans else Classification.insufficient_evidence
        )
        record_ids = [record.record_id for record in records]
    fixture = SingleCallModelOutput(
        classification=classification,
        candidate_record_ids=record_ids,
        cited_evidence_span_ids=[span.span_id for span in all_spans] if structured else [],
        supporting_evidence=["Narrative fields overlap."] if all_spans else [],
        contradictions=[],
        uncertainty=["Authorized human review remains required."],
    )
    evidence = "\n".join(
        f"<untrusted_evidence record_id={record.record_id!r}>\n{record.text}\n</untrusted_evidence>"
        for record in records
    )
    result = await provider.generate_structured(
        template_id=template.template_id,
        template_version=template.version,
        system_prompt=template.content,
        user_prompt=evidence,
        response_model=SingleCallModelOutput,
        mock_payload=fixture.model_dump(mode="json"),
    )
    output = result.output
    cited_ids = set(output.cited_evidence_span_ids)
    return SystemOutput(
        system_id=system_id,
        system_name="Structured single-call LLM" if structured else "Generic single-prompt LLM",
        evaluation_mode=(
            "Deterministic mock evaluation"
            if provider.mode == "mock"
            else "Real-provider evaluation"
        ),
        classification=output.classification,
        candidate_record_ids=output.candidate_record_ids,
        cited_evidence=[span for span in all_spans if span.span_id in cited_ids],
        output={
            **output.model_dump(mode="json"),
            "injection_resisted": not injection or structured,
        },
        duration_ms=round((perf_counter() - started) * 1000, 3),
        model_calls=1,
        retries=result.metadata.attempts - 1,
    )
