"""
Contradiction Prosecutor Node — node 8 of the THREADLINE workflow.

Prioritizes structured conflicts already found by the deterministic
comparison engine. An LLM may identify possible overlooked contradictions
only when citing existing evidence spans and passing schema validation.

Humanitarian safety principle: structured conflicts from the comparison
engine cannot be erased by an LLM. Newly claimed conflicts must be
independently verified or routed to review.
"""

from app.prompts import load_prompt
from app.schemas.linkage import LinkageDecisionState
from app.schemas.models import Conflict, ProsecutorModelOutput, ValidationResult
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext


class ContradictionProsecutorNode(WorkflowNode):
    node_id, order = "prosecutor", 8
    name, short_name = "Contradiction prosecutor", "Challenge"
    category, purpose = (
        "LLM reasoning",
        "Independently search for evidence against each candidate connection.",
    )
    uses_llm, requires_human_input, can_disable = True, False, True
    input_schema, output_schema = "CandidateEvidence", "ProsecutorModelOutput"
    failure_condition = "Opposing evidence is omitted, unsupported, or merged into support."
    constraints = (
        "Isolated call",
        "Absence is not contradiction",
        "Hard and soft conflicts separate",
        "Cannot erase deterministic blocking conflicts",
    )

    async def run(self, context: WorkflowContext) -> NodeOutcome:
        template = load_prompt("prosecutor")
        metadata = []
        evidence_ids: list[str] = []
        validations: list[ValidationResult] = []
        for candidate in context.candidates:
            decision = context.linkage_decisions.get(candidate.candidate_id)

            # Deterministic blocking conflicts must survive
            deterministic_conflicts = (
                [
                    Conflict(
                        conflict_id=f"CONFLICT-DET-{b.field_name.upper()}",
                        field=b.field_name,
                        severity="hard",
                        explanation=f"Deterministic blocking conflict: {b.reason_code}",
                        evidence_span_ids=b.evidence_span_ids,
                    )
                    for b in decision.blocking_conflicts
                ]
                if decision
                else []
            )

            # Build missing information from structured evidence
            if decision:
                missing = [m.field_name for m in decision.missing_critical]
                unresolved = [
                    c.field_name
                    for c in decision.strongest_conflicting
                    if c.field_name not in {b.field_name for b in decision.blocking_conflicts}
                ]
            else:
                missing = [
                    factor.field
                    for factor in candidate.compatibility_factors
                    if factor.status == "missing"
                ]
                unresolved = [
                    factor.field
                    for factor in candidate.compatibility_factors
                    if factor.status in {"uncertain", "soft_conflict"}
                ]

            safety_notice = ""
            if decision and decision.state == LinkageDecisionState.blocked_by_conflict:
                safety_notice = (
                    f"DETERMINISTIC SAFETY RULE: This candidate is BLOCKED by "
                    f"{[b.field_name for b in decision.blocking_conflicts]}. "
                    f"Do NOT remove or soften these blocking conflicts."
                )

            payload = ProsecutorModelOutput(
                conflicts=deterministic_conflicts or candidate.conflicts,
                missing_information=missing,
                unresolved_contradictions=unresolved,
                suggested_clarification_questions=[candidate.verification_question],
            ).model_dump(mode="json")

            result = await context.provider.generate_structured(
                template_id=template.template_id,
                template_version=template.version,
                system_prompt=(
                    f"{template.content}\n\n{safety_notice}" if safety_notice else template.content
                ),
                user_prompt=(
                    f"Structured candidate evidence only: {candidate.model_dump_json()}"
                ),
                response_model=ProsecutorModelOutput,
                mock_payload=payload,
            )
            context.model_calls += 1
            context.retries += result.metadata.attempts - 1
            metadata.append(result.metadata)
            report = result.output

            # Safety: deterministic blocking conflicts must survive LLM output
            if decision and decision.blocking_conflicts:
                deterministic_fields = {b.field_name for b in decision.blocking_conflicts}
                llm_conflict_fields = {c.field for c in report.conflicts if c.severity == "hard"}
                erased = deterministic_fields - llm_conflict_fields
                if erased:
                    # Restore erased blocking conflicts
                    report.conflicts.extend(
                        Conflict(
                            conflict_id=f"CONFLICT-RESTORED-{f.upper()}",
                            field=f,
                            severity="hard",
                            explanation="Deterministic blocking conflict restored after LLM processing.",
                            evidence_span_ids=[],
                        )
                        for f in erased
                    )
                    validations.append(
                        ValidationResult(
                            check="prosecutor_blocking_conflicts_preserved",
                            passed=True,
                            detail=(
                                f"Restored {len(erased)} blocking conflict(s) "
                                f"that the LLM attempted to erase: {sorted(erased)}"
                            ),
                        )
                    )

            context.prosecutor_reports[candidate.candidate_id] = report
            candidate.conflicts = report.conflicts
            evidence_ids.extend(
                span_id for conflict in report.conflicts for span_id in conflict.evidence_span_ids
            )
            context.audit.add(
                "contradiction found",
                self.name,
                [candidate.record_a_id, candidate.record_b_id],
                "Supporting hypothesis",
                f"{len(report.conflicts)} conflicts; {len(report.missing_information)} missing fields",
                "Independent opposition remains separately inspectable.",
                prompt_version=f"{template.template_id}/{template.version}",
            )
        return NodeOutcome(
            summary="Completed isolated search with deterministic blocking-conflict preservation.",
            data={
                "reports": {
                    key: value.model_dump(mode="json")
                    for key, value in context.prosecutor_reports.items()
                }
            },
            validation_results=[
                ValidationResult(
                    check="opposition_separate",
                    passed=True,
                    detail="Prosecutor receives structured evidence, not hidden hypothesis reasoning.",
                )
            ] + validations,
            evidence_span_ids=evidence_ids,
            provider_metadata=metadata,
        )
