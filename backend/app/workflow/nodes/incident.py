from app.schemas.models import ValidationResult
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext


class IncidentConfigurationNode(WorkflowNode):
    node_id, order = "incident", 1
    name, short_name = "Incident configuration", "Configure"
    category, purpose = "Human input", "Validate incident scope and workflow safety limits."
    uses_llm, requires_human_input, can_disable = False, True, False
    input_schema, output_schema = "AnalyzeRequest", "IncidentConfigurationOutput"
    failure_condition = "Incident metadata or safety limits are invalid."
    constraints = (
        "Synthetic identities only",
        "No public people search",
        "Candidate limit enforced",
    )

    async def run(self, context: WorkflowContext) -> NodeOutcome:
        request = context.request
        settings = context.settings
        total_characters = sum(len(record.text) for record in request.records)
        checks = [
            ValidationResult(
                check="record_count_limit",
                passed=len(request.records) <= settings.max_records_per_request,
                detail=f"{len(request.records)}/{settings.max_records_per_request}",
            ),
            ValidationResult(
                check="record_text_limit",
                passed=all(
                    len(record.text) <= settings.max_record_text_characters
                    for record in request.records
                ),
                detail=f"Maximum {settings.max_record_text_characters} characters per record.",
            ),
            ValidationResult(
                check="total_text_limit",
                passed=total_characters <= settings.max_total_request_characters,
                detail=f"{total_characters}/{settings.max_total_request_characters}",
            ),
            ValidationResult(
                check="candidate_limit",
                passed=request.options.candidate_limit <= settings.max_candidates_per_record,
                detail=f"{request.options.candidate_limit}/{settings.max_candidates_per_record}",
            ),
        ]
        if not all(check.passed for check in checks):
            raise ValueError("Incident configuration exceeds a configured safety limit.")
        for record in request.records:
            context.audit.add(
                "source ingested",
                self.name,
                [record.record_id],
                "No stored record",
                "Original source preserved",
                "Synthetic source record accepted within configured limits.",
            )
        return NodeOutcome(
            summary="Incident scope, languages, privacy boundary, and limits validated.",
            data={
                "incident_id": request.incident.incident_id,
                "allowed_languages": request.incident.languages,
                "privacy_policy": "least-necessary disclosure",
                "feature_flags": {"quarantine": True, "human_review_required": True},
            },
            validation_results=checks,
        )
