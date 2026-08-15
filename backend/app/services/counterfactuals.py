from __future__ import annotations

from app.schemas.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    CandidateConnection,
    CounterfactualRequest,
    CounterfactualType,
    EvidenceClaim,
    EvidenceSpan,
)

UNAVAILABLE_MARKER = "[Synthetic source evidence unavailable for counterfactual replay.]"


def _claim_and_spans(
    response: AnalyzeResponse, request: CounterfactualRequest
) -> tuple[EvidenceClaim | None, list[EvidenceSpan]]:
    contract = next(
        (item for item in response.evidence_contracts if item.candidate_id == request.candidate_id),
        None,
    )
    claim = (
        next((item for item in contract.claims if item.claim_id == request.claim_id), None)
        if contract and request.claim_id
        else None
    )
    spans = list(claim.source_spans) if claim else []
    if request.evidence_span_id:
        spans = [
            span
            for record in response.records
            for span in record.evidence_spans
            if span.span_id == request.evidence_span_id
        ]
    return claim, spans


def derive_counterfactual_request(
    source_request: AnalyzeRequest,
    source_response: AnalyzeResponse,
    counterfactual: CounterfactualRequest,
) -> tuple[AnalyzeRequest, list[str]]:
    derived = source_request.model_copy(deep=True)
    claim, spans = _claim_and_spans(source_response, counterfactual)
    altered_ids: list[str] = []
    source_id = counterfactual.source_record_id
    if counterfactual.counterfactual_type == CounterfactualType.remove_source_record:
        if source_id is None:
            raise ValueError("source_record_id is required")
        derived.records = [record for record in derived.records if record.record_id != source_id]
        if not derived.records:
            raise ValueError("A counterfactual cannot remove every source record.")
        return derived, [source_id]
    if counterfactual.counterfactual_type == CounterfactualType.mark_source_unavailable:
        if source_id is None:
            raise ValueError("source_record_id is required")
        record = next((item for item in derived.records if item.record_id == source_id), None)
        if record is None:
            raise ValueError("Source record not found")
        record.text = UNAVAILABLE_MARKER
        record.translated_text = None
        record.ingestion_hash = None
        record.reliability_metadata = {
            **record.reliability_metadata,
            "counterfactual_availability": "unavailable",
        }
        return derived, [source_id]
    if (
        counterfactual.counterfactual_type
        in {
            CounterfactualType.remove_compatibility_claim,
            CounterfactualType.remove_conflicting_claim,
            CounterfactualType.remove_rival_comparison_claim,
        }
        and claim is None
    ):
        raise ValueError("claim_id is required and must resolve to the selected contract")
    if not spans:
        raise ValueError("The selected counterfactual has no resolvable evidence spans")

    by_record: dict[str, list[EvidenceSpan]] = {}
    for span in spans:
        by_record.setdefault(span.record_id, []).append(span)
        altered_ids.append(span.span_id)
    for record_id, record_spans in by_record.items():
        record = next((item for item in derived.records if item.record_id == record_id), None)
        if record is None:
            raise ValueError(f"Source record {record_id} not found")
        for span in sorted(record_spans, key=lambda item: item.start, reverse=True):
            if record.text[span.start : span.end] != span.quote:
                raise ValueError("Counterfactual span no longer resolves to immutable source text")
            replacement = (
                f"approximately {span.quote}"
                if counterfactual.counterfactual_type
                == CounterfactualType.reduce_evidence_certainty
                else UNAVAILABLE_MARKER
            )
            record.text = record.text[: span.start] + replacement + record.text[span.end :]
        record.ingestion_hash = None
    return derived, sorted(set(altered_ids))


def first_responsible_node(source: AnalyzeResponse, counterfactual: AnalyzeResponse) -> str:
    observed = {
        item.node_id: item.structured_output for item in counterfactual.workflow_trace_details
    }
    for trace in source.workflow_trace_details:
        if observed.get(trace.node_id) != trace.structured_output:
            return trace.node_id
    return "release_gate"


def find_comparable_candidate(
    source: AnalyzeResponse, counterfactual: AnalyzeResponse, candidate_id: str
) -> tuple[CandidateConnection | None, CandidateConnection | None]:
    original = next((item for item in source.candidates if item.candidate_id == candidate_id), None)
    if original is None:
        return None, counterfactual.candidates[0] if counterfactual.candidates else None
    wanted = {original.record_a_id, original.record_b_id}
    comparable = next(
        (
            item
            for item in counterfactual.candidates
            if {item.record_a_id, item.record_b_id} == wanted
        ),
        None,
    )
    return original, comparable or (
        counterfactual.candidates[0] if counterfactual.candidates else None
    )
