"""
Deterministic linkage decision engine.

Takes structured FieldComparison results and produces a LinkageDecision.
All rules are deterministic. No LLM is called. The decision is based on
field policies, comparison classifications, and safety rules.

Humanitarian safety principle: false merges are the highest-risk failure.
The engine errs on the side of human review whenever evidence is ambiguous,
missing, or mixed. An LLM may summarize structured results but may NOT
determine the final state.
"""

from __future__ import annotations

from uuid import uuid4

from app.schemas.linkage import (
    BlockingConflict,
    LinkageDecision,
    LinkageDecisionState,
    LinkageReasonCode,
    MissingCriticalEvidence,
    SupportingComparison,
)
from app.services.field_policy import ReliabilityCategory
from app.services.pairwise_compare import (
    ComparisonClass,
    FieldComparison,
)

# ─────────────────────────────────────────────────────────────
# Thresholds (versioned for reproducibility)
# ─────────────────────────────────────────────────────────────

# Minimum total score to consider link_recommended
LINK_RECOMMENDED_MIN_SCORE = 0.35

# Minimum total score for human_review_required (below this = insufficient_evidence)
HUMAN_REVIEW_MIN_SCORE = 0.15

# Minimum number of independent evidence categories required for link_recommended
# (counted as unique ReliabilityCategory values among supporting comparisons)
MIN_INDEPENDENT_CATEGORIES = 2


# ─────────────────────────────────────────────────────────────
# Decision engine
# ─────────────────────────────────────────────────────────────

def _unique_categories(comparisons: list[FieldComparison]) -> set[ReliabilityCategory]:
    """Extract unique reliability categories from a list of comparisons."""
    return {c.reliability for c in comparisons}


def _is_strong_support(comp: FieldComparison) -> bool:
    """A comparison counts as strong support if it's an exact or normalized match."""
    return comp.classification in {ComparisonClass.exact_match, ComparisonClass.normalized_match}


def _is_blocking(comp: FieldComparison) -> bool:
    """A comparison blocks linkage if the policy says so and it's a conflict."""
    return comp.blocks_linkage or (
        comp.classification == ComparisonClass.strong_conflict
        and comp.reliability in {
            ReliabilityCategory.unique_identifier,
            ReliabilityCategory.strong_discriminator,
        }
    )


def _is_strong_conflict(comp: FieldComparison) -> bool:
    """A comparison is a strong conflict."""
    return comp.classification == ComparisonClass.strong_conflict


def _is_missing(comp: FieldComparison) -> bool:
    """A comparison is missing on at least one side."""
    return comp.classification in {
        ComparisonClass.missing_left,
        ComparisonClass.missing_right,
        ComparisonClass.missing_both,
    }


