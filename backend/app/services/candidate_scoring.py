from __future__ import annotations

import re
from itertools import combinations

from rapidfuzz.fuzz import ratio

from app.schemas.models import (
    CandidateConnection,
    Certainty,
    Classification,
    CompatibilityFactor,
    Conflict,
    NormalizedRecord,
    ScoreComponent,
)
from app.services.normalization import normalize_name
from app.services.timeline_rules import timeline_compatibility

DISPLAY_CLASSIFICATION = {
    Classification.strong_candidate_for_review: "Strong candidate for review",
    Classification.possible_candidate: "Possible candidate",
    Classification.insufficient_evidence: "Insufficient evidence",
    Classification.conflicting_evidence: "Conflicting evidence",
}


def _field(record: NormalizedRecord, key: str) -> tuple[str | None, Certainty]:
    for field in record.fields:
        if field.key == key and field.value is not None:
            return str(field.value), field.certainty
    return None, Certainty.missing


def _span_ids(record: NormalizedRecord, key: str) -> list[str]:
    return [
        field.source_span_id
        for field in record.fields
        if field.key == key and field.source_span_id is not None
    ]


def _age_number(value: str | None) -> int | None:
    if value is None:
        return None
    match = re.search(r"\b(\d{1,2})\b", value)
    return int(match.group(1)) if match else None


