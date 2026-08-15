from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from app.baselines.fuzzy_matcher import run_fuzzy
from app.baselines.single_call import build_input_manifest, run_single_call
from app.config import Settings
from app.providers.base import ModelProvider
from app.schemas.models import AnalyzeRequest, BaselineRunResponse, Classification, SystemOutput
from app.workflow.orchestrator import WorkflowOrchestrator


class BaselineRunner:
    def __init__(self, *, settings: Settings, provider: ModelProvider) -> None:  # type: ignore[type-arg]
        self.settings = settings
        self.provider = provider

    async def run(self, request: AnalyzeRequest) -> BaselineRunResponse:
        input_manifest = build_input_manifest(request)
        fuzzy = run_fuzzy(request)
        fuzzy.output["input_manifest"] = input_manifest
        generic = await run_single_call(request, self.provider, structured=False)
        structured = await run_single_call(request, self.provider, structured=True)
        started = perf_counter()
        workflow = await WorkflowOrchestrator(settings=self.settings, provider=self.provider).run(
            request
        )
        best = workflow.candidates[0] if workflow.candidates else None
        full = SystemOutput(
            system_id="threadline",
            system_name="Full THREADLINE workflow",
            evaluation_mode=(
                "Deterministic mock evaluation"
                if request.options.provider_mode.value == "mock"
                else "Real-provider evaluation"
            ),
            classification=best.classification_code
            if best
            else Classification.insufficient_evidence,
            candidate_record_ids=[best.record_a_id, best.record_b_id] if best else [],
            cited_evidence=[
                span for record in workflow.records for span in record.evidence_spans if span.valid
            ],
            output={
                "case_id": workflow.case_id,
                "workflow_run_id": workflow.workflow_run_id,
                "workflow_response": workflow.model_dump(mode="json"),
                "workflow_trace": [
                    item.model_dump(mode="json") for item in workflow.workflow_trace
                ],
                "workflow_trace_details": [
                    item.model_dump(mode="json") for item in workflow.workflow_trace_details
                ],
                "candidate": best.model_dump(mode="json") if best else None,
                "injection_resisted": all(
                    record.quarantined
                    for record in workflow.records
                    if record.detected_instructions
                ),
                "provider_mode": self.provider.mode,
                "provider_model": self.provider.model_name,
                "input_manifest": input_manifest,
                "evaluation_warning": (
                    "Deterministic mock replay - not model performance."
                    if self.provider.mode == "mock"
                    else "Measured provider evaluation."
                ),
            },
            duration_ms=round((perf_counter() - started) * 1000, 3),
            model_calls=int(workflow.operational.get("model_calls", 0)),
            retries=int(workflow.operational.get("retries", 0)),
        )
        return BaselineRunResponse(
            run_id=f"BASELINE-{uuid4()}", systems=[fuzzy, generic, structured, full]
        )
