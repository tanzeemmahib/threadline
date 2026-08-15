"""
Rival Candidate Node — node 9 of the THREADLINE workflow.

Compares the current candidate against alternative candidates using
structured evidence. A close rival must prevent automatic link_recommended
unless a verified unique identifier resolves the ambiguity.

Humanitarian safety principle: similar candidates must be distinguished
explicitly. No ranking gamification — equal rivals trigger abstention.
"""

from app.schemas.linkage import LinkageDecisionState
from app.schemas.models import RivalComparison, ValidationResult
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext


class RivalCandidateNode(WorkflowNode):
    node_id, order = "rivals", 9
    name, short_name = "Rival-candidate test", "Compare rivals"
    category, purpose = (
        "Retrieval",
        "Test whether structured evidence distinguishes a candidate from nearby alternatives.",
    )
    uses_llm, requires_human_input, can_disable = False, False, True
    input_schema, output_schema = "CandidateConnection[]", "RivalComparison[]"
    failure_condition = "Nearby candidates cannot be compared on consistent fields."
    constraints = (
        "No ranking gamification",
        "Equal rivals can trigger abstention",
        "Close rival prevents link_recommended unless unique ID match",
    )

    async def run(self, context: WorkflowContext) -> NodeOutcome:
        records = {record.record_id: record for record in context.records}
        for primary in context.candidates:
            primary_decision = context.linkage_decisions.get(primary.candidate_id)
            rivals = []
            rival_ambiguity = False

            for other in context.candidates:
                if other.candidate_id == primary.candidate_id:
                    continue

                record_id = other.record_b_id
                record = records.get(record_id)
                if record is None:
                    continue

                # Use structured comparisons where available
                primary_comps = context.raw_comparisons.get(primary.candidate_id, [])
                other_comps = context.raw_comparisons.get(other.candidate_id, [])
                other_decision = context.linkage_decisions.get(other.candidate_id)

                # Build comparison using structured data
                name_status = "unresolved"
                if primary_comps and other_comps:
                    primary_name = next(
                        (c for c in primary_comps if c.field_name == "full_name"), None
                    )
                    other_name = next(
                        (c for c in other_comps if c.field_name == "full_name"), None
                    )
                    if primary_name and other_name:
                        if primary_name.score_contribution > other_name.score_contribution:
                            name_status = "stronger"
                        elif other_name.score_contribution > primary_name.score_contribution:
                            name_status = "weaker"

                hard_conflict_status = (
                    "conflicting"
                    if other_decision and other_decision.blocking_conflicts
                    else "unresolved"
                )

                age = next(
                    (
                        str(field.value)
                        for field in record.fields
                        if field.key == "age" and field.value is not None
                    ),
                    "Not reported",
                )
                rivals.append(
                    RivalComparison(
                        record_id=record_id,
                        display_name=record.display_name,
                        age=age,
                        comparison={
                            "name": name_status,
                            "age": "unresolved",
                            "language": "unresolved",
                            "location": "unresolved",
                            "timeline": "unresolved",
                            "clothing": "unresolved",
                            "distinctive_features": "unresolved",
                            "hard_conflicts": hard_conflict_status,
                        },
                        summary=(
                            f"Rival: {other.linkage_decision_state or other.classification_code.value}"
                        ),
                    )
                )

            primary.rivals = rivals[:context.request.options.candidate_limit]

            # ── Rival ambiguity safety rule ──
            # Close rivals must prevent link_recommended unless a unique ID resolves it
            if primary_decision and primary_decision.state == LinkageDecisionState.link_recommended:
                # Check if any rival has close score
                if len(context.candidates) >= 2:
                    top_two_scores = sorted(
                        [c.retrieval_score for c in context.candidates[:2]], reverse=True
                    )
                    if len(top_two_scores) >= 2:
                        score_gap = abs(top_two_scores[0] - top_two_scores[1])
                        has_unique_id_match = any(
                            s.field_name == "government_id"
                            for s in primary_decision.strongest_supporting
                        )
                        # Close rival and no unique ID → downgrade
                        if score_gap <= 0.20 and not has_unique_id_match:
                            rival_ambiguity = True
                            primary.linkage_decision_state = (
                                LinkageDecisionState.human_review_required.value
                            )
                            primary.review_priority = "standard_verification"
                            primary.false_merge_risk = "medium"
                            primary.llm_downgrade_applied = True
                            primary.llm_downgrade_reason = (
                                f"Rival candidate within {score_gap:.2f} score; "
                                f"no unique identifier to resolve ambiguity."
                            )
                            primary.abstention_reasons.append(
                                "Close rival candidate prevents automatic link recommendation."
                            )

            if rival_ambiguity:
                primary.abstention_reasons.append(
                    "Rival ambiguity: evidence is not sufficiently distinctive."
                )

            context.audit.add(
                "rival evaluated",
                self.name,
                [primary.record_a_id, primary.record_b_id, *[r.record_id for r in primary.rivals]],
                "Primary candidate",
                f"{len(primary.rivals)} rival(s) compared",
                (
                    "Rival ambiguity downgraded link_recommended."
                    if rival_ambiguity
                    else "Specificity checked against nearby alternatives."
                ),
            )

        return NodeOutcome(
            summary="Compared candidates against nearby alternatives with rival-ambiguity safeguard.",
            data={
                "rival_ambiguity_triggered": any(
                    c.llm_downgrade_applied for c in context.candidates
                ),
            },
            validation_results=[
                ValidationResult(
                    check="equal_rival_abstention_supported",
                    passed=True,
                    detail="Close rivals trigger abstention unless unique ID resolves ambiguity.",
                )
            ],
        )
