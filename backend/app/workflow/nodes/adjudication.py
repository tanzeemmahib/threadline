from collections import Counter

from app.prompts import load_prompt
from app.schemas.models import AdjudicationModelOutput, Classification, ValidationResult
from app.services.candidate_scoring import DISPLAY_CLASSIFICATION
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext


class IndependentAdjudicationNode(WorkflowNode):
    node_id, order = "adjudicate", 10
    name, short_name = "Independent adjudication", "Adjudicate"
    category, purpose = (
        "LLM reasoning",
        "Aggregate isolated structured adjudications using observable outcomes.",
    )
    uses_llm, requires_human_input, can_disable = True, False, True
    input_schema, output_schema = "AdjudicationPacket", "AdjudicationModelOutput[]"
    failure_condition = "Support, opposition, rivals, or deterministic checks are unavailable."
    constraints = (
        "Exactly four allowed classifications",
        "No probability",
        "At least two isolated real-provider adjudications",
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
            hard_count = sum(conflict.severity == "hard" for conflict in candidate.conflicts)
            rival_ambiguity = bool(candidate.abstention_reasons)
            if hard_count:
                fixture_classification = Classification.conflicting_evidence
            elif (
                rival_ambiguity
                or candidate.classification_code == Classification.insufficient_evidence
            ):
                fixture_classification = Classification.insufficient_evidence
            else:
                fixture_classification = candidate.classification_code
            outputs = []
            for _ in range(count):
                fixture = AdjudicationModelOutput(
                    classification=fixture_classification,
                    reasons=[candidate.supporting_summary, candidate.opposing_summary],
                    unresolved_issues=candidate.abstention_reasons,
                    hard_conflict_count=hard_count,
                    evidence_coverage="insufficient"
                    if fixture_classification == Classification.insufficient_evidence
                    else "partial",
                    rival_ambiguity=rival_ambiguity,
                    recommended_human_action="Request more information and conduct independent authorized verification."
                    if fixture_classification == Classification.insufficient_evidence
                    else "Route the evidence packet to authorized human review.",
                )
                hypothesis = context.hypotheses.get(candidate.candidate_id)
                prosecutor = context.prosecutor_reports.get(candidate.candidate_id)
                hypothesis_json = hypothesis.model_dump_json() if hypothesis else "{}"
                prosecutor_json = prosecutor.model_dump_json() if prosecutor else "{}"
                result = await context.provider.generate_structured(
                    template_id=template.template_id,
                    template_version=template.version,
                    system_prompt=template.content,
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
            if hard_count:
                selected = Classification.conflicting_evidence
            elif rival_ambiguity:
                selected = Classification.insufficient_evidence
            candidate.classification_code = selected
            candidate.classification = DISPLAY_CLASSIFICATION[selected]
            candidate.label = (
                DISPLAY_CLASSIFICATION[selected]
                if selected
                in {Classification.conflicting_evidence, Classification.insufficient_evidence}
                else f"{DISPLAY_CLASSIFICATION[selected]} connection"
            )
            candidate.adjudicator_agreement = len(votes) == 1
            validations.append(
                ValidationResult(
                    check="allowed_classification",
                    passed=selected in Classification,
                    detail=f"{candidate.candidate_id}: {selected.value}",
                )
            )
            context.audit.add(
                "adjudication produced",
                self.name,
                [candidate.record_a_id, candidate.record_b_id],
                "Support, opposition, rivals, and checks",
                selected.value,
                "Observable outcomes aggregated without a probability.",
                prompt_version=f"{template.template_id}/{template.version}",
            )
        return NodeOutcome(
            summary="Aggregated isolated adjudications into allowed review classifications without probabilities.",
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