def determine_linkage(
    comparisons: list[FieldComparison],
    record_id_a: str,
    record_id_b: str,
    display_name_a: str = "",
    display_name_b: str = "",
    *,
    candidate_generation_rules: list[str] | None = None,
) -> LinkageDecision:
    """Produce a deterministic linkage recommendation from structured comparisons.

    Rules (in order of precedence):

    1. system_error: if comparisons are empty or fundamentally broken.
    2. blocked_by_conflict: any unique_identifier or strong_discriminator
       field has a strong_conflict.
    3. do_not_link: multiple strong conflicts with no compensating evidence.
    4. link_recommended: unique_identifier exact match AND no blocking conflicts,
       OR strong multi-field agreement across >=2 independent categories with
       sufficient total score and no blocking conflicts.
    5. insufficient_evidence: total score below threshold OR only common/
       contextual fields match.
    6. human_review_required: everything else (the default, safe state).

    An LLM confidence value cannot override these rules.
    """
    decision_id = f"LINK-{uuid4().hex[:12].upper()}"
    reason_codes: list[LinkageReasonCode] = []
    blocking: list[BlockingConflict] = []
    strongest_supporting: list[SupportingComparison] = []
    strongest_conflicting: list[BlockingConflict] = []
    missing_critical: list[MissingCriticalEvidence] = []

    if not comparisons:
        return LinkageDecision(
            decision_id=decision_id,
            record_id_a=record_id_a,
            record_id_b=record_id_b,
            state=LinkageDecisionState.system_error,
            reason_codes=[LinkageReasonCode.comparison_failure],
            human_readable_explanation="No field comparisons were produced.",
            candidate_generation_rules=candidate_generation_rules or [],
            false_merge_risk="none",
        )

    # Calculate total score
    total_score = sum(c.score_contribution for c in comparisons if c.score_contribution > 0)

    # Categorize comparisons
    supporting = [c for c in comparisons if _is_strong_support(c)]
    strong_conflicts_list = [c for c in comparisons if _is_strong_conflict(c)]
    all_conflicts = [c for c in comparisons if c.classification in {
        ComparisonClass.conflict, ComparisonClass.strong_conflict,
    }]
    missing = [c for c in comparisons if _is_missing(c)]
    comparable = [c for c in comparisons if not _is_missing(c) and c.classification != ComparisonClass.not_comparable]

    # Build blocking conflicts list
    for comp in comparisons:
        if _is_blocking(comp):
            blocking.append(BlockingConflict(
                field_name=comp.field_name,
                comparison_class=comp.classification.value,
                reason_code=comp.reason_code,
                left_value=comp.left_value,
                right_value=comp.right_value,
                reliability=comp.reliability,
                evidence_span_ids=comp.left_evidence_span_ids + comp.right_evidence_span_ids,
            ))

    # Build supporting list
    for comp in supporting:
        strongest_supporting.append(SupportingComparison(
            field_name=comp.field_name,
            comparison_class=comp.classification.value,
            reason_code=comp.reason_code,
            left_value=comp.left_value,
            right_value=comp.right_value,
            score_contribution=comp.score_contribution,
            reliability=comp.reliability,
            evidence_span_ids=comp.left_evidence_span_ids + comp.right_evidence_span_ids,
        ))

    # ── Transliteration safety check ──
    # Cross-script name similarity must not independently authorize a merge.
    # A transliteration-compatible name can strengthen a pair, but at least
    # one independent non-name supporting field must exist.
    transliteration_name_support = [
        c for c in supporting
        if c.field_name == "full_name"
        and c.reason_code in {
            "name_formal_transliteration_match",
            "name_consonant_skeleton_compatible",
            "name_token_reordered_compatible",
            "name_known_variant_match",
        }
    ]
    non_name_support = [c for c in supporting if c.field_name != "full_name"]
    has_name_only_transliteration = (
        transliteration_name_support
        and not non_name_support
        and len(supporting) == len(transliteration_name_support)
    )
    if has_name_only_transliteration:
        reason_codes.append(LinkageReasonCode.transliteration_only_name)

    # Build conflicting list
    for comp in strong_conflicts_list:
        strongest_conflicting.append(BlockingConflict(
            field_name=comp.field_name,
            comparison_class=comp.classification.value,
            reason_code=comp.reason_code,
            left_value=comp.left_value,
            right_value=comp.right_value,
            reliability=comp.reliability,
            evidence_span_ids=comp.left_evidence_span_ids + comp.right_evidence_span_ids,
        ))

    # Build missing critical evidence
    for comp in missing:
        if comp.reliability in {
            ReliabilityCategory.unique_identifier,
            ReliabilityCategory.strong_discriminator,
            ReliabilityCategory.moderate_discriminator,
        }:
            missing_from: Literal["left", "right", "both"] = (
                "both" if comp.classification == ComparisonClass.missing_both
                else "left" if comp.classification == ComparisonClass.missing_left
                else "right"
            )
            missing_critical.append(MissingCriticalEvidence(
                field_name=comp.field_name,
                missing_from=missing_from,
                reliability=comp.reliability,
                impact=(
                    "prevents automatic linkage"
                    if comp.reliability == ReliabilityCategory.unique_identifier
                    else "reduces certainty"
                ),
            ))

    # ── Rule 1: Blocked by conflict ──
    has_unique_id = supporting and any(
        c.reliability == ReliabilityCategory.unique_identifier for c in supporting
    )
    if blocking:
        # Unique identifier conflict → blocked_by_conflict always
        if any(c.reliability == ReliabilityCategory.unique_identifier for c in comparisons if _is_blocking(c)):
            reason_codes.append(LinkageReasonCode.government_id_conflict)
        # DOB conflict → blocked_by_conflict
        if any(c.field_name == "date_of_birth" for c in blocking):
            reason_codes.append(LinkageReasonCode.date_of_birth_conflict)
        # Distinguishing marks conflict → blocked_by_conflict
        if any(c.field_name == "distinguishing_marks" for c in blocking):
            reason_codes.append(LinkageReasonCode.distinguishing_mark_conflict)
        # Age hard conflict → blocked_by_conflict
        if any(c.field_name == "age" for c in blocking):
            reason_codes.append(LinkageReasonCode.age_hard_conflict)

        if not reason_codes:
            reason_codes = [LinkageReasonCode.multiple_strong_conflicts]

        return LinkageDecision(
            decision_id=decision_id,
            record_id_a=record_id_a,
            record_id_b=record_id_b,
            state=LinkageDecisionState.blocked_by_conflict,
            reason_codes=reason_codes,
            total_score=round(total_score, 4),
            strongest_supporting=strongest_supporting,
            strongest_conflicting=strongest_conflicting,
            blocking_conflicts=blocking,
            missing_critical=missing_critical,
            candidate_generation_rules=candidate_generation_rules or [],
            human_readable_explanation=_format_explanation(
                LinkageDecisionState.blocked_by_conflict,
                reason_codes,
                len(supporting),
                len(blocking),
                total_score,
            ),
            explanation_reason_codes=[rc.value for rc in reason_codes],
            false_merge_risk="blocked",
        )

    # ── Rule 2: Unique identifier match → link_recommended ──
    if has_unique_id:
        reason_codes.append(LinkageReasonCode.unique_identifier_match)
        return LinkageDecision(
            decision_id=decision_id,
            record_id_a=record_id_a,
            record_id_b=record_id_b,
            state=LinkageDecisionState.link_recommended,
            reason_codes=reason_codes,
            total_score=round(total_score, 4),
            strongest_supporting=strongest_supporting,
            strongest_conflicting=strongest_conflicting,
            blocking_conflicts=blocking,
            missing_critical=missing_critical,
            candidate_generation_rules=candidate_generation_rules or [],
            human_readable_explanation=_format_explanation(
                LinkageDecisionState.link_recommended,
                reason_codes,
                len(supporting),
                len(blocking),
                total_score,
            ),
            explanation_reason_codes=[rc.value for rc in reason_codes],
            false_merge_risk="low",
        )

    # ── Rule 3: do_not_link (multiple strong conflicts, no supporting evidence) ──
    if len(strong_conflicts_list) >= 2 and not supporting:
        reason_codes.append(LinkageReasonCode.multiple_strong_conflicts)
        return LinkageDecision(
            decision_id=decision_id,
            record_id_a=record_id_a,
            record_id_b=record_id_b,
            state=LinkageDecisionState.do_not_link,
            reason_codes=reason_codes,
            total_score=round(total_score, 4),
            strongest_supporting=strongest_supporting,
            strongest_conflicting=strongest_conflicting,
            blocking_conflicts=blocking,
            missing_critical=missing_critical,
            candidate_generation_rules=candidate_generation_rules or [],
            human_readable_explanation=_format_explanation(
                LinkageDecisionState.do_not_link,
                reason_codes,
                len(supporting),
                len(blocking),
                total_score,
            ),
            explanation_reason_codes=[rc.value for rc in reason_codes],
            false_merge_risk="none",
        )

    # ── Rule 4: insufficient_evidence ──
    categories = _unique_categories([c for c in comparisons if c.score_contribution > 0 and c.classification != ComparisonClass.conflict])

    # Only common/contextual fields match → insufficient
    if categories and categories <= {
        ReliabilityCategory.weak_discriminator,
        ReliabilityCategory.contextual_only,
    }:
        reason_codes.append(LinkageReasonCode.insufficient_distinctive_fields)

    # Common name only
    name_support = [c for c in supporting if c.field_name == "full_name"]
    if name_support and len(categories) == 1 and ReliabilityCategory.moderate_discriminator in categories:
        # Only name matches, no other category
        reason_codes.append(LinkageReasonCode.common_name_only)

    # Location only
    location_comps = [c for c in supporting if "location" in c.field_name]
    if location_comps and len(categories) == 1 and ReliabilityCategory.contextual_only in categories:
        reason_codes.append(LinkageReasonCode.location_only)

    # Score too low
    if total_score < HUMAN_REVIEW_MIN_SCORE:
        if not reason_codes:
            reason_codes.append(LinkageReasonCode.no_supporting_evidence)

    if reason_codes:
        return LinkageDecision(
            decision_id=decision_id,
            record_id_a=record_id_a,
            record_id_b=record_id_b,
            state=LinkageDecisionState.insufficient_evidence,
            reason_codes=reason_codes,
            total_score=round(total_score, 4),
            strongest_supporting=strongest_supporting,
            strongest_conflicting=strongest_conflicting,
            blocking_conflicts=blocking,
            missing_critical=missing_critical,
            candidate_generation_rules=candidate_generation_rules or [],
            human_readable_explanation=_format_explanation(
                LinkageDecisionState.insufficient_evidence,
                reason_codes,
                len(supporting),
                len(blocking),
                total_score,
            ),
            explanation_reason_codes=[rc.value for rc in reason_codes],
            false_merge_risk="none",
        )

    # ── Rule 5: link_recommended ──
    if (
        total_score >= LINK_RECOMMENDED_MIN_SCORE
        and len(categories) >= MIN_INDEPENDENT_CATEGORIES
        and not blocking
    ):
        reason_codes.append(LinkageReasonCode.multi_field_agreement)
        return LinkageDecision(
            decision_id=decision_id,
            record_id_a=record_id_a,
            record_id_b=record_id_b,
            state=LinkageDecisionState.link_recommended,
            reason_codes=reason_codes,
            total_score=round(total_score, 4),
            strongest_supporting=strongest_supporting,
            strongest_conflicting=strongest_conflicting,
            blocking_conflicts=blocking,
            missing_critical=missing_critical,
            candidate_generation_rules=candidate_generation_rules or [],
            human_readable_explanation=_format_explanation(
                LinkageDecisionState.link_recommended,
                reason_codes,
                len(supporting),
                len(blocking),
                total_score,
            ),
            explanation_reason_codes=[rc.value for rc in reason_codes],
            false_merge_risk="low",
        )

    # ── Rule 6: human_review_required (default safe state) ──
    if missing_critical:
        reason_codes.append(LinkageReasonCode.missing_key_discriminator)
    if strong_conflicts_list and supporting:
        reason_codes.append(LinkageReasonCode.mixed_signals)
    if not reason_codes:
        reason_codes.append(LinkageReasonCode.ambiguous_evidence)

    return LinkageDecision(
        decision_id=decision_id,
        record_id_a=record_id_a,
        record_id_b=record_id_b,
        state=LinkageDecisionState.human_review_required,
        reason_codes=reason_codes,
        total_score=round(total_score, 4),
        strongest_supporting=strongest_supporting,
        strongest_conflicting=strongest_conflicting,
        blocking_conflicts=blocking,
        missing_critical=missing_critical,
        candidate_generation_rules=candidate_generation_rules or [],
        human_readable_explanation=_format_explanation(
            LinkageDecisionState.human_review_required,
            reason_codes,
            len(supporting),
            len(blocking),
            total_score,
        ),
        explanation_reason_codes=[rc.value for rc in reason_codes],
        false_merge_risk="medium",
    )


