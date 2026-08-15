"""
Independent Adjudication Node — node 10 of the THREADLINE workflow.

Treats the deterministic linkage decision as the safety floor.
May only preserve or downgrade; may never upgrade blocked, do_not_link,
or insufficient_evidence to link_recommended.

Humanitarian safety principle: LLM adjudication cannot override
deterministic safety rules. Every attempted state transition is recorded.
"""

from collections import Counter

from app.prompts import load_prompt
from app.schemas.linkage import LinkageDecisionState
from app.schemas.models import AdjudicationModelOutput, Classification, ValidationResult
from app.services.candidate_scoring import DISPLAY_CLASSIFICATION
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext

# ── Allowed state transitions (deterministic → adjudicated) ──
# Only these transitions are permitted. Anything else is rejected.
ALLOWED_TRANSITIONS: dict[LinkageDecisionState, set[LinkageDecisionState]] = {
    LinkageDecisionState.link_recommended: {
        LinkageDecisionState.link_recommended,
        LinkageDecisionState.human_review_required,
        LinkageDecisionState.insufficient_evidence,
    },
    LinkageDecisionState.human_review_required: {
        LinkageDecisionState.human_review_required,
        LinkageDecisionState.insufficient_evidence,
        LinkageDecisionState.blocked_by_conflict,
    },
    LinkageDecisionState.insufficient_evidence: {
        LinkageDecisionState.insufficient_evidence,
    },
    LinkageDecisionState.do_not_link: {
        LinkageDecisionState.do_not_link,
        LinkageDecisionState.blocked_by_conflict,
    },
    LinkageDecisionState.blocked_by_conflict: {
        LinkageDecisionState.blocked_by_conflict,
    },
    LinkageDecisionState.system_error: {
        LinkageDecisionState.system_error,
        LinkageDecisionState.human_review_required,
        LinkageDecisionState.insufficient_evidence,
    },
}


