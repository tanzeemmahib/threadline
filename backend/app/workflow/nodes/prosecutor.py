from app.prompts import load_prompt
from app.schemas.models import ProsecutorModelOutput, ValidationResult
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
    )

    async def run(self, context: WorkflowContext) -> NodeOutcome:
        template = load_prompt("prosecutor")
        metadata = []
        evidence_ids: list[str] = []
        for candidate in context.candidates:
            missing = [
                factor.field
                for factor in candidate.compatibility_factors
                if factor.status == "missing"
            ]
            payload = ProsecutorModelOutput(
                conflicts=candidate.conflicts,
                missing_information=missing,
                unresolved_contradictions=[
                    factor.field
                    for factor in candidate.compatibility_factors
                    if factor.status in {"uncertain", "soft_conflict"}
                ],
                suggested_clarification_questions=[candidate.verification_question],
            ).model_dump(mode="json")
            result = await context.provider.generate_structured(
                template_id=template.template_id,
                template_version=template.version,
                system_prompt=template.content,
                user_prompt=f"Structured candidate evidence only: {candidate.model_dump_json()}",
                response_model=ProsecutorModelOutput,
                mock_payload=payload,
            )
            context.model_calls += 1
            context.retries += result.metadata.attempts - 1
            metadata.append(result.metadata)
            report = result.output
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
            summary="Completed an isolated search for hard, soft, missing, and unresolved opposing evidence.",
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
            ],
            evidence_span_ids=evidence_ids,
            provider_metadata=metadata,
        )
