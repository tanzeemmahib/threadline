from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import uuid4

from app.config import Settings
from app.providers.base import ModelProvider
from app.schemas.models import (
    AnalysisSummary,
    AnalyzeRequest,
    AnalyzeResponse,
    Classification,
    NormalizedRecord,
    ValidationResult,
    WorkflowTrace,
    WorkflowTraceDetail,
)
from app.services.audit import AuditBuilder
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext
from app.workflow.registry import disableable_node_ids, workflow_nodes


class NodeExecutionError(RuntimeError):
    def __init__(self, node_id: str, message: str) -> None:
        super().__init__(message)
        self.node_id = node_id


class WorkflowOrchestrator:
    def __init__(self, *, settings: Settings, provider: ModelProvider) -> None:  # type: ignore[type-arg]
        self.settings = settings
        self.provider = provider

    async def run(self, request: AnalyzeRequest) -> AnalyzeResponse:
        unknown_disabled = set(request.options.disabled_nodes) - disableable_node_ids()
        if unknown_disabled:
            raise ValueError(f"Nodes cannot be disabled: {sorted(unknown_disabled)}")
        context = WorkflowContext(
            request=request,
            settings=self.settings,
            provider=self.provider,
            audit=AuditBuilder(mock_mode=request.options.provider_mode.value == "mock"),
        )
        nodes = workflow_nodes()
        compact: list[WorkflowTrace] = []
        details: list[WorkflowTraceDetail] = []
        mock_base = datetime(2026, 4, 18, 22, 2, tzinfo=UTC)
        for index, node in enumerate(nodes):
            started = (
                mock_base + timedelta(seconds=index) if context.mock_mode else datetime.now(UTC)
            )
            timer = perf_counter()
            before = self._state_summary(context)
            status = "completed"
            try:
                if node.node_id in context.disabled_nodes:
                    status = "skipped"
                    outcome = self._skip_node(node, context)
                else:
                    outcome = await node.run(context)
            except Exception as exc:
                raise NodeExecutionError(node.node_id, str(exc)) from exc
            completed = (
                mock_base + timedelta(seconds=index + 1) if context.mock_mode else datetime.now(UTC)
            )
            duration = None if context.mock_mode else round((perf_counter() - timer) * 1000, 3)
            after = self._state_summary(context)
            provider_metadata = outcome.provider_metadata
            model_names = {item.model for item in provider_metadata if item.model}
            template_ids = {item.prompt_template_id for item in provider_metadata}
            template_versions = {item.prompt_template_version for item in provider_metadata}
            details.append(
                WorkflowTraceDetail(
                    node_id=node.node_id,
                    node_version=node.version,
                    node_name=node.name,
                    category=node.category,
                    status=status,
                    uses_llm=node.uses_llm,
                    requires_human_input=node.requires_human_input,
                    started_at=started,
                    completed_at=completed,
                    duration_ms=duration,
                    provider=self.provider.mode if node.uses_llm else "deterministic",
                    model=", ".join(sorted(model_names)) or None,
                    prompt_template_id=", ".join(sorted(template_ids)) or None,
                    prompt_template_version=", ".join(sorted(template_versions)) or None,
                    input_record_ids=[record.record_id for record in request.records],
                    input_schema=node.input_schema,
                    structured_input={
                        "state": before,
                        "record_count": len(context.records),
                        "candidate_count": len(context.candidates),
                    },
                    structured_output=outcome.data,
                    output_schema=node.output_schema,
                    validation_results=outcome.validation_results,
                    deterministic_checks=list(node.constraints),
                    evidence_span_ids=outcome.evidence_span_ids,
                    warnings=outcome.warnings,
                    failure_conditions=[node.failure_condition],
                    abstention_reason=outcome.abstention_reason,
                    token_usage=sum(item.token_usage or 0 for item in provider_metadata) or None,
                    estimated_cost=None,
                    next_node=nodes[index + 1].node_id if index + 1 < len(nodes) else None,
                    human_review_requirement="Required"
                    if node.requires_human_input
                    else "Not required at this stage",
                    before_state=before,
                    after_state=after,
                )
            )
            compact.append(
                WorkflowTrace(
                    node_id=node.node_id,
                    order=node.order,
                    name=node.name,
                    short_name=node.short_name,
                    category=node.category,
                    input=node.input_schema,
                    purpose=node.purpose,
                    output=outcome.summary,
                    method="Configured LLM"
                    if node.uses_llm
                    else "Deterministic rules"
                    if not node.requires_human_input
                    else "Authorized human procedure",
                    failure_condition=node.failure_condition,
                    human_input_requirement="Required"
                    if node.requires_human_input
                    else "None at this stage.",
                    constraints=list(node.constraints),
                    downstream_consumer=nodes[index + 1].name
                    if index + 1 < len(nodes)
                    else "Authorized external procedure",
                    demo_duration_ms=None,
                )
            )
        status = (
            "insufficient_evidence"
            if not context.candidates
            or all(
                candidate.classification_code == Classification.insufficient_evidence
                for candidate in context.candidates
            )
            else "review_required"
        )
        fingerprint = hashlib.sha256(
            json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()[:12]
        case_id = f"CASE-{fingerprint.upper()}"
        workflow_run_id = (
            f"RUN-MOCK-{fingerprint.upper()}" if context.mock_mode else f"RUN-{uuid4()}"
        )
        summary = AnalysisSummary(
            records_processed=len(context.records),
            languages_detected=len({record.language for record in context.records}),
            candidate_connections=len(context.candidates),
            awaiting_human_review=len(context.candidates),
            hard_conflicts=sum(
                conflict.severity == "hard"
                for candidate in context.candidates
                for conflict in candidate.conflicts
            ),
            quarantined_instructions=sum(
                len(record.detected_instructions) for record in context.records
            ),
        )
        return AnalyzeResponse(
            case_id=case_id,
            workflow_run_id=workflow_run_id,
            status=status,
            mode=request.options.provider_mode,
            summary=summary,
            records=context.records,
            candidates=context.candidates,
            workflow_trace=compact if request.options.include_workflow_trace else [],
            workflow_trace_details=details if request.options.include_workflow_trace else [],
            audit_events=context.audit.events,
            operational={"model_calls": context.model_calls, "retries": context.retries},
        )

    @staticmethod
    def _state_summary(context: WorkflowContext) -> str:
        return (
            f"records={len(context.records)}; candidates={len(context.candidates)}; "
            f"audit_events={len(context.audit.events)}"
        )

    @staticmethod
    def _skip_node(node: WorkflowNode, context: WorkflowContext) -> NodeOutcome:
        if node.node_id == "quarantine":
            for source in context.request.records:
                context.records.append(
                    NormalizedRecord(
                        record_id=source.record_id,
                        source_type=source.source_type,
                        language=source.language,
                        text=source.text,
                        timestamp=source.timestamp,
                        display_name=source.display_name or source.record_id,
                        safe_text=source.text,
                        translated_text=source.translated_text,
                        source_reliability_metadata=source.source_reliability_metadata,
                        reliability_note=source.source_reliability_metadata,
                    )
                )
        elif node.node_id == "prosecutor":
            for candidate in context.candidates:
                had_hard_conflict = any(
                    conflict.severity == "hard" for conflict in candidate.conflicts
                )
                candidate.conflicts = []
                if had_hard_conflict:
                    candidate.classification_code = Classification.possible_candidate
                    candidate.classification = "Possible candidate"
                    candidate.label = "Possible candidate connection"
        elif node.node_id == "rivals":
            for candidate in context.candidates:
                candidate.rivals = []
                candidate.abstention_reasons = [
                    reason
                    for reason in candidate.abstention_reasons
                    if "rival" not in reason.lower()
                ]
        elif node.node_id == "adjudicate":
            for candidate in context.candidates:
                candidate.adjudicator_agreement = False
        return NodeOutcome(
            summary=f"{node.name} disabled for controlled ablation.",
            data={"disabled": True, "node_id": node.node_id},
            validation_results=[
                ValidationResult(
                    check="controlled_ablation_skip",
                    passed=True,
                    detail=f"{node.node_id} was explicitly disabled.",
                )
            ],
            warnings=[
                "This run is an ablation and does not represent the full THREADLINE workflow."
            ],
        )
