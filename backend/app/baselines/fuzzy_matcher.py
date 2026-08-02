from __future__ import annotations

from time import perf_counter

from rapidfuzz.fuzz import ratio

from app.schemas.models import AnalyzeRequest, Classification, SystemOutput
from app.services.extraction import extract_record
from app.services.normalization import normalize_name


def run_fuzzy(request: AnalyzeRequest) -> SystemOutput:
    started = perf_counter()
    best_score = -1.0
    best_ids: list[str] = []
    cited = []
    for index, record_a in enumerate(request.records):
        fields_a, spans_a = extract_record(record_a)
        name_a = next(
            (str(field.value) for field in fields_a if field.key == "name" and field.value), ""
        )
        for record_b in request.records[index + 1 :]:
            fields_b, spans_b = extract_record(record_b)
            name_b = next(
                (str(field.value) for field in fields_b if field.key == "name" and field.value), ""
            )
            score = (
                ratio(normalize_name(name_a), normalize_name(name_b)) if name_a and name_b else 0.0
            )
            if score > best_score:
                best_score = score
                best_ids = [record_a.record_id, record_b.record_id]
                cited = [span for span in [*spans_a, *spans_b] if span.field == "Name"]
    classification = (
        Classification.possible_candidate
        if best_score >= 65
        else Classification.insufficient_evidence
    )
    return SystemOutput(
        system_id="fuzzy",
        system_name="Exact/fuzzy matching",
        evaluation_mode="Deterministic mock evaluation",
        classification=classification,
        candidate_record_ids=best_ids,
        cited_evidence=cited,
        output={
            "ranking_score": round(max(best_score, 0), 2),
            "ranking_signal_only": True,
            "injection_resisted": True,
        },
        duration_ms=round((perf_counter() - started) * 1000, 3),
        model_calls=0,
    )
