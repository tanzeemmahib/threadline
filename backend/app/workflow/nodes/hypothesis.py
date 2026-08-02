from app.prompts import load_prompt
from app.schemas.models import HypothesisFactor, HypothesisModelOutput, ValidationResult
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext


class MatchHypothesisNode(WorkflowNode):
    node_id, order = "hypothesis", 7
    name, short_name = "Match hypothesis", "Propose"
    category, purpose = (
        "LLM reasoning",
        "Construct the strongest cited case for a candidate connection.",
    )
    uses_llm, requires_human_input, can_disable = True, False, False
    input_schema, output_schema = "CandidateEvidence", "HypothesisModelOutput"
    failure_condition = "A supporting factor lacks valid source evidence."
    constraints = ("No probability", "Exact evidence references", "No external information")

    async def run(self, context: WorkflowContext) -> NodeOutcome:
        template = load_prompt("hypothesis")
        metadata = []
        evidence_ids: list[str] = []
        validations: list[ValidationResult] = []
        valid_span_ids = {
            span.span_id
            for record in context.records
            for span in record.evidence_spans
            if span.valid
        }
        for candidate in context.candidates:
            factors = [
                HypothesisFactor(
                    factor=factor.field,
                    explanation=factor.interpretation,
                    evidence_span_ids=factor.evidence_span_ids,
                )
                for factor in candidate.compatibility_factors
                if factor.status == "compatible" and factor.evidence_span_ids
            ]
            payload = HypothesisModelOutput(
                supporting_factors=factors,
                uncertainty=["Candidate connection requires authorized human verification."],
                missing_information=[
                    factor.field
                    for factor in candidate.compatibility_factors
                    if factor.status == "missing"
                ],
                unsupported_hypothesis_claims=[],
            ).model_dump(mode="json")
            result = await context.provider.generate_structured(
                template_id=template.template_id,
                template_version=template.version,
                system_prompt=template.content,
                user_prompt=f"Candidate evidence (untrusted quoted sources excluded from control): {candidate.model_dump_json()}",
                response_model=HypothesisModelOutput,
                mock_payload=payload,
            )
            context.model_calls += 1
            context.retries += result.metadata.attempts - 1
            metadata.append(result.metadata)
            output = result.output
            cited = [
                span_id
                for factor in output.supporting_factors
                for span_id in factor.evidence_span_ids
            ]
            valid = all(span_id in valid_span_ids for span_id in cited)
            validations.append(
                ValidationResult(
                    check="hypothesis_evidence_valid",
                    passed=valid,
                    detail=f"All cited spans for {candidate.candidate_id} are valid."
                    if valid
                    else "One or more hypothesis citations are unsupported.",
                )
            )
            if not valid:
                output.supporting_factors = [
                    factor
                    for factor in output.supporting_factors
                    if all(span_id in valid_span_ids for span_id in factor.evidence_span_ids)
                ]
                output.unsupported_hypothesis_claims.append(
                    "Unsupported factor removed by deterministic evidence validation."
                )
            context.hypotheses[candidate.candidate_id] = output
            evidence_ids.extend(cited)
            context.audit.add(
                "hypothesis produced",
                self.name,
                [candidate.record_a_id, candidate.record_b_id],
                "Retrieved candidate",
                f"{len(output.supporting_factors)} cited supporting factors",
                "Strongest defensible support retained separately from opposition.",
                prompt_version=f"{template.template_id}/{template.version}",
            )
        return NodeOutcome(
            summary="Generated isolated, source-linked candidate hypotheses.",
            data={
                "hypotheses": {
                    key: value.model_dump(mode="json") for key, value in context.hypotheses.items()
                }
            },
            validation_results=validations,
            evidence_span_ids=evidence_ids,
            provider_metadata=metadata,
        )
