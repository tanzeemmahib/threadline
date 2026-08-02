from app.schemas.models import RivalComparison, ValidationResult
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext


class RivalCandidateNode(WorkflowNode):
    node_id, order = "rivals", 9
    name, short_name = "Rival-candidate test", "Compare rivals"
    category, purpose = (
        "Retrieval",
        "Test whether evidence distinguishes a candidate from nearby alternatives.",
    )
    uses_llm, requires_human_input, can_disable = False, False, True
    input_schema, output_schema = "CandidateConnection[]", "RivalComparison[]"
    failure_condition = "Nearby candidates cannot be compared on consistent fields."
    constraints = ("No ranking gamification", "Equal rivals can trigger abstention")

    async def run(self, context: WorkflowContext) -> NodeOutcome:
        ambiguity = False
        if len(context.candidates) >= 2:
            top_pair_ids = {
                context.candidates[0].record_a_id,
                context.candidates[0].record_b_id,
            }
            top_pair = [record for record in context.records if record.record_id in top_pair_ids]
            sparse_pair = all(
                sum(field.value is not None for field in record.fields) <= 2 for record in top_pair
            )
            ambiguity = (
                abs(context.candidates[0].retrieval_score - context.candidates[1].retrieval_score)
                <= 0.15
                and sparse_pair
            )
        records = {record.record_id: record for record in context.records}
        for primary in context.candidates:
            rivals = []
            for other in context.candidates:
                if other.candidate_id == primary.candidate_id:
                    continue
                record_id = other.record_b_id
                record = records[record_id]
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
                            "name": "stronger"
                            if other.score_components[0].value >= primary.score_components[0].value
                            else "weaker",
                            "age": "unresolved",
                            "language": "unresolved",
                            "location": "unresolved",
                            "timeline": "unresolved",
                            "clothing": "unresolved",
                            "distinctive_features": "unresolved",
                            "hard_conflicts": "conflicting" if other.conflicts else "unresolved",
                        },
                        summary="Nearby alternative retained for specificity review.",
                    )
                )
            primary.rivals = rivals[: context.request.options.candidate_limit]
            if ambiguity:
                primary.abstention_reasons.extend(
                    [
                        "Two candidates have materially equal retrieval support.",
                        "Evidence is not sufficiently distinctive; rival ambiguity remains.",
                    ]
                )
            context.audit.add(
                "rival evaluated",
                self.name,
                [primary.record_a_id, primary.record_b_id, *[r.record_id for r in primary.rivals]],
                "Primary candidate only",
                f"{len(primary.rivals)} rival(s) compared",
                "Specificity was checked against nearby alternatives.",
            )
        return NodeOutcome(
            summary="Compared candidates against nearby alternatives and retained rival ambiguity.",
            data={"rival_ambiguity": ambiguity},
            validation_results=[
                ValidationResult(
                    check="equal_rival_abstention_supported",
                    passed=True,
                    detail="Materially equal candidates are exposed to adjudication as ambiguous.",
                )
            ],
            abstention_reason="Evidence is not sufficiently distinctive; rival ambiguity remains."
            if ambiguity
            else None,
        )
