"""
Field-policy registry — single source of truth for field comparison behaviour.

Each field defines its comparison type, reliability category, normalization strategy,
and how agreement or disagreement affects linkage decisions.

Humanitarian safety principle: false merges are the highest-risk failure.
Policies reflect this — common attributes are weak signals; unique identifiers are strong;
conflicts on high-reliability fields block automatic linkage.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ComparisonType(StrEnum):
    """How two values for this field should be compared."""
    exact_string = "exact_string"           # case/punctuation/whitespace-insensitive exact match
    normalized_name = "normalized_name"     # Unicode NFKD, transliteration-aware, word reordering
    fuzzy_name = "fuzzy_name"              # RapidFuzz ratio with explicit threshold
    numeric_exact = "numeric_exact"         # Exact integer match
    numeric_approximate = "numeric_approximate"  # Within configured tolerance window
    date_iso = "date_iso"                  # ISO date comparison with precision awareness
    phone_normalized = "phone_normalized"   # Digits-only after stripping formatting
    email_normalized = "email_normalized"   # Lowercased, trimmed
    set_overlap = "set_overlap"            # Intersection of token sets
    geo_proximity = "geo_proximity"         # Named-location proximity (within configured window)
    time_window = "time_window"            # Time-range overlap or ordered chronology
    enum_exact = "enum_exact"              # Exact match on enumerated values
    identifier_exact = "identifier_exact"   # Government/aid ID — exact match only


class ReliabilityCategory(StrEnum):
    """How reliable this field is as identity evidence."""
    unique_identifier = "unique_identifier"       # Near-certain identity proof (gov ID, biometric)
    strong_discriminator = "strong_discriminator" # Highly distinguishing (phone, email, full name+DOB)
    moderate_discriminator = "moderate_discriminator"  # Somewhat distinguishing (name alone, address)
    weak_discriminator = "weak_discriminator"     # Weakly distinguishing (age, language, clothing)
    contextual_only = "contextual_only"           # Not identity evidence (shelter location, last-seen time)
    not_comparable = "not_comparable"             # Should not participate in identity comparison


@dataclass(frozen=True, slots=True)
class FieldPolicy:
    """Canonical comparison policy for a single field."""

    # ── identity ──
    canonical_name: str
    extraction_keys: tuple[str, ...]  # keys used in ExtractedField.key

    # ── comparison ──
    comparison_type: ComparisonType
    reliability: ReliabilityCategory

    # ── agreement behaviour ──
    exact_agreement_is_strong_evidence: bool = False
    normalized_agreement_is_strong_evidence: bool = False
    partial_agreement_is_weak_evidence: bool = False

    # ── disagreement behaviour ──
    disagreement_blocks_linkage: bool = False
    disagreement_is_strong_conflict: bool = False

    # ── missing-value behaviour ──
    missing_reduces_certainty: bool = True
    missing_is_not_a_contradiction: bool = True

    # ── special considerations ──
    commonly_shared: bool = False          # true if field is commonly shared across unrelated people
    may_change_over_time: bool = False     # true if the value can change (e.g., clothing, location)
    source_reliability_affects_weight: bool = False
    fuzzy_threshold: float | None = None   # threshold for fuzzy_name comparison (0-100 RapidFuzz)

    # ── scoring ──
    score_weight: float = 0.0              # contribution to overall linkage score (0-1)

    # ── normalization ──
    normalize_unicode: bool = True
    normalize_case: bool = True
    normalize_whitespace: bool = True
    allow_transliteration: bool = False
    allow_reordered_names: bool = False

    # ── multi-value handling ──
    allow_multiple_values: bool = False    # field may have multiple valid values (e.g., aliases)


# ─────────────────────────────────────────────────────────────
# Canonical field-policy registry
# ─────────────────────────────────────────────────────────────

FIELD_POLICIES: dict[str, FieldPolicy] = {
    # ── Identity-critical fields ──
    "full_name": FieldPolicy(
        canonical_name="full_name",
        extraction_keys=("name",),
        comparison_type=ComparisonType.normalized_name,
        reliability=ReliabilityCategory.moderate_discriminator,
        normalized_agreement_is_strong_evidence=False,
        partial_agreement_is_weak_evidence=True,
        disagreement_blocks_linkage=False,
        disagreement_is_strong_conflict=False,
        commonly_shared=True,
        may_change_over_time=False,
        source_reliability_affects_weight=False,
        fuzzy_threshold=72.0,
        score_weight=0.12,
        allow_transliteration=True,
        allow_reordered_names=True,
        allow_multiple_values=True,
    ),
    "date_of_birth": FieldPolicy(
        canonical_name="date_of_birth",
        extraction_keys=("date_of_birth", "dob"),
        comparison_type=ComparisonType.date_iso,
        reliability=ReliabilityCategory.strong_discriminator,
        exact_agreement_is_strong_evidence=True,
        normalized_agreement_is_strong_evidence=True,
        disagreement_blocks_linkage=True,
        disagreement_is_strong_conflict=True,
        commonly_shared=False,
        may_change_over_time=False,
        score_weight=0.18,
    ),
    "age": FieldPolicy(
        canonical_name="age",
        extraction_keys=("age",),
        comparison_type=ComparisonType.numeric_approximate,
        reliability=ReliabilityCategory.weak_discriminator,
        exact_agreement_is_strong_evidence=False,
        partial_agreement_is_weak_evidence=True,
        disagreement_blocks_linkage=False,
        disagreement_is_strong_conflict=True,  # exact ages >=5 apart with exact certainty
        commonly_shared=True,
        may_change_over_time=True,
        fuzzy_threshold=None,
        score_weight=0.08,
    ),
    "government_id": FieldPolicy(
        canonical_name="government_id",
        extraction_keys=("government_id", "national_id", "aid_id", "registration_number"),
        comparison_type=ComparisonType.identifier_exact,
        reliability=ReliabilityCategory.unique_identifier,
        exact_agreement_is_strong_evidence=True,
        normalized_agreement_is_strong_evidence=True,
        disagreement_blocks_linkage=True,
        disagreement_is_strong_conflict=True,
        commonly_shared=False,
        may_change_over_time=False,
        score_weight=0.25,
        normalize_unicode=True,
        normalize_case=True,
        normalize_whitespace=True,
    ),
    "phone": FieldPolicy(
        canonical_name="phone",
        extraction_keys=("phone", "phone_number", "contact_phone"),
        comparison_type=ComparisonType.phone_normalized,
        reliability=ReliabilityCategory.strong_discriminator,
        exact_agreement_is_strong_evidence=True,
        normalized_agreement_is_strong_evidence=True,
        disagreement_blocks_linkage=False,
        disagreement_is_strong_conflict=False,
        commonly_shared=False,
        may_change_over_time=True,
        score_weight=0.15,
    ),
    "email": FieldPolicy(
        canonical_name="email",
        extraction_keys=("email", "email_address", "contact_email"),
        comparison_type=ComparisonType.email_normalized,
        reliability=ReliabilityCategory.strong_discriminator,
        exact_agreement_is_strong_evidence=True,
        normalized_agreement_is_strong_evidence=True,
        disagreement_blocks_linkage=False,
        disagreement_is_strong_conflict=False,
        commonly_shared=False,
        may_change_over_time=True,
        score_weight=0.10,
    ),

    # ── Demographic/descriptive fields ──
    "sex_gender": FieldPolicy(
        canonical_name="sex_gender",
        extraction_keys=("sex", "gender", "sex_gender"),
        comparison_type=ComparisonType.enum_exact,
        reliability=ReliabilityCategory.weak_discriminator,
        exact_agreement_is_strong_evidence=False,
        partial_agreement_is_weak_evidence=True,
        disagreement_blocks_linkage=False,
        disagreement_is_strong_conflict=False,
        commonly_shared=True,
        may_change_over_time=False,
        score_weight=0.02,
    ),
    "language": FieldPolicy(
        canonical_name="language",
        extraction_keys=("languages", "language"),
        comparison_type=ComparisonType.set_overlap,
        reliability=ReliabilityCategory.weak_discriminator,
        exact_agreement_is_strong_evidence=False,
        partial_agreement_is_weak_evidence=True,
        disagreement_blocks_linkage=False,
        disagreement_is_strong_conflict=False,
        commonly_shared=True,
        may_change_over_time=False,
        score_weight=0.03,
    ),
    "nationality": FieldPolicy(
        canonical_name="nationality",
        extraction_keys=("nationality",),
        comparison_type=ComparisonType.enum_exact,
        reliability=ReliabilityCategory.weak_discriminator,
        exact_agreement_is_strong_evidence=False,
        partial_agreement_is_weak_evidence=True,
        disagreement_blocks_linkage=False,
        disagreement_is_strong_conflict=False,
        commonly_shared=True,
        may_change_over_time=False,
        score_weight=0.02,
    ),
    "physical_descriptors": FieldPolicy(
        canonical_name="physical_descriptors",
        extraction_keys=("physical_descriptors", "height", "build", "hair_color", "eye_color"),
        comparison_type=ComparisonType.set_overlap,
        reliability=ReliabilityCategory.weak_discriminator,
        exact_agreement_is_strong_evidence=False,
        partial_agreement_is_weak_evidence=True,
        disagreement_blocks_linkage=False,
        disagreement_is_strong_conflict=False,
        commonly_shared=True,
        may_change_over_time=False,
        score_weight=0.03,
    ),
    "distinguishing_marks": FieldPolicy(
        canonical_name="distinguishing_marks",
        extraction_keys=("distinguishing_marks", "distinctive_features", "scars", "tattoos"),
        comparison_type=ComparisonType.set_overlap,
        reliability=ReliabilityCategory.strong_discriminator,
        exact_agreement_is_strong_evidence=True,
        partial_agreement_is_weak_evidence=True,
        disagreement_blocks_linkage=False,
        disagreement_is_strong_conflict=True,
        commonly_shared=False,
        may_change_over_time=False,
        score_weight=0.10,
    ),
    "clothing": FieldPolicy(
        canonical_name="clothing",
        extraction_keys=("clothing", "clothing_description"),
        comparison_type=ComparisonType.set_overlap,
        reliability=ReliabilityCategory.weak_discriminator,
        exact_agreement_is_strong_evidence=False,
        partial_agreement_is_weak_evidence=True,
        disagreement_blocks_linkage=False,
        disagreement_is_strong_conflict=False,
        commonly_shared=True,
        may_change_over_time=True,
        score_weight=0.02,
    ),

    # ── Relational fields ──
    "family_member_names": FieldPolicy(
        canonical_name="family_member_names",
        extraction_keys=("family_member_names", "parent_name", "mother_name", "father_name",
                         "sibling_names", "relative_names"),
        comparison_type=ComparisonType.normalized_name,
        reliability=ReliabilityCategory.moderate_discriminator,
        normalized_agreement_is_strong_evidence=False,
        partial_agreement_is_weak_evidence=True,
        disagreement_blocks_linkage=False,
        disagreement_is_strong_conflict=False,
        commonly_shared=False,
        may_change_over_time=False,
        fuzzy_threshold=72.0,
        score_weight=0.08,
        allow_transliteration=True,
        allow_reordered_names=True,
        allow_multiple_values=True,
    ),

    # ── Location fields ──
    "home_address": FieldPolicy(
        canonical_name="home_address",
        extraction_keys=("home_address", "address", "residence"),
        comparison_type=ComparisonType.geo_proximity,
        reliability=ReliabilityCategory.moderate_discriminator,
        exact_agreement_is_strong_evidence=False,
        partial_agreement_is_weak_evidence=True,
        disagreement_blocks_linkage=False,
        disagreement_is_strong_conflict=False,
        commonly_shared=False,
        may_change_over_time=True,
        score_weight=0.05,
    ),
    "last_known_location": FieldPolicy(
        canonical_name="last_known_location",
        extraction_keys=("last_known_location", "last_seen_location", "location"),
        comparison_type=ComparisonType.geo_proximity,
        reliability=ReliabilityCategory.contextual_only,
        exact_agreement_is_strong_evidence=False,
        partial_agreement_is_weak_evidence=True,
        disagreement_blocks_linkage=False,
        disagreement_is_strong_conflict=False,
        commonly_shared=True,
        may_change_over_time=True,
        score_weight=0.03,
    ),
    "shelter_location": FieldPolicy(
        canonical_name="shelter_location",
        extraction_keys=("shelter_location", "shelter", "hospital_location", "camp_location"),
        comparison_type=ComparisonType.geo_proximity,
        reliability=ReliabilityCategory.contextual_only,
        exact_agreement_is_strong_evidence=False,
        partial_agreement_is_weak_evidence=True,
        disagreement_blocks_linkage=False,
        disagreement_is_strong_conflict=False,
        commonly_shared=True,
        may_change_over_time=True,
        score_weight=0.02,
    ),

    # ── Temporal fields ──
    "last_seen_time": FieldPolicy(
        canonical_name="last_seen_time",
        extraction_keys=("last_seen_time", "timestamp", "datetime_last_seen", "time"),
        comparison_type=ComparisonType.time_window,
        reliability=ReliabilityCategory.contextual_only,
        exact_agreement_is_strong_evidence=False,
        partial_agreement_is_weak_evidence=True,
        disagreement_blocks_linkage=False,
        disagreement_is_strong_conflict=False,
        commonly_shared=True,
        may_change_over_time=True,
        score_weight=0.03,
    ),
}


def get_policy(field_key: str) -> FieldPolicy | None:
    """Look up the FieldPolicy for an ExtractedField key."""
    for policy in FIELD_POLICIES.values():
        if field_key in policy.extraction_keys:
            return policy
    return None


def get_all_comparable_policies() -> list[FieldPolicy]:
    """All policies that can participate in identity comparison."""
    return [
        policy
        for policy in FIELD_POLICIES.values()
        if policy.reliability != ReliabilityCategory.not_comparable
        and policy.score_weight > 0
    ]


def policy_for_canonical_name(canonical_name: str) -> FieldPolicy | None:
    """Look up a policy by its canonical name."""
    return FIELD_POLICIES.get(canonical_name)