def score_pair(
    record_a: NormalizedRecord,
    record_b: NormalizedRecord,
    rank: int,
    *,
    use_timeline: bool = True,
) -> CandidateConnection:
    name_a, name_certainty_a = _field(record_a, "name")
    name_b, name_certainty_b = _field(record_b, "name")
    forms_a = record_a.normalized_names
    forms_b = record_b.normalized_names
    if forms_a and forms_b:
        name_score = max(
            (
                ratio(normalize_name(form_a), normalize_name(form_b)) / 100
                for form_a in forms_a
                for form_b in forms_b
            ),
            default=0.0,
        )
    elif name_a is not None and name_b is not None:
        name_score = ratio(name_a.lower(), name_b.lower()) / 100
    else:
        name_score = 0.0
    age_a_value, age_certainty_a = _field(record_a, "age")
    age_b_value, age_certainty_b = _field(record_b, "age")
    age_a, age_b = _age_number(age_a_value), _age_number(age_b_value)
    age_score = 0.25
    age_status = "missing"
    hard_age_conflict = False
    if age_a is not None and age_b is not None:
        difference = abs(age_a - age_b)
        hard_age_conflict = (
            difference >= 5
            and age_certainty_a == Certainty.exact
            and age_certainty_b == Certainty.exact
        )
        age_score = (
            1.0 if difference == 0 else 0.8 if difference <= 1 else 0.3 if difference <= 3 else 0.0
        )
        age_status = (
            "hard_conflict"
            if hard_age_conflict
            else "compatible"
            if difference == 0
            else "soft_conflict"
        )

    languages_a, lang_certainty_a = _field(record_a, "languages")
    languages_b, lang_certainty_b = _field(record_b, "languages")
    language_overlap = bool(
        languages_a
        and languages_b
        and set(re.findall(r"[a-z]+", languages_a.lower()))
        & set(re.findall(r"[a-z]+", languages_b.lower()))
    )
    language_score = (
        1.0 if language_overlap else 0.25 if languages_a is None or languages_b is None else 0.0
    )

    clothing_a, cloth_certainty_a = _field(record_a, "clothing")
    clothing_b, cloth_certainty_b = _field(record_b, "clothing")
    colors = {"blue", "navy", "black", "white", "green", "grey", "gray"}
    cloth_words_a = set(re.findall(r"[a-z]+", (clothing_a or "").lower()))
    cloth_words_b = set(re.findall(r"[a-z]+", (clothing_b or "").lower()))
    blue_equivalent = bool(cloth_words_a & {"blue", "navy"}) and bool(
        cloth_words_b & {"blue", "navy"}
    )
    clothing_overlap = bool((cloth_words_a & cloth_words_b & colors) or blue_equivalent)
    clothing_score = 1.0 if clothing_overlap else 0.25 if not clothing_a or not clothing_b else 0.0

    timeline_result = timeline_compatibility(record_a, record_b)
    timeline_score = (1.0 if timeline_result.passed else 0.0) if use_timeline else 0.5
    components = [
        ScoreComponent(
            field="name", value=name_score, explanation="RapidFuzz normalized-name ratio."
        ),
        ScoreComponent(
            field="age", value=age_score, explanation="Deterministic age compatibility."
        ),
        ScoreComponent(
            field="language", value=language_score, explanation="Narrative language overlap."
        ),
        ScoreComponent(
            field="clothing", value=clothing_score, explanation="Color and garment overlap."
        ),
        ScoreComponent(field="timeline", value=timeline_score, explanation=timeline_result.detail),
    ]
    retrieval_score = round(
        0.42 * name_score
        + 0.20 * age_score
        + 0.14 * language_score
        + 0.10 * clothing_score
        + 0.14 * timeline_score,
        4,
    )

    factors: list[CompatibilityFactor] = []
    if name_a is not None or name_b is not None:
        factors.append(
            CompatibilityFactor(
                factor_id=f"CF-{rank}-NAME",
                field="Name",
                record_a_value=name_a or "Not reported",
                record_b_value=name_b or "Not reported",
                status="compatible"
                if name_score >= 0.72
                else "uncertain"
                if name_score >= 0.45
                else "soft_conflict",
                interpretation=(
                    "Comparable name forms were retrieved; this is a ranking signal, not identity proof."
                ),
                certainty_a=name_certainty_a,
                certainty_b=name_certainty_b,
                evidence_span_ids=_span_ids(record_a, "name") + _span_ids(record_b, "name"),
            )
        )
    factors.append(
        CompatibilityFactor(
            factor_id=f"CF-{rank}-AGE",
            field="Age",
            record_a_value=age_a_value or "Not reported",
            record_b_value=age_b_value or "Not reported",
            status=age_status,
            interpretation=(
                "Exact ages are incompatible."
                if hard_age_conflict
                else "Age evidence is compatible or remains uncertain based on certainty labels."
            ),
            certainty_a=age_certainty_a,
            certainty_b=age_certainty_b,
            evidence_span_ids=_span_ids(record_a, "age") + _span_ids(record_b, "age"),
        )
    )
    if languages_a or languages_b:
        factors.append(
            CompatibilityFactor(
                factor_id=f"CF-{rank}-LANG",
                field="Language",
                record_a_value=languages_a or "Not reported",
                record_b_value=languages_b or "Not reported",
                status="compatible" if language_overlap else "uncertain",
                interpretation="Reported languages overlap."
                if language_overlap
                else "Language evidence is incomplete.",
                certainty_a=lang_certainty_a,
                certainty_b=lang_certainty_b,
                evidence_span_ids=_span_ids(record_a, "languages")
                + _span_ids(record_b, "languages"),
            )
        )
    if clothing_a or clothing_b:
        factors.append(
            CompatibilityFactor(
                factor_id=f"CF-{rank}-CLOTH",
                field="Clothing",
                record_a_value=clothing_a or "Not reported",
                record_b_value=clothing_b or "Not reported",
                status="compatible" if clothing_overlap else "uncertain",
                interpretation="Outerwear descriptions overlap."
                if clothing_overlap
                else "Clothing is missing or non-distinctive.",
                certainty_a=cloth_certainty_a,
                certainty_b=cloth_certainty_b,
                evidence_span_ids=_span_ids(record_a, "clothing") + _span_ids(record_b, "clothing"),
            )
        )

    conflicts: list[Conflict] = []
    if hard_age_conflict:
        conflicts.append(
            Conflict(
                conflict_id=f"CONFLICT-{rank}-AGE",
                field="Age",
                severity="hard",
                explanation=f"Two exact ages differ: {age_a} and {age_b}.",
                evidence_span_ids=_span_ids(record_a, "age") + _span_ids(record_b, "age"),
            )
        )
    missing_discriminators = sum(
        value is None
        for value in (name_a, name_b, age_a_value, age_b_value, clothing_a, clothing_b)
    )
    if hard_age_conflict or not timeline_result.passed:
        classification = Classification.conflicting_evidence
    elif retrieval_score >= 0.88 and missing_discriminators <= 2:
        classification = Classification.strong_candidate_for_review
    elif retrieval_score >= 0.46 and missing_discriminators <= 4:
        classification = Classification.possible_candidate
    else:
        classification = Classification.insufficient_evidence

    display = DISPLAY_CLASSIFICATION[classification]
    return CandidateConnection(
        candidate_id=f"MATCH-{rank:03d}",
        record_a_id=record_a.record_id,
        record_b_id=record_b.record_id,
        label=f"{display} connection"
        if classification != Classification.conflicting_evidence
        else display,
        classification=display,
        classification_code=classification,
        supporting_summary="Compatible fields are separately cited and remain subject to human verification.",
        opposing_summary=(
            "A hard conflict prevents a positive candidate recommendation."
            if hard_age_conflict
            else "Missing and non-distinctive fields limit the connection."
        ),
        verification_question="Can an authorized reviewer obtain one independent distinctive detail?",
        verification_explanation="A distinctive, independently sourced detail can help resolve remaining ambiguity.",
        additional_questions=["Can location or time be independently verified?"],
        abstention_reasons=(
            ["Evidence is not sufficiently distinctive."]
            if classification == Classification.insufficient_evidence
            else []
        ),
        compatibility_factors=factors,
        conflicts=conflicts,
        retrieval_score=retrieval_score,
        score_components=components,
        rank=rank,
    )


def retrieve_candidates(
    records: list[NormalizedRecord], limit: int, *, use_timeline: bool = True
) -> list[CandidateConnection]:
    provisional = [
        score_pair(a, b, 1, use_timeline=use_timeline)
        for a, b in combinations(records, 2)
        if a.record_id != b.record_id
    ]
    provisional.sort(key=lambda candidate: candidate.retrieval_score, reverse=True)
    selected = provisional[:limit]
    for rank, candidate in enumerate(selected, 1):
        candidate.rank = rank
        candidate.candidate_id = f"MATCH-{rank:03d}"
    return selected
