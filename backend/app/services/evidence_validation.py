from app.schemas.models import EvidenceSpan, RecordInput, ValidationResult


def validate_span(record: RecordInput, span: EvidenceSpan) -> list[ValidationResult]:
    quote_present = span.quote in record.text
    offsets_in_range = 0 <= span.start <= span.end <= len(record.text)
    offsets_match = offsets_in_range and record.text[span.start : span.end] == span.quote
    record_matches = span.record_id == record.record_id
    return [
        ValidationResult(
            check="evidence_quote_occurs_in_original",
            passed=quote_present,
            detail="Quote found in original text." if quote_present else "Quote not found.",
        ),
        ValidationResult(
            check="character_offsets_match_quote",
            passed=offsets_match,
            detail="Offsets match exact quote." if offsets_match else "Offsets do not match quote.",
        ),
        ValidationResult(
            check="source_record_id_matches",
            passed=record_matches,
            detail="Source record matches." if record_matches else "Source record mismatch.",
        ),
    ]


def validate_all_spans(
    records: list[RecordInput], spans: list[EvidenceSpan]
) -> list[ValidationResult]:
    record_map = {record.record_id: record for record in records}
    results: list[ValidationResult] = []
    for span in spans:
        record = record_map.get(span.record_id)
        if record is None:
            results.append(
                ValidationResult(
                    check="source_record_exists",
                    passed=False,
                    detail=f"Unknown source record {span.record_id}.",
                )
            )
            continue
        results.extend(validate_span(record, span))
    return results