class IndependentAdjudicationNode(WorkflowNode):
    node_id, order = "adjudicate", 10
    name, short_name = "Independent adjudication", "Adjudicate"
    category, purpose = (
        "LLM reasoning",
        "Aggregate isolated structured adjudications with deterministic safety floor.",
    )
    uses_llm, requires_human_input, can_disable = True, False, True
    input_schema, output_schema = "AdjudicationPacket", "AdjudicationModelOutput[]"
    failure_condition = "Support, opposition, rivals, or deterministic checks are unavailable."
    constraints = (
        "Deterministic decision is safety floor",
        "May preserve or downgrade only",
        "May never upgrade blocked/insufficient to link_recommended",
        "Every transition is recorded with reason code",
    )

    async def run(self, context: WorkflowContext) -> NodeOutcome:
        template = load_prompt("adjudication")
        metadata = []
        evidence_ids: list[str] = []
        validations: list[ValidationResult] = []
        count = (
            max(2, context.request.options.adjudicator_count)
            if not context.mock_mode
            else context.request.options.adjudicator_count
        )
        for candidate in context.candidates:
            decision = context.linkage_decisions.get(candidate.candidate_id)
            deterministic_state = decision.state if decision else None
            hard_count = sum(
                conflict.severity == "hard" for conflict in candidate.conflicts
            )
            rival_ambiguity = bool(candidate.abstention_reasons)

            # Fixture classification respects deterministic floor
            if hard_count or (
                deterministic_state == LinkageDecisionState.blocked_by_conflict
            ):
                fixture_classification = Classification.conflicting_evidence
            elif rival_ambiguity:
                fixture_classification = Classification.insufficient_evidence
            elif deterministic_state == LinkageDecisionState.link_recommended:
                fixture_classification = Classification.strong_candidate_for_review
            elif deterministic_state == LinkageDecisionState.human_review_required:
                fixture_classification = Classification.possible_candidate
            elif deterministic_state == LinkageDecisionState.insufficient_evidence:
                fixture_classification = Classification.insufficient_evidence
            else:
                fixture_classification = candidate.classification_code

            # Safety notice in system prompt
            safety_notice = ""
            if deterministic_state:
                allowed = ALLOWED_TRANSITIONS.get(deterministic_state, {deterministic_state})
                safety_notice = (
                    f"DETERMINISTIC SAFETY FLOOR: The initial linkage state is "
                    f"'{deterministic_state.value}'. You may only PRESERVE this state "
                    f"or DOWNGRADE to one of: {sorted(s.value for s in allowed)}. "
                    f"You MUST NOT upgrade to link_recommended from blocked, do_not_link, "
                    f"or insufficient_evidence states."
                )

            outputs = []
            for _ in range(count):
                fixture = AdjudicationModelOutput(
                    classification=fixture_classification,
                    reasons=[
                        candidate.supporting_summary,
                        candidate.opposing_summary,
                    ],
                    unresolved_issues=candidate.abstention_reasons,
                    hard_conflict_count=hard_count,
                    evidence_coverage=(
                        "insufficient"
                        if fixture_classification == Classification.insufficient_evidence
                        else "partial"
                    ),
                    rival_ambiguity=rival_ambiguity,
                    recommended_human_action=(
                        "Request more information and conduct independent authorized verification."
                        if fixture_classification == Classification.insufficient_evidence
                        else "Route the evidence packet to authorized human review."
                    ),
                )
                hypothesis = context.hypotheses.get(candidate.candidate_id)
                prosecutor = context.prosecutor_reports.get(candidate.candidate_id)
                hypothesis_json = hypothesis.model_dump_json() if hypothesis else "{}"
                prosecutor_json = prosecutor.model_dump_json() if prosecutor else "{}"
                result = await context.provider.generate_structured(
                    template_id=template.template_id,
                    template_version=template.version,
                    system_prompt=(
                        f"{template.content}\n\n{safety_notice}"
                        if safety_notice
                        else template.content
                    ),
                    user_prompt=(
                        f"Structured evidence packet: candidate={candidate.model_dump_json()} "
                        f"hypothesis={hypothesis_json} prosecutor={prosecutor_json}"
                    ),
                    response_model=AdjudicationModelOutput,
                    mock_payload=fixture.model_dump(mode="json"),
                )
                context.model_calls += 1
                context.retries += result.metadata.attempts - 1
                metadata.append(result.metadata)
                outputs.append(result.output)

            context.adjudications[candidate.candidate_id] = outputs
            votes = Counter(output.classification for output in outputs)
            selected = votes.most_common(1)[0][0]

            # ── Safety: enforce deterministic floor ──
            if hard_count or deterministic_state == LinkageDecisionState.blocked_by_conflict:
                selected = Classification.conflicting_evidence
                candidate.linkage_decision_state = LinkageDecisionState.blocked_by_conflict.value
            elif rival_ambiguity:
                selected = Classification.insufficient_evidence
                if deterministic_state == LinkageDecisionState.link_recommended:
                    candidate.linkage_decision_state = LinkageDecisionState.human_review_required.value
                    candidate.llm_downgrade_applied = True
                    candidate.llm_downgrade_reason = "Rival ambiguity downgraded link_recommended."
            elif deterministic_state == LinkageDecisionState.insufficient_evidence:
                selected = Classification.insufficient_evidence
            elif deterministic_state == LinkageDecisionState.do_not_link:
                selected = Classification.conflicting_evidence

            # Record transition
            transition_recorded = (
                f"deterministic={deterministic_state.value if deterministic_state else 'none'} "
                f"→ adjudicated={selected.value}"
            )

            candidate.classification_code = selected
            candidate.classification = DISPLAY_CLASSIFICATION[selected]
            candidate.label = (
                DISPLAY_CLASSIFICATION[selected]
                if selected in {
                    Classification.conflicting_evidence,
                    Classification.insufficient_evidence,
                }
                else f"{DISPLAY_CLASSIFICATION[selected]} connection"
            )
            candidate.adjudicator_agreement = len(votes) == 1

            validations.append(
                ValidationResult(
                    check="allowed_classification",
                    passed=selected in Classification,
                    detail=f"{candidate.candidate_id}: {selected.value} ({transition_recorded})",
                )
            )

            # Validate no unsafe upgrade occurred
            if deterministic_state in {
                LinkageDecisionState.blocked_by_conflict,
                LinkageDecisionState.do_not_link,
                LinkageDecisionState.insufficient_evidence,
            }:
                unsafe_upgrade = (
                    selected == Classification.strong_candidate_for_review
                )
                validations.append(
                    ValidationResult(
                        check="no_unsafe_upgrade",
                        passed=not unsafe_upgrade,
                        detail=(
                            f"Decision preserved at {selected.value}; "
                            f"no unsafe upgrade from {deterministic_state.value}."
                        ),
                    )
                )

            context.audit.add(
                "adjudication produced",
                self.name,
                [candidate.record_a_id, candidate.record_b_id],
                "Support, opposition, rivals, and checks",
                f"{selected.value} ({transition_recorded})",
                "Observable outcomes aggregated with deterministic safety floor.",
                prompt_version=f"{template.template_id}/{template.version}",
            )

        return NodeOutcome(
            summary="Aggregated adjudications with deterministic safety floor; no unsafe upgrades.",
            data={
                "adjudications": {
                    key: [item.model_dump(mode="json") for item in value]
                    for key, value in context.adjudications.items()
                }
            },
            validation_results=validations,
            evidence_span_ids=evidence_ids,
            provider_metadata=metadata,
        )