# ─────────────────────────────────────────────────────────────
# Explanation formatting (Phase F — integrated here for cohesion)
# ─────────────────────────────────────────────────────────────

_EXPLANATION_TEMPLATES: dict[LinkageDecisionState, dict[str, str]] = {
    LinkageDecisionState.link_recommended: {
        "positive": "Records share {support_count} supporting field(s) across {category_count} independent evidence categories.",
        "detail": "Total evidence score {score:.3f} meets the recommendation threshold of {threshold:.3f}.",
        "caution": "Linkage is recommended for authorized review, not autonomous confirmation.",
    },
    LinkageDecisionState.human_review_required: {
        "positive": "Records have {support_count} supporting match(es) but {block_count} unresolved issue(s) prevent automatic linkage.",
        "detail": "Score {score:.3f} is below the automatic-recommendation threshold or evidence is ambiguous.",
        "caution": "Authorized human review is required before any linkage determination.",
    },
    LinkageDecisionState.insufficient_evidence: {
        "positive": "Records lack sufficient distinctive evidence to recommend linkage.",
        "detail": "Score {score:.3f} with no strong discriminators matched.",
        "caution": "Missing information is not a contradiction — request additional evidence when possible.",
    },
    LinkageDecisionState.do_not_link: {
        "positive": "Multiple strong conflicts and no supporting evidence indicate different identities.",
        "detail": "{block_count} strong conflict(s) with no compensating support.",
        "caution": "This is a system recommendation; human review may override with additional evidence.",
    },
    LinkageDecisionState.blocked_by_conflict: {
        "positive": "Automatic linkage is blocked by {block_count} conflict(s) on high-reliability fields.",
        "detail": "Conflicting evidence on fields that strongly discriminate identity.",
        "caution": "Blocked pairs must NOT be automatically linked. Human investigation required to resolve the conflict.",
    },
    LinkageDecisionState.system_error: {
        "positive": "The comparison engine encountered an error.",
        "detail": "No valid comparisons were produced.",
        "caution": "This pair cannot be automatically evaluated. Escalate to system administrator.",
    },
}


