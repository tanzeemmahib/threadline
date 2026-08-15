"""
Deterministic pairwise comparison engine.

Takes two NormalizedRecords and returns structured comparison results
for every field covered by the field-policy registry.

Humanitarian safety principle: every comparison result is typed, explained,
and traceable to source evidence spans. No raw string comparison without
classification.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum

from app.schemas.models import (
    Certainty,
    NormalizedRecord,
)
from app.services.field_policy import (
    FIELD_POLICIES,
    ComparisonType,
    FieldPolicy,
    ReliabilityCategory,
)
from app.services.normalization import normalize_name

# Compatibility factors are explicit so partial evidence strength is
# centralized, reviewable, and testable. They do not alter the 0.35 threshold.
DOB_YEAR_ONLY_COMPATIBILITY_FACTOR = 0.3
NAME_TRANSLITERATION_COMPATIBILITY_FACTOR = 0.6
NAME_REORDER_COMPATIBILITY_FACTOR = 0.5

# ─────────────────────────────────────────────────────────────
# Comparison result types
# ─────────────────────────────────────────────────────────────


class ComparisonClass(StrEnum):
    """Typed result of comparing a single field across two records."""
    exact_match = "exact_match"
    normalized_match = "normalized_match"
    compatible = "compatible"
    partial_match = "partial_match"
    conflict = "conflict"
    strong_conflict = "strong_conflict"
    missing_left = "missing_left"
    missing_right = "missing_right"
    missing_both = "missing_both"
    insufficient_evidence = "insufficient_evidence"
    not_comparable = "not_comparable"


@dataclass(slots=True)
class FieldComparison:
    """Result of comparing one field across two records."""

    field_name: str                     # canonical field name from policy
    extraction_key: str                 # the ExtractedField.key that produced this comparison

    # ── values ──
    left_value: str | None = None
    right_value: str | None = None
    left_normalized: str | None = None
    right_normalized: str | None = None

    # ── classification ──
    classification: ComparisonClass = ComparisonClass.not_comparable
    reason_code: str = ""               # deterministic machine-readable code

    # ── reliability ──
    reliability: ReliabilityCategory = ReliabilityCategory.not_comparable
    left_certainty: Certainty = Certainty.missing
    right_certainty: Certainty = Certainty.missing

    # ── scoring ──
    score_contribution: float = 0.0     # how much this field contributes to linkage score
    blocks_linkage: bool = False        # true if this field alone blocks automatic linkage

    # ── evidence ──
    left_evidence_span_ids: list[str] = field(default_factory=list)
    right_evidence_span_ids: list[str] = field(default_factory=list)

    # ── metadata ──
    comparison_detail: str = ""         # human-readable explanation


# ─────────────────────────────────────────────────────────────
# Normalization helpers
# ─────────────────────────────────────────────────────────────

def _normalize_for_comparison(value: str, policy: FieldPolicy) -> str:
    """Apply normalization steps defined by the field policy."""
    result = value
    if policy.normalize_whitespace:
        result = " ".join(result.split())
    if policy.normalize_case:
        result = result.lower()
    if policy.normalize_unicode:
        result = unicodedata.normalize("NFKD", result)
        result = "".join(c for c in result if not unicodedata.combining(c))
    return result.strip()


def _normalize_phone(value: str) -> str:
    """Extract digits only from a phone number string.

    Uses the shared phone_parser module for consistent normalization
    across Unicode digit systems, directional controls, and formatting.
    """
    from app.services.phone_parser import parse_phone
    parsed = parse_phone(value)
    return parsed.normalized_digits


def _normalize_email(value: str) -> str | None:
    """Return a normalized complete email address, or ``None``."""
    from app.services.email_normalizer import normalize_valid_email

    return normalize_valid_email(value)


def _extract_tokens(value: str) -> set[str]:
    """Extract lowercase word tokens from a value."""
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _extract_age(value: str | None) -> int | None:
    """Extract numeric age from an age string."""
    if value is None:
        return None
    match = re.search(r"\b(\d{1,3})\b", str(value))
    return int(match.group(1)) if match else None


def _extract_date_parts(value: str) -> tuple[int | None, int | None, int | None]:
    """Extract year, month, day from a date string. Returns (None, None, None) on failure."""
    # ISO format: YYYY-MM-DD or YYYY-MM or YYYY
    iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", value.strip())
    if iso:
        return int(iso.group(1)), int(iso.group(2)), int(iso.group(3))
    ym = re.match(r"^(\d{4})-(\d{2})$", value.strip())
    if ym:
        return int(ym.group(1)), int(ym.group(2)), None
    y = re.match(r"^(\d{4})$", value.strip())
    if y:
        return int(y.group(1)), None, None
    return None, None, None


# ─────────────────────────────────────────────────────────────
# Field-level comparison functions
# ─────────────────────────────────────────────────────────────

def _compare_exact_string(
    left: str | None, right: str | None, policy: FieldPolicy
) -> FieldComparison:
    """Exact string comparison after normalization."""
    if left is None and right is None:
        return FieldComparison(
            field_name=policy.canonical_name,
            extraction_key=policy.extraction_keys[0],
            classification=ComparisonClass.missing_both,
            reason_code="both_missing",
            reliability=policy.reliability,
        )
    if left is None:
        return FieldComparison(
            field_name=policy.canonical_name,
            extraction_key=policy.extraction_keys[0],
            right_value=right,
            classification=ComparisonClass.missing_left,
            reason_code="left_missing",
            reliability=policy.reliability,
        )
    if right is None:
        return FieldComparison(
            field_name=policy.canonical_name,
            extraction_key=policy.extraction_keys[0],
            left_value=left,
            classification=ComparisonClass.missing_right,
            reason_code="right_missing",
            reliability=policy.reliability,
        )
    left_norm = _normalize_for_comparison(left, policy)
    right_norm = _normalize_for_comparison(right, policy)
    is_match = left_norm == right_norm
    score = policy.score_weight if is_match else 0.0
    blocks = policy.disagreement_blocks_linkage and not is_match
    return FieldComparison(
        field_name=policy.canonical_name,
        extraction_key=policy.extraction_keys[0],
        left_value=left,
        right_value=right,
        left_normalized=left_norm,
        right_normalized=right_norm,
        classification=ComparisonClass.exact_match if is_match else ComparisonClass.conflict,
        reason_code="exact_string_match" if is_match else "string_mismatch",
        reliability=policy.reliability,
        score_contribution=score,
        blocks_linkage=blocks,
        comparison_detail=(
            f"Exact match: '{left_norm}'" if is_match
            else f"Mismatch: '{left_norm}' vs '{right_norm}'"
        ),
    )


def _compare_normalized_name(
    left: str | None, right: str | None, policy: FieldPolicy
) -> FieldComparison:
    """Name comparison using multi-channel, transliteration-aware matching.

    Evaluates: original-script match, Latin transliteration, consonant skeleton,
    token-set overlap, token-order, and initials. Returns full provenance in
    reason_code and comparison_detail.

    Safety: transliteration-based matches are explicitly marked and receive
    reduced score weight. Cross-script names without independent supporting
    evidence should not independently authorize linkage.
    """
    if left is None and right is None:
        return FieldComparison(
            field_name=policy.canonical_name,
            extraction_key=policy.extraction_keys[0],
            classification=ComparisonClass.missing_both,
            reason_code="both_missing",
            reliability=policy.reliability,
        )
    if left is None:
        return FieldComparison(
            field_name=policy.canonical_name,
            extraction_key=policy.extraction_keys[0],
            right_value=right,
            classification=ComparisonClass.missing_left,
            reason_code="left_missing",
            reliability=policy.reliability,
        )
    if right is None:
        return FieldComparison(
            field_name=policy.canonical_name,
            extraction_key=policy.extraction_keys[0],
            left_value=left,
            classification=ComparisonClass.missing_right,
            reason_code="right_missing",
            reliability=policy.reliability,
        )

    from app.services.normalization import compare_name_strings

    threshold = policy.fuzzy_threshold or 72.0
    result = compare_name_strings(left, right, fuzzy_threshold=threshold)

    # Map the multi-channel result to ComparisonClass and score
    channel = result.channel
    code = result.reason_code

    # ── Policy-flag enforcement ──
    # When allow_transliteration is False, downgrade transliteration-based matches
    if (
        not getattr(policy, "allow_transliteration", True)
        and channel in ("formal_transliteration_match", "consonant_skeleton_compatible")
    ):
        channel = "ambiguous"
        code = "name_transliteration_disabled_by_policy"
        result.is_formal_transliteration = False
        result.is_consonant_skeleton = False
    # When allow_reordered_names is False, downgrade token-reorder matches
    if (
        not getattr(policy, "allow_reordered_names", True)
        and channel == "token_reordered_compatible"
        and result.is_token_reordered
    ):
        channel = "token_set_compatible"
        code = "name_reorder_disabled_by_policy"
        result.is_token_reordered = False

    if channel in ("exact_original", "normalized_original"):
        cls = ComparisonClass.normalized_match
        score = policy.score_weight
    elif channel == "formal_transliteration_match":
        cls = ComparisonClass.normalized_match if not result.is_cross_script else ComparisonClass.compatible
        score = policy.score_weight * (0.85 if result.is_cross_script else 1.0)
    elif channel == "consonant_skeleton_compatible":
        cls = ComparisonClass.compatible
        score = policy.score_weight * NAME_TRANSLITERATION_COMPATIBILITY_FACTOR
    elif channel == "known_variant_match":
        cls = ComparisonClass.compatible
        score = policy.score_weight * 0.75
    elif channel == "token_reordered_compatible":
        cls = ComparisonClass.compatible
        score = policy.score_weight * NAME_REORDER_COMPATIBILITY_FACTOR
    elif channel == "token_set_compatible":
        cls = ComparisonClass.compatible
        score = policy.score_weight * 0.5
    elif channel == "initials_match":
        cls = ComparisonClass.partial_match
        score = policy.score_weight * 0.25
    elif channel == "ambiguous" or result.fuzzy_score >= threshold:
        cls = ComparisonClass.compatible
        score = policy.score_weight * 0.5
    elif result.fuzzy_score >= 45:
        cls = ComparisonClass.partial_match
        score = policy.score_weight * 0.3
    else:
        cls = ComparisonClass.conflict
        score = 0.0

    # Short-name safety: single-token source names cannot get high confidence
    if (
        cls in (ComparisonClass.normalized_match, ComparisonClass.compatible)
        and (result.left_representation and result.left_representation.is_short_name)
    ):
        cls = ComparisonClass.compatible
        score = min(score, policy.score_weight * 0.4)
        code = "name_short_name_match"

    return FieldComparison(
        field_name=policy.canonical_name,
        extraction_key=policy.extraction_keys[0],
        left_value=left,
        right_value=right,
        left_normalized=(
            result.left_representation.normalized_latin_transliteration
            if result.left_representation else normalize_name(left or "")
        ),
        right_normalized=(
            result.right_representation.normalized_latin_transliteration
            if result.right_representation else normalize_name(right or "")
        ),
        classification=cls,
        reason_code=code,
        reliability=policy.reliability,
        score_contribution=round(score, 4),
        blocks_linkage=False,
        comparison_detail=result.detail,
    )


def _compare_fuzzy_name(
    left: str | None, right: str | None, policy: FieldPolicy
) -> FieldComparison:
    """Fuzzy name comparison — delegates to normalized name logic."""
    return _compare_normalized_name(left, right, policy)


def _compare_numeric_approximate(
    left: str | None, right: str | None, policy: FieldPolicy
) -> FieldComparison:
    """Numeric comparison with tolerance window."""
    age_left = _extract_age(left)
    age_right = _extract_age(right)

    if age_left is None and age_right is None:
        return FieldComparison(
            field_name=policy.canonical_name,
            extraction_key=policy.extraction_keys[0],
            left_value=left,
            right_value=right,
            classification=ComparisonClass.missing_both,
            reason_code="both_unparseable",
            reliability=policy.reliability,
        )
    if age_left is None:
        return FieldComparison(
            field_name=policy.canonical_name,
            extraction_key=policy.extraction_keys[0],
            right_value=right,
            classification=ComparisonClass.missing_left,
            reason_code="left_unparseable",
            reliability=policy.reliability,
        )
    if age_right is None:
        return FieldComparison(
            field_name=policy.canonical_name,
            extraction_key=policy.extraction_keys[0],
            left_value=left,
            classification=ComparisonClass.missing_right,
            reason_code="right_unparseable",
            reliability=policy.reliability,
        )

    diff = abs(age_left - age_right)
    if diff == 0:
        cls = ComparisonClass.exact_match
        code = "age_exact"
        score = policy.score_weight
        blocks = False
    elif diff <= 1:
        cls = ComparisonClass.normalized_match
        code = "age_compatible_1yr"
        score = policy.score_weight * 0.8
        blocks = False
    elif diff <= 3:
        cls = ComparisonClass.compatible
        code = "age_compatible_3yr"
        score = policy.score_weight * 0.4
        blocks = False
    elif diff >= 5:
        # Check certainty — only block if both certainties are exact
        cls = ComparisonClass.strong_conflict
        code = "age_hard_conflict"
        score = 0.0
        blocks = True  # will be conditionally honored based on certainty
    else:
        cls = ComparisonClass.conflict
        code = "age_soft_conflict"
        score = 0.0
        blocks = False

    return FieldComparison(
        field_name=policy.canonical_name,
        extraction_key=policy.extraction_keys[0],
        left_value=str(age_left),
        right_value=str(age_right),
        left_normalized=str(age_left),
        right_normalized=str(age_right),
        classification=cls,
        reason_code=code,
        reliability=policy.reliability,
        score_contribution=round(score, 4),
        blocks_linkage=blocks,
        comparison_detail=f"Ages {age_left} vs {age_right} (diff={diff})",
    )


def _compare_date_iso(
    left: str | None, right: str | None, policy: FieldPolicy
) -> FieldComparison:
    """ISO date comparison with precision awareness."""
    if left is None and right is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            classification=ComparisonClass.missing_both, reason_code="both_missing",
            reliability=policy.reliability,
        )
    if left is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            right_value=right, classification=ComparisonClass.missing_left,
            reason_code="left_missing", reliability=policy.reliability,
        )
    if right is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, classification=ComparisonClass.missing_right,
            reason_code="right_missing", reliability=policy.reliability,
        )

    ly, lm, ld = _extract_date_parts(left)
    ry, rm, rd = _extract_date_parts(right)

    if ly is None or ry is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, right_value=right,
            classification=ComparisonClass.insufficient_evidence,
            reason_code="date_unparseable", reliability=policy.reliability,
        )

    # Year must match for any agreement
    if ly != ry:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, right_value=right,
            left_normalized=f"{ly:04d}-{lm:02d}" if lm else f"{ly:04d}",
            right_normalized=f"{ry:04d}-{rm:02d}" if rm else f"{ry:04d}",
            classification=ComparisonClass.strong_conflict,
            reason_code="dob_year_mismatch",
            reliability=policy.reliability,
            score_contribution=0.0,
            blocks_linkage=True,
            comparison_detail=f"Date of birth year mismatch: {ly} vs {ry}",
        )

    # Same year — check precision
    if lm is not None and rm is not None:
        if lm == rm:
            if ld is not None and rd is not None:
                if ld == rd:
                    return FieldComparison(
                        field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
                        left_value=left, right_value=right,
                        left_normalized=f"{ly:04d}-{lm:02d}-{ld:02d}",
                        right_normalized=f"{ry:04d}-{rm:02d}-{rd:02d}",
                        classification=ComparisonClass.exact_match,
                        reason_code="dob_exact_full",
                        reliability=policy.reliability,
                        score_contribution=policy.score_weight,
                        comparison_detail=f"Exact DOB match: {ly:04d}-{lm:02d}-{ld:02d}",
                    )
                # same year+month, different day → conflict
                return FieldComparison(
                    field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
                    left_value=left, right_value=right,
                    classification=ComparisonClass.strong_conflict,
                    reason_code="dob_day_mismatch",
                    reliability=policy.reliability,
                    score_contribution=0.0,
                    blocks_linkage=True,
                    comparison_detail=f"DOB day mismatch: {ly:04d}-{lm:02d}-{ld:02d} vs {ly:04d}-{lm:02d}-{rd:02d}",
                )
            # same year+month, one or both missing day → compatible
            return FieldComparison(
                field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
                left_value=left, right_value=right,
                classification=ComparisonClass.compatible,
                reason_code="dob_year_month_match",
                reliability=policy.reliability,
                score_contribution=policy.score_weight * 0.8,
                comparison_detail=f"DOB year+month match: {ly:04d}-{lm:02d}",
            )
        # same year, different month → conflict
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, right_value=right,
            classification=ComparisonClass.strong_conflict,
            reason_code="dob_month_mismatch",
            reliability=policy.reliability,
            score_contribution=0.0,
            blocks_linkage=True,
            comparison_detail=f"DOB month mismatch: {ly:04d}-{lm:02d} vs {ly:04d}-{rm:02d}",
        )

    # Same year only (no month detail) — compatible but weak
    return FieldComparison(
        field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
        left_value=left, right_value=right,
        left_normalized=f"{ly:04d}", right_normalized=f"{ry:04d}",
        classification=ComparisonClass.compatible,
        reason_code="dob_year_only_match",
        reliability=policy.reliability,
        score_contribution=policy.score_weight * DOB_YEAR_ONLY_COMPATIBILITY_FACTOR,
        comparison_detail=f"DOB year match only: {ly:04d}",
    )


def _compare_phone_normalized(
    left: str | None, right: str | None, policy: FieldPolicy
) -> FieldComparison:
    """Phone comparison using shared phone_parser with full international support.

    Supports: Unicode digit normalization, +/00 prefix equivalence,
    compatible local/international matching, extension separation,
    safe suffix overlap, and conflict detection.
    """
    from app.services.phone_parser import (
        ParsedPhone,
        PhoneComparisonOutcome,
        parse_phone_with_ocr,
    )

    # Missing-value handling
    if left is None and right is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            classification=ComparisonClass.missing_both, reason_code="both_missing",
            reliability=policy.reliability,
        )
    if left is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            right_value=right, classification=ComparisonClass.missing_left,
            reason_code="left_missing", reliability=policy.reliability,
        )
    if right is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, classification=ComparisonClass.missing_right,
            reason_code="right_missing", reliability=policy.reliability,
        )

    # Parse both phones through shared parser (conservative OCR stage applied
    # so OCR-assisted matches are distinguished from clean exact matches)
    left_parsed: ParsedPhone = parse_phone_with_ocr(left)
    right_parsed: ParsedPhone = parse_phone_with_ocr(right)

    if not left_parsed.is_valid or not right_parsed.is_valid:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, right_value=right,
            classification=ComparisonClass.insufficient_evidence,
            reason_code="phone_no_digits", reliability=policy.reliability,
        )

    # Compare parsed phones
    from app.services.phone_parser import compare_parsed_phones
    outcome, reason = compare_parsed_phones(left_parsed, right_parsed)

    left_digits = left_parsed.normalized_digits
    right_digits = right_parsed.normalized_digits

    # Map parser outcomes to comparison classification
    if outcome == PhoneComparisonOutcome.exact_match:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, right_value=right,
            left_normalized=left_digits, right_normalized=right_digits,
            classification=ComparisonClass.exact_match,
            reason_code=reason,
            reliability=policy.reliability,
            score_contribution=policy.score_weight,
            comparison_detail=f"Phone digits match: ...{left_digits[-4:]}",
        )

    elif outcome == PhoneComparisonOutcome.intl_prefix_equivalent:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, right_value=right,
            left_normalized=left_digits, right_normalized=right_digits,
            classification=ComparisonClass.exact_match,  # Proven equivalent
            reason_code=reason,
            reliability=policy.reliability,
            score_contribution=policy.score_weight,
            comparison_detail="International prefix equivalent (+X == 00X)",
        )

    elif outcome == PhoneComparisonOutcome.compatible_local_intl:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, right_value=right,
            left_normalized=left_digits, right_normalized=right_digits,
            classification=ComparisonClass.compatible,
            reason_code=reason,
            reliability=policy.reliability,
            score_contribution=policy.score_weight * 0.6,
            comparison_detail="Compatible local/international phone formats",
        )

    elif outcome == PhoneComparisonOutcome.ocr_assisted_compatible:
        # OCR-assisted matches are conservative: never full-strength, never
        # equivalent to a clean exact match, and never a strong identifier.
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, right_value=right,
            left_normalized=left_digits, right_normalized=right_digits,
            classification=ComparisonClass.compatible,
            reason_code=reason,
            reliability=policy.reliability,
            score_contribution=policy.score_weight * 0.6,
            comparison_detail="OCR-assisted phone match (conservative, not exact)",
        )

    elif outcome == PhoneComparisonOutcome.weak_suffix_overlap:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, right_value=right,
            left_normalized=left_digits, right_normalized=right_digits,
            classification=ComparisonClass.partial_match,
            reason_code="phone_suffix_match",
            reliability=policy.reliability,
            score_contribution=policy.score_weight * 0.4,
            comparison_detail="Phone suffix matches (last 7 digits)",
        )

    elif outcome == PhoneComparisonOutcome.conflict:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, right_value=right,
            left_normalized=left_digits, right_normalized=right_digits,
            classification=ComparisonClass.conflict,
            reason_code=reason,
            reliability=policy.reliability,
            comparison_detail="Phone numbers differ",
        )

    # insufficient
    return FieldComparison(
        field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
        left_value=left, right_value=right,
        left_normalized=left_digits, right_normalized=right_digits,
        classification=ComparisonClass.insufficient_evidence,
        reason_code="phone_insufficient_for_comparison",
        reliability=policy.reliability,
    )


def _compare_email_normalized(
    left: str | None, right: str | None, policy: FieldPolicy
) -> FieldComparison:
    """Email comparison: lowercased, trimmed."""
    if left is None and right is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            classification=ComparisonClass.missing_both, reason_code="both_missing",
            reliability=policy.reliability,
        )
    if left is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            right_value=right, classification=ComparisonClass.missing_left,
            reason_code="left_missing", reliability=policy.reliability,
        )
    if right is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, classification=ComparisonClass.missing_right,
            reason_code="right_missing", reliability=policy.reliability,
        )

    left_norm = _normalize_email(left)
    right_norm = _normalize_email(right)

    if left_norm is None or right_norm is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, right_value=right,
            left_normalized=left_norm, right_normalized=right_norm,
            classification=ComparisonClass.insufficient_evidence,
            reason_code="email_invalid_or_incomplete",
            reliability=policy.reliability,
            comparison_detail="At least one email value is malformed or incomplete",
        )

    if left_norm == right_norm:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, right_value=right,
            left_normalized=left_norm, right_normalized=right_norm,
            classification=ComparisonClass.exact_match,
            reason_code="email_exact_match",
            reliability=policy.reliability,
            score_contribution=policy.score_weight,
            comparison_detail="Email addresses match",
        )
    return FieldComparison(
        field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
        left_value=left, right_value=right,
        left_normalized=left_norm, right_normalized=right_norm,
        classification=ComparisonClass.conflict,
        reason_code="email_mismatch",
        reliability=policy.reliability,
        comparison_detail="Email addresses differ",
    )


def _compare_set_overlap(
    left: str | None, right: str | None, policy: FieldPolicy
) -> FieldComparison:
    """Set-overlap comparison (languages, clothing, descriptors)."""
    if left is None and right is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            classification=ComparisonClass.missing_both, reason_code="both_missing",
            reliability=policy.reliability,
        )
    if left is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            right_value=right, classification=ComparisonClass.missing_left,
            reason_code="left_missing", reliability=policy.reliability,
        )
    if right is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, classification=ComparisonClass.missing_right,
            reason_code="right_missing", reliability=policy.reliability,
        )

    left_tokens = _extract_tokens(left)
    right_tokens = _extract_tokens(right)
    overlap = left_tokens & right_tokens

    if not overlap:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, right_value=right,
            classification=ComparisonClass.conflict,
            reason_code="no_overlap",
            reliability=policy.reliability,
            comparison_detail="No overlapping tokens",
        )

    jaccard = len(overlap) / len(left_tokens | right_tokens) if (left_tokens | right_tokens) else 0
    if jaccard >= 0.6:
        cls = ComparisonClass.compatible
        code = "strong_overlap"
        score = policy.score_weight
    else:
        cls = ComparisonClass.partial_match
        code = "partial_overlap"
        score = policy.score_weight * 0.4

    return FieldComparison(
        field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
        left_value=left, right_value=right,
        left_normalized=", ".join(sorted(left_tokens)),
        right_normalized=", ".join(sorted(right_tokens)),
        classification=cls,
        reason_code=code,
        reliability=policy.reliability,
        score_contribution=round(score, 4),
        comparison_detail=f"Token overlap: {len(overlap)} shared of {len(left_tokens | right_tokens)} unique",
    )


def _compare_geo_proximity(
    left: str | None, right: str | None, policy: FieldPolicy
) -> FieldComparison:
    """Geo-proximity comparison — named-location overlap with configurable window.

    Since THREADLINE does not currently use lat/lng, this treats locations as
    named entities with exact-match proximity within a configured set of known locations.
    """
    if left is None and right is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            classification=ComparisonClass.missing_both, reason_code="both_missing",
            reliability=policy.reliability,
        )
    if left is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            right_value=right, classification=ComparisonClass.missing_left,
            reason_code="left_missing", reliability=policy.reliability,
        )
    if right is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, classification=ComparisonClass.missing_right,
            reason_code="right_missing", reliability=policy.reliability,
        )

    left_norm = _normalize_for_comparison(left, policy)
    right_norm = _normalize_for_comparison(right, policy)

    # Exact location name match
    if left_norm == right_norm:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, right_value=right,
            left_normalized=left_norm, right_normalized=right_norm,
            classification=ComparisonClass.exact_match,
            reason_code="location_exact",
            reliability=policy.reliability,
            score_contribution=policy.score_weight,
            comparison_detail=f"Same location: '{left_norm}'",
        )

    # Token overlap for approximate location match
    left_tokens = _extract_tokens(left_norm)
    right_tokens = _extract_tokens(right_norm)
    overlap = left_tokens & right_tokens
    if overlap:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, right_value=right,
            left_normalized=left_norm, right_normalized=right_norm,
            classification=ComparisonClass.partial_match,
            reason_code="location_partial_overlap",
            reliability=policy.reliability,
            score_contribution=policy.score_weight * 0.3,
            comparison_detail=f"Partial location overlap: {overlap}",
        )

    return FieldComparison(
        field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
        left_value=left, right_value=right,
        left_normalized=left_norm, right_normalized=right_norm,
        classification=ComparisonClass.conflict,
        reason_code="location_different",
        reliability=policy.reliability,
        comparison_detail=f"Different locations: '{left_norm}' vs '{right_norm}'",
    )


def _compare_enum_exact(
    left: str | None, right: str | None, policy: FieldPolicy
) -> FieldComparison:
    """Exact enum match after normalization."""
    return _compare_exact_string(left, right, policy)


def _compare_time_window(
    left: str | None, right: str | None, policy: FieldPolicy
) -> FieldComparison:
    """Time-window comparison using the timeline_rules approach."""
    if left is None and right is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            classification=ComparisonClass.missing_both, reason_code="both_missing",
            reliability=policy.reliability,
        )
    if left is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            right_value=right, classification=ComparisonClass.missing_left,
            reason_code="left_missing", reliability=policy.reliability,
        )
    if right is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, classification=ComparisonClass.missing_right,
            reason_code="right_missing", reliability=policy.reliability,
        )

    # Reuse timeline_rules minute extraction
    from app.services.timeline_rules import minutes_from_text

    a_mins = minutes_from_text(left)
    b_mins = minutes_from_text(right)

    if a_mins is None or b_mins is None:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, right_value=right,
            classification=ComparisonClass.insufficient_evidence,
            reason_code="time_unparseable",
            reliability=policy.reliability,
        )

    diff = abs(a_mins - b_mins)
    plausible = b_mins >= a_mins or diff <= 30

    if plausible:
        return FieldComparison(
            field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
            left_value=left, right_value=right,
            classification=ComparisonClass.compatible,
            reason_code="timeline_plausible",
            reliability=policy.reliability,
            score_contribution=policy.score_weight,
            comparison_detail="Chronological order is plausible",
        )
    return FieldComparison(
        field_name=policy.canonical_name, extraction_key=policy.extraction_keys[0],
        left_value=left, right_value=right,
        classification=ComparisonClass.conflict,
        reason_code="timeline_implausible",
        reliability=policy.reliability,
        comparison_detail="Negative travel interval detected",
    )


def _compare_identifier_exact(
    left: str | None, right: str | None, policy: FieldPolicy
) -> FieldComparison:
    """Exact identifier comparison (government/aid ID)."""
    return _compare_exact_string(left, right, policy)


# ─────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────

_COMPARATORS = {
    ComparisonType.exact_string: _compare_exact_string,
    ComparisonType.normalized_name: _compare_normalized_name,
    ComparisonType.fuzzy_name: _compare_fuzzy_name,
    ComparisonType.numeric_exact: _compare_exact_string,
    ComparisonType.numeric_approximate: _compare_numeric_approximate,
    ComparisonType.date_iso: _compare_date_iso,
    ComparisonType.phone_normalized: _compare_phone_normalized,
    ComparisonType.email_normalized: _compare_email_normalized,
    ComparisonType.set_overlap: _compare_set_overlap,
    ComparisonType.geo_proximity: _compare_geo_proximity,
    ComparisonType.time_window: _compare_time_window,
    ComparisonType.enum_exact: _compare_enum_exact,
    ComparisonType.identifier_exact: _compare_identifier_exact,
}


# ─────────────────────────────────────────────────────────────
# Main pairwise comparison function
# ─────────────────────────────────────────────────────────────


def _get_field_value(record: NormalizedRecord, extraction_keys: tuple[str, ...]) -> str | None:
    """Find the first matching field value in a record for any of the given keys."""
    for extracted_field in record.fields:
        if extracted_field.key in extraction_keys and extracted_field.value is not None:
            return str(extracted_field.value)
    return None


def _get_field_certainty(record: NormalizedRecord, extraction_keys: tuple[str, ...]) -> Certainty:
    """Get the certainty for the first matching field."""
    for extracted_field in record.fields:
        if extracted_field.key in extraction_keys:
            return extracted_field.certainty
    return Certainty.missing


def _get_evidence_span_ids(record: NormalizedRecord, extraction_keys: tuple[str, ...]) -> list[str]:
    """Get evidence span IDs for matching fields."""
    ids: list[str] = []
    for extracted_field in record.fields:
        if extracted_field.key in extraction_keys and extracted_field.source_span_id:
            ids.append(extracted_field.source_span_id)
    return ids


def compare_records(
    record_a: NormalizedRecord,
    record_b: NormalizedRecord,
    *,
    policies: dict[str, FieldPolicy] | None = None,
) -> list[FieldComparison]:
    """Compare two records across all registered field policies.

    Returns one FieldComparison per policy. Fields not present in either
    record are marked as missing_both. Missing on only one side is marked
    as missing_left/missing_right.

    This is the canonical deterministic comparison function. It must not
    call any LLM and must produce identical output for identical input.
    """
    if policies is None:
        policies = FIELD_POLICIES

    results: list[FieldComparison] = []

    for canonical_name, policy in policies.items():
        if policy.reliability == ReliabilityCategory.not_comparable:
            continue

        left_val = _get_field_value(record_a, policy.extraction_keys)
        right_val = _get_field_value(record_b, policy.extraction_keys)

        comparator = _COMPARATORS.get(policy.comparison_type)
        if comparator is None:
            results.append(FieldComparison(
                field_name=canonical_name,
                extraction_key=policy.extraction_keys[0],
                classification=ComparisonClass.not_comparable,
                reason_code="no_comparator",
                reliability=policy.reliability,
            ))
            continue

        result = comparator(left_val, right_val, policy)

        # Enrich with certainty and evidence
        result.left_certainty = _get_field_certainty(record_a, policy.extraction_keys)
        result.right_certainty = _get_field_certainty(record_b, policy.extraction_keys)
        result.left_evidence_span_ids = _get_evidence_span_ids(record_a, policy.extraction_keys)
        result.right_evidence_span_ids = _get_evidence_span_ids(record_b, policy.extraction_keys)

        # Override age strong_conflict if certainty is not exact on both sides
        if (
            policy.canonical_name == "age"
            and result.classification == ComparisonClass.strong_conflict
            and not (
                result.left_certainty == Certainty.exact
                and result.right_certainty == Certainty.exact
            )
        ):
            result.classification = ComparisonClass.conflict
            result.blocks_linkage = False
            result.reason_code = "age_soft_conflict_certainty"
            result.comparison_detail += " (certainty not exact — downgraded to soft conflict)"

        results.append(result)

    return results


def total_linkage_score(comparisons: list[FieldComparison]) -> float:
    """Sum score contributions across all non-missing, non-conflict comparisons."""
    return round(sum(c.score_contribution for c in comparisons), 4)


def blocking_conflicts(comparisons: list[FieldComparison]) -> list[FieldComparison]:
    """Return all comparisons that block automatic linkage."""
    return [c for c in comparisons if c.blocks_linkage]


def strong_evidence_comparisons(comparisons: list[FieldComparison]) -> list[FieldComparison]:
    """Return comparisons that provide strong evidence (exact match or normalized match)."""
    return [
        c for c in comparisons
        if c.classification in {ComparisonClass.exact_match, ComparisonClass.normalized_match}
    ]


def conflicting_comparisons(comparisons: list[FieldComparison]) -> list[FieldComparison]:
    """Return all conflicting comparisons."""
    return [
        c for c in comparisons
        if c.classification in {ComparisonClass.conflict, ComparisonClass.strong_conflict}
    ]
