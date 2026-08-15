"""
Linkage-decision models for THREADLINE identity resolution.

These models extend the existing Classification enum with a safety-first
decision contract. The existing Classification (strong_candidate_for_review,
possible_candidate, insufficient_evidence, conflicting_evidence) remains
as the retrieval-level signal. LinkageDecision is the final identity-
resolution recommendation.

Humanitarian safety principle: no binary match=true/false output.
Every decision has structured evidence, blocking conflicts, and
deterministic rules. An LLM may summarize but never determine the final state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from app.schemas.models import StrictModel
from app.services.field_policy import ReliabilityCategory


class LinkageDecisionState(StrEnum):
    """Final linkage recommendation states."""
    link_recommended = "link_recommended"
    human_review_required = "human_review_required"
    insufficient_evidence = "insufficient_evidence"
    do_not_link = "do_not_link"
    blocked_by_conflict = "blocked_by_conflict"
    system_error = "system_error"


# ── Reason codes ──

class LinkageReasonCode(StrEnum):
    """Deterministic reason codes for linkage decisions."""
    # Positive signals
    unique_identifier_match = "unique_identifier_match"
    multi_field_agreement = "multi_field_agreement"
    strong_discriminator_agreement = "strong_discriminator_agreement"

    # Blocking conflicts
    date_of_birth_conflict = "date_of_birth_conflict"
    government_id_conflict = "government_id_conflict"
    distinguishing_mark_conflict = "distinguishing_mark_conflict"
    age_hard_conflict = "age_hard_conflict"

    # Insufficient evidence
    insufficient_distinctive_fields = "insufficient_distinctive_fields"
    common_name_only = "common_name_only"
    location_only = "location_only"
    single_weak_match = "single_weak_match"
    missing_critical_fields = "missing_critical_fields"
    transliteration_only_name = "transliteration_only_name"

    # Review required
    ambiguous_evidence = "ambiguous_evidence"
    mixed_signals = "mixed_signals"
    rival_ambiguity = "rival_ambiguity"
    missing_key_discriminator = "missing_key_discriminator"
    source_reliability_concern = "source_reliability_concern"

    # Non-match
    multiple_strong_conflicts = "multiple_strong_conflicts"
    no_supporting_evidence = "no_supporting_evidence"

    # System
    comparison_failure = "comparison_failure"
    validation_error = "validation_error"


# ── Supporting/comparing evidence models ──

class SupportingComparison(StrictModel):
    """A single field comparison that supports linkage."""
    field_name: str
    comparison_class: str  # ComparisonClass value
    reason_code: str
    left_value: str | None = None
    right_value: str | None = None
    score_contribution: float = 0.0
    reliability: ReliabilityCategory
    evidence_span_ids: list[str] = []


class BlockingConflict(StrictModel):
    """A single field conflict that blocks automatic linkage."""
    field_name: str
    comparison_class: str
    reason_code: str
    left_value: str | None = None
    right_value: str | None = None
    reliability: ReliabilityCategory
    evidence_span_ids: list[str] = []


class MissingCriticalEvidence(StrictModel):
    """A critical field missing from one or both records."""
    field_name: str
    missing_from: Literal["left", "right", "both"]
    reliability: ReliabilityCategory
    impact: str  # e.g., "reduces certainty", "prevents automatic linkage"


# ── Decision model ──

class LinkageDecision(StrictModel):
    """Final identity-resolution recommendation for a record pair.

    This is the canonical output of the linkage decision engine.
    It must not be determined solely by an LLM. Every state is
    the result of deterministic rules operating on structured
    FieldComparison results.
    """

    # ── identity ──
    decision_id: str
    record_id_a: str
    record_id_b: str

    # ── decision ──
    state: LinkageDecisionState
    reason_codes: list[LinkageReasonCode]

    # ── scoring ──
    total_score: float = 0.0
    decision_threshold_version: str = "1.0.0"

    # ── evidence breakdown ──
    strongest_supporting: list[SupportingComparison] = []
    strongest_conflicting: list[BlockingConflict] = []
    blocking_conflicts: list[BlockingConflict] = []
    missing_critical: list[MissingCriticalEvidence] = []

    # ── candidate generation ──
    candidate_generation_rules: list[str] = []

    # ── explanation ──
    human_readable_explanation: str = ""
    explanation_reason_codes: list[str] = []

    # ── LLM involvement ──
    llm_contributed: bool = False
    llm_contribution_description: str = ""

    # ── audit ──
    created_at: datetime = datetime.now(timezone.utc)
    decision_engine_version: str = "1.0.0"

    # ── safety ──
    safety_notice: str = (
        "THREADLINE proposes candidate record connections for authorized human review "
        "and does not autonomously determine identity."
    )
    false_merge_risk: Literal["none", "low", "medium", "high", "blocked"] = "none"


# ── Pairwise comparison summary (used by explainability) ──

class PairwiseComparisonSummary(StrictModel):
    """Summary of a pairwise comparison suitable for explanation generation."""
    record_id_a: str
    record_id_b: str
    display_name_a: str
    display_name_b: str
    total_comparisons: int
    exact_matches: int
    normalized_matches: int
    compatible: int
    partial_matches: int
    conflicts: int
    strong_conflicts: int
    missing_left: int
    missing_right: int
    missing_both: int
    blocking_conflicts_present: bool
    unique_identifier_match: bool
    decisions: list[LinkageDecision] = []