def _format_explanation(
    state: LinkageDecisionState,
    reason_codes: list[LinkageReasonCode],
    support_count: int,
    block_count: int,
    total_score: float,
) -> str:
    """Build a human-readable explanation from structured reason codes."""
    templates = _EXPLANATION_TEMPLATES.get(state, _EXPLANATION_TEMPLATES[LinkageDecisionState.system_error])
    category_count = len({rc.value for rc in reason_codes})

    parts = [
        templates["positive"].format(
            support_count=support_count,
            block_count=block_count,
            category_count=category_count,
        ),
        templates["detail"].format(
            score=total_score,
            threshold=LINK_RECOMMENDED_MIN_SCORE,
            block_count=block_count,
        ),
        templates["caution"],
    ]

    if reason_codes:
        codes_str = ", ".join(rc.value for rc in reason_codes)
        parts.append(f"Reason codes: {codes_str}.")

    return " ".join(parts)


def format_structured_explanation(
    decision: LinkageDecision,
    *,
    include_values: bool = False,
) -> str:
    """Generate a structured, evidence-backed explanation for a linkage decision.

    This produces explanations traceable to reason codes, never raw
    confidence scores. Sensitive values are redacted by default.
    """
    state_labels = {
        LinkageDecisionState.link_recommended: "Linkage recommended",
        LinkageDecisionState.human_review_required: "Human review required",
        LinkageDecisionState.insufficient_evidence: "Insufficient evidence",
        LinkageDecisionState.do_not_link: "Do not link",
        LinkageDecisionState.blocked_by_conflict: "Blocked by conflict",
        LinkageDecisionState.system_error: "System error",
    }

    lines = [
        f"Decision: {state_labels.get(decision.state, decision.state.value)}",
        f"Records: {decision.record_id_a} <-> {decision.record_id_b}",
    ]

    if decision.strongest_supporting:
        support_fields = [s.field_name for s in decision.strongest_supporting]
        lines.append(f"Supporting evidence: {', '.join(support_fields)}")
        if include_values:
            for s in decision.strongest_supporting:
                if s.left_value and s.right_value:
                    lines.append(f"  {s.field_name}: '{s.left_value}' ≈ '{s.right_value}'")

    if decision.strongest_conflicting:
        conflict_fields = [c.field_name for c in decision.strongest_conflicting]
        lines.append(f"Conflicting evidence: {', '.join(conflict_fields)}")
        if include_values:
            for c in decision.strongest_conflicting:
                if c.left_value and c.right_value:
                    lines.append(f"  {c.field_name}: '{c.left_value}' ≠ '{c.right_value}'")

    if decision.blocking_conflicts:
        blocking_fields = [b.field_name for b in decision.blocking_conflicts]
        lines.append(f"Blocking conflicts: {', '.join(blocking_fields)}")

    if decision.missing_critical:
        missing_fields = [m.field_name for m in decision.missing_critical]
        lines.append(f"Missing critical evidence: {', '.join(missing_fields)}")

    if decision.candidate_generation_rules:
        lines.append(f"Candidate found via: {', '.join(decision.candidate_generation_rules)}")

    lines.append(f"Score: {decision.total_score:.4f}")
    lines.append(f"False-merge risk: {decision.false_merge_risk}")

    return "\n".join(lines)
