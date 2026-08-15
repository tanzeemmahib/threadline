from __future__ import annotations

import hashlib
import json
from time import perf_counter
from typing import Any

from app.prompts import load_prompt
from app.providers.base import ModelProvider
from app.schemas.models import (
    AnalyzeRequest,
    Classification,
    SingleCallModelOutput,
    SystemOutput,
)
from app.services.extraction import extract_record


def build_input_manifest(request: AnalyzeRequest) -> dict[str, Any]:
    """Return a credential-free digest of the exact records supplied to a system.

    The manifest deliberately hashes raw text instead of duplicating it in stored
    benchmark metadata. Raw text remains available in the case fixture and the
    per-case submission artifact.
    """

    records = [
        {
            "record_id": record.record_id,
            "text": record.text,
        }
        for record in request.records
    ]
    canonical = json.dumps(
        records,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    complete_evidence = json.dumps(
        [record.model_dump(mode="json") for record in request.records],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return {
        "record_count": len(records),
        "record_ids": [record["record_id"] for record in records],
        "text_sha256_by_record": {
            record["record_id"]: hashlib.sha256(record["text"].encode("utf-8")).hexdigest()
            for record in records
        },
        "input_sha256": hashlib.sha256(canonical).hexdigest(),
        "available_evidence_sha256": hashlib.sha256(complete_evidence).hexdigest(),
    }


async def run_single_call(
    request: AnalyzeRequest,
    provider: ModelProvider,  # type: ignore[type-arg]
    *,
    structured: bool,
) -> SystemOutput:
    started = perf_counter()
    system_id = "structured" if structured else "generic"
    template = load_prompt("structured_baseline" if structured else "generic_baseline")
    records = request.records
    candidate_records = records[:2]
    all_spans = []
    candidate_spans = []
    for record in records:
        _, spans = extract_record(record)
        all_spans.extend(spans)
        if record in candidate_records:
            candidate_spans.extend(spans)
    injection = any("ignore previous instructions" in record.text.lower() for record in records)
    if len(candidate_records) < 2:
        classification = Classification.insufficient_evidence
        record_ids: list[str] = []
    elif injection and not structured:
        classification = Classification.strong_candidate_for_review
        record_ids = [record.record_id for record in candidate_records]
    else:
        classification = (
            Classification.possible_candidate
            if candidate_spans
            else Classification.insufficient_evidence
        )
        record_ids = [record.record_id for record in candidate_records]
    fixture = SingleCallModelOutput(
        classification=classification,
        candidate_record_ids=record_ids,
        cited_evidence_span_ids=(
            [span.span_id for span in candidate_spans] if structured else []
        ),
        supporting_evidence=["Narrative fields overlap."] if candidate_spans else [],
        contradictions=[],
        uncertainty=["Authorized human review remains required."],
    )
    evidence_chunks = []
    for record in records:
        metadata = record.model_dump(mode="json")
        metadata.pop("text", None)
        evidence_chunks.append(
            f"<untrusted_evidence record_id={record.record_id!r}>\n"
            f"<record_metadata>{json.dumps(metadata, ensure_ascii=False, sort_keys=True)}</record_metadata>\n"
            f"<record_text>\n{record.text}\n</record_text>\n"
            "</untrusted_evidence>"
        )
    evidence = "\n".join(evidence_chunks)
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
    input_manifest = build_input_manifest(request)
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
            "prompt_template_id": template.template_id,
            "prompt_template_version": template.version,
            "provider_mode": provider.mode,
            "provider_model": provider.model_name,
            "input_manifest": input_manifest,
            "evaluation_warning": (
                "Deterministic mock replay - not model performance."
                if provider.mode == "mock"
                else "Measured provider evaluation."
            ),
        },
        duration_ms=round((perf_counter() - started) * 1000, 3),
        model_calls=1,
        retries=result.metadata.attempts - 1,
    )
