"""
Candidate Retrieval Node — node 6 of the THREADLINE workflow.

Replaced legacy all-pairs retrieval with the new deterministic identity-
resolution pipeline: candidate generation → pairwise structured comparison
→ deterministic linkage decision.

Humanitarian safety principle: candidate generation is a recall step, not a
decision. No LLM call occurs here. Every candidate carries blocking reason
codes and structured evidence references.
"""

from __future__ import annotations

from app.schemas.linkage import LinkageDecisionState
from app.schemas.models import (
    CandidateConnection,
    Certainty,
    Classification,
    CompatibilityFactor,
    Conflict,
    ScoreComponent,
    ValidationResult,
)
from app.services.candidate_generation import generate_candidates
from app.services.candidate_scoring import DISPLAY_CLASSIFICATION
from app.services.pairwise_compare import (
    compare_records,
    total_linkage_score,
)
from app.services.linkage_decision import determine_linkage
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext

# ── Mapping from LinkageDecisionState to legacy Classification ──
# This preserves backward compatibility with nodes 7-12 that consume
# classification_code, while the authoritative result is in linkage_decision.
STATE_TO_CLASSIFICATION: dict[LinkageDecisionState, Classification] = {
    LinkageDecisionState.link_recommended: Classification.strong_candidate_for_review,
    LinkageDecisionState.human_review_required: Classification.possible_candidate,
    LinkageDecisionState.insufficient_evidence: Classification.insufficient_evidence,
    LinkageDecisionState.do_not_link: Classification.conflicting_evidence,
    LinkageDecisionState.blocked_by_conflict: Classification.conflicting_evidence,
    LinkageDecisionState.system_error: Classification.insufficient_evidence,
}


def _comparisons_to_compatibility(comparisons, rank: int, record_a_id: str, record_b_id: str):
    """Convert FieldComparison list to legacy CompatibilityFactor and Conflict lists."""
    factors = []
    conflicts = []
    for comp in comparisons:
        if comp.classification.value.startswith("missing_"):
            continue
        # Compatibility factor
        status = (
            "compatible" if comp.classification.value in ("exact_match", "normalized_match", "compatible")
            else "soft_conflict" if comp.classification.value == "partial_match"
            else "hard_conflict" if comp.classification.value == "strong_conflict"
            else "uncertain" if comp.classification.value == "conflict"
            else "missing"
        )
        factors.append(CompatibilityFactor(
            factor_id=f"CF-{rank}-{comp.field_name.upper()}",
            field=comp.field_name,
            record_a_value=comp.left_value or "Not reported",
            record_b_value=comp.right_value or "Not reported",
            status=status,
            interpretation=comp.comparison_detail,
            certainty_a=comp.left_certainty,
            certainty_b=comp.right_certainty,
            evidence_span_ids=comp.left_evidence_span_ids + comp.right_evidence_span_ids,
        ))
        if status == "hard_conflict":
            conflicts.append(Conflict(
                conflict_id=f"CONFLICT-{rank}-{comp.field_name.upper()}",
                field=comp.field_name,
                severity="hard",
                explanation=comp.comparison_detail,
                evidence_span_ids=comp.left_evidence_span_ids + comp.right_evidence_span_ids,
            ))
    return factors, conflicts


def _comparisons_to_scores(comparisons, rank: int):
    """Convert FieldComparison list to legacy ScoreComponent list."""
    return [
        ScoreComponent(
            field=comp.field_name,
            value=comp.score_contribution,
            explanation=comp.comparison_detail,
        )
        for comp in comparisons
        if comp.score_contribution > 0 or comp.classification.value.startswith("missing_")
    ]


