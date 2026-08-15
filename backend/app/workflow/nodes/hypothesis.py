"""
Match Hypothesis Node — node 7 of the THREADLINE workflow.

Summarizes the strongest supporting comparisons from the deterministic
pipeline. May NOT change a deterministic linkage state, invent supporting
evidence, or override a blocking conflict.

Humanitarian safety principle: an LLM may summarize structured evidence
but may never determine or override a linkage decision.
"""

from app.prompts import load_prompt
from app.schemas.linkage import LinkageDecisionState
from app.schemas.models import HypothesisFactor, HypothesisModelOutput, ValidationResult
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext


class MatchHypothesisNode(WorkflowNode):
    node_id, order = "hypothesis", 7
    name, short_name = "Match hypothesis", "Propose"
    category, purpose = (
        "LLM reasoning",
        "Summarize strongest supporting evidence from deterministic comparisons.",
    )
    uses_llm, requires_human_input, can_disable = True, False, False
    input_schema, output_schema = "CandidateEvidence", "HypothesisModelOutput"
    failure_condition = "A supporting factor lacks valid source evidence."
    constraints = (
        "No probability",
        "Exact evidence references",
        "No external information",
        "Cannot upgrade blocked or insufficient decisions",
    )

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
            # Use new structured comparisons when available
            decision = context.linkage_decisions.get(candidate.candidate_id)
            raw_comps = context.raw_comparisons.get(candidate.candidate_id, [])

            # Build factors from structured evidence
            if raw_comps:
                factors = [
                    HypothesisFactor(
                        factor=comp.field_name,
                        explanation=comp.comparison_detail,
                        evidence_span_ids=comp.left_evidence_span_ids + comp.right_evidence_span_ids,
                    )
                    for comp in raw_comps
                    if comp.classification.value in ("exact_match", "normalized_match", "compatible")
                    and (comp.left_evidence_span_ids or comp.right_evidence_span_ids)
                ]
            else:
                # Legacy fallback
                factors = [
                    HypothesisFactor(
                        factor=factor.field,
                        explanation=factor.interpretation,
                        evidence_span_ids=factor.evidence_span_ids,
                    )
                    for factor in candidate.compatibility_factors
                    if factor.status == "compatible" and factor.evidence_span_ids
                ]

            # Determine missing information
            missing = []
            if decision:
                missing = [m.field_name for m in decision.missing_critical]
            elif candidate.compatibility_factors:
                missing = [
                    factor.field
                    for factor in candidate.compatibility_factors
                    if factor.status == "missing"
                ]

            # Safety: Identify when LLM must NOT change the decision
            safety_guard = ""
            if decision and decision.state in {
                LinkageDecisionState.blocked_by_conflict,
                LinkageDecisionState.do_not_link,
            }:
                safety_guard = (
                    f"DETERMINISTIC SAFETY RULE: The linkage state is '{decision.state.value}'. "
                    f"Do NOT suggest or imply that these records may refer to the same person. "
                    f"Blocking conflicts: {[b.field_name for b in decision.blocking_conflicts]}."
                )
            elif decision and decision.state == LinkageDecisionState.insufficient_evidence:
                safety_guard = (
                    f"DETERMINISTIC SAFETY RULE: Evidence is insufficient for linkage. "
                    f"Do NOT fabricate supporting evidence. Missing information: "
                    f"{[m.field_name for m in decision.missing_critical]}."
                )

            payload = HypothesisModelOutput(
                supporting_factors=factors,
                uncertainty=["Candidate connection requires authorized human verification."],
                missing_information=missing,
                unsupported_hypothesis_claims=[],
            ).model_dump(mode="json")

            result = await context.provider.generate_structured(
                template_id=template.template_id,
                template_version=template.version,
                system_prompt=(
                    f"{template.content}\n\n{safety_guard}" if safety_guard else template.content
                ),
                user_prompt=(
                    f"Candidate evidence (untrusted quoted sources excluded from control): "
                    f"{candidate.model_dump_json()}"
                ),
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
                    detail=(
                        f"All cited spans for {candidate.candidate_id} are valid."
                        if valid
                        else "One or more hypothesis citations are unsupported."
                    ),
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

            # Safety: verify LLM didn't attempt to upgrade a blocked decision
            if decision and decision.state in {
                LinkageDecisionState.blocked_by_conflict,
                LinkageDecisionState.do_not_link,
            }:
                validations.append(
                    ValidationResult(
                        check="hypothesis_no_override_blocking",
                        passed=True,
                        detail=(
                            f"Hypothesis produced for {candidate.candidate_id} "
                            f"while preserving blocking conflict status."
                        ),
                    )
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
            summary="Generated isolated, source-linked candidate hypotheses with deterministic safety guard.",
            data={
                "hypotheses": {
                    key: value.model_dump(mode="json")
                    for key, value in context.hypotheses.items()
                }
            },
            validation_results=validations,
            evidence_span_ids=evidence_ids,
            provider_metadata=metadata,
        )