class CandidateRetrievalNode(WorkflowNode):
    node_id, order = "retrieve", 6
    name, short_name = "Candidate retrieval", "Retrieve"
    category, purpose = (
        "Retrieval",
        "Generate bounded candidate pairs with structured comparison and deterministic linkage decisions.",
    )
    uses_llm, requires_human_input, can_disable = False, False, False
    input_schema, output_schema = "NormalizedRecord[]", "CandidateConnection[]"
    failure_condition = "No discriminating fields are available; explicit abstention remains valid."
    constraints = (
        "Favor recall",
        "Score is not probability",
        "Missing fields do not automatically discard",
        "Unique-identifier candidates survive caps",
        "No LLM call in candidate generation or comparison",
    )

    async def run(self, context: WorkflowContext) -> NodeOutcome:
        records = context.records
        if not records or len(records) < 2:
            context.candidates = []
            return NodeOutcome(
                summary="Insufficient records for candidate generation.",
                data={"candidate_ids": [], "candidates_generated": 0},
                abstention_reason="Fewer than two records available for comparison.",
            )

        # ── Step 1: Candidate generation ──
        raw_candidates = generate_candidates(
            records,
            max_candidates=context.request.options.candidate_limit * 3,  # generous for safety
        )

        # Compatibility fallback: if no candidates from blocking, use legacy all-pairs
        if not raw_candidates:
            from app.services.candidate_scoring import retrieve_candidates as legacy_retrieve
            legacy_candidates = legacy_retrieve(
                records,
                context.request.options.candidate_limit,
                use_timeline="timeline" not in context.disabled_nodes,
            )
            context.candidates = legacy_candidates
            for candidate in context.candidates:
                context.audit.add(
                    "candidate retrieved (legacy fallback)",
                    self.name,
                    [candidate.record_a_id, candidate.record_b_id],
                    "No candidate pair",
                    candidate.candidate_id,
                    "Legacy retrieval: no blocking strategies matched.",
                )
            return NodeOutcome(
                summary=(
                    f"Retrieved {len(context.candidates)} candidate(s) "
                    f"via legacy fallback (no blocking matches)."
                ),
                data={
                    "candidate_ids": [c.candidate_id for c in context.candidates],
                    "ranking_signal_only": True,
                    "fallback_to_legacy": True,
                },
                validation_results=[
                    ValidationResult(
                        check="no_probability_exposed",
                        passed=True,
                        detail="Legacy scores are retrieval ranking signals only.",
                    )
                ],
                evidence_span_ids=[
                    span.span_id for record in context.records for span in record.evidence_spans
                ],
            )

        # ── Step 2: Ensure unique-identifier candidates survive caps ──
        # Re-sort: put gov_id candidates first, then by rule count
        gov_id_pairs = [
            (a, b, rules) for a, b, rules in raw_candidates
            if "government_id" in rules
        ]
        other_pairs = [
            (a, b, rules) for a, b, rules in raw_candidates
            if "government_id" not in rules
        ]
        capped = gov_id_pairs + other_pairs
        capped = capped[:context.request.options.candidate_limit]

        # ── Step 3: For each candidate, run comparison + decision ──
        record_map = {r.record_id: r for r in records}
        candidates: list[CandidateConnection] = []

        for rank, (rid_a, rid_b, rule_ids) in enumerate(capped, 1):
            rec_a = record_map.get(rid_a)
            rec_b = record_map.get(rid_b)
            if rec_a is None or rec_b is None:
                continue

            # Pairwise structured comparison
            comparisons = compare_records(rec_a, rec_b)
            score = total_linkage_score(comparisons)

            # Deterministic linkage decision
            decision = determine_linkage(
                comparisons,
                rid_a,
                rid_b,
                display_name_a=rec_a.display_name,
                display_name_b=rec_b.display_name,
                candidate_generation_rules=rule_ids,
            )

            # Store in context
            candidate_id = f"MATCH-{rank:03d}"
            context.linkage_decisions[candidate_id] = decision
            context.raw_comparisons[candidate_id] = comparisons
            context.candidate_generation_rules[candidate_id] = rule_ids

            # Convert to backward-compatible CandidateConnection
            factors, conflicts = _comparisons_to_compatibility(
                comparisons, rank, rid_a, rid_b
            )
            score_components = _comparisons_to_scores(comparisons, rank)

            # Map decision state to legacy classification
            legacy_cls = STATE_TO_CLASSIFICATION.get(
                decision.state, Classification.insufficient_evidence
            )

            # Build supporting/opposing summaries from decision
            support_fields = [s.field_name for s in decision.strongest_supporting]
            conflict_fields = [c.field_name for c in decision.strongest_conflicting]
            block_fields = [b.field_name for b in decision.blocking_conflicts]
            missing_fields = [m.field_name for m in decision.missing_critical]

            supporting_summary = (
                f"Supporting fields: {', '.join(support_fields)}."
                if support_fields
                else "No strong supporting evidence."
            )
            opposing_summary = (
                f"Blocking conflicts: {', '.join(block_fields)}. "
                f"Conflicts: {', '.join(conflict_fields)}."
                if block_fields or conflict_fields
                else "No opposing evidence found."
            )

            is_fallback = any(r.startswith("fallback_") for r in rule_ids)

            candidate = CandidateConnection(
                candidate_id=candidate_id,
                record_a_id=rid_a,
                record_b_id=rid_b,
                label=(
                    DISPLAY_CLASSIFICATION[legacy_cls]
                    if legacy_cls in {Classification.conflicting_evidence, Classification.insufficient_evidence}
                    else f"{DISPLAY_CLASSIFICATION[legacy_cls]} connection"
                ),
                classification=DISPLAY_CLASSIFICATION[legacy_cls],
                classification_code=legacy_cls,
                supporting_summary=supporting_summary,
                opposing_summary=opposing_summary,
                verification_question=(
                    "Can an authorized reviewer verify one independent distinctive detail?"
                ),
                verification_explanation=(
                    "A distinctive, independently sourced detail can help resolve remaining ambiguity."
                ),
                compatibility_factors=factors,
                conflicts=conflicts,
                retrieval_score=score,
                score_components=score_components,
                rank=rank,
                # ── New identity-resolution fields ──
                blocking_reason_codes=[b.reason_code for b in decision.blocking_conflicts],
                candidate_generation_rules=rule_ids,
                candidate_fallback=is_fallback,
                pairwise_comparisons=[
                    {
                        "field_name": c.field_name,
                        "classification": c.classification.value,
                        "reason_code": c.reason_code,
                        "score_contribution": c.score_contribution,
                    }
                    for c in comparisons
                ],
                linkage_decision=decision.model_dump(mode="json"),
                linkage_decision_state=decision.state.value,
                false_merge_risk=decision.false_merge_risk,
                review_priority=_review_priority(decision.state),
                abstention_reasons=(
                    [f"Missing critical evidence: {', '.join(missing_fields)}"]
                    if missing_fields and decision.state == LinkageDecisionState.insufficient_evidence
                    else [f"Blocked by: {', '.join(block_fields)}"]
                    if block_fields
                    else []
                ),
            )
            candidates.append(candidate)

            # Audit
            context.audit.add(
                "candidate generated",
                self.name,
                [rid_a, rid_b],
                "Normalized records",
                candidate_id,
                (
                    f"Structured comparison: {len(comparisons)} fields, "
                    f"score={score:.4f}, state={decision.state.value}, "
                    f"rules={rule_ids}"
                ),
            )

        context.candidates = candidates

        abstention = (
            "No candidate pairs were generated by any blocking strategy."
            if not candidates
            else None
        )

        return NodeOutcome(
            summary=(
                f"Generated {len(candidates)} candidate(s) via {len(raw_candidates)} "
                f"blocking-produced pairs; {len(gov_id_pairs)} with unique identifiers."
            ),
            data={
                "candidate_ids": [c.candidate_id for c in candidates],
                "candidates_generated": len(candidates),
                "raw_candidates": len(raw_candidates),
                "gov_id_candidates": len(gov_id_pairs),
                "fallback_used": any(c.candidate_fallback for c in candidates),
                "linkage_states": {
                    c.candidate_id: c.linkage_decision_state
                    for c in candidates
                },
                "ranking_signal_only": True,
                "deterministic_pipeline": True,
            },
            validation_results=[
                ValidationResult(
                    check="no_probability_exposed",
                    passed=True,
                    detail="Scores are deterministic comparison outputs, not probabilities.",
                ),
                ValidationResult(
                    check="deterministic_candidate_generation",
                    passed=True,
                    detail="Candidate generation uses deterministic blocking rules.",
                ),
                ValidationResult(
                    check="no_llm_in_comparison",
                    passed=True,
                    detail="Comparison and decision are deterministic; no LLM call made.",
                ),
            ],
            evidence_span_ids=[
                span.span_id for record in context.records for span in record.evidence_spans
            ],
            abstention_reason=abstention,
        )


def _review_priority(state: LinkageDecisionState) -> str:
    """Map linkage decision state to review priority level."""
    mapping = {
        LinkageDecisionState.blocked_by_conflict: "urgent_conflict_review",
        LinkageDecisionState.link_recommended: "high_priority_verification",
        LinkageDecisionState.human_review_required: "standard_verification",
        LinkageDecisionState.insufficient_evidence: "request_more_information",
        LinkageDecisionState.do_not_link: "no_action_recommended",
        LinkageDecisionState.system_error: "technical_failure",
    }
    return mapping.get(state, "standard_verification")
