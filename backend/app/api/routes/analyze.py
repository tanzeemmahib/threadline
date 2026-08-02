from datetime import UTC, datetime

from fastapi import APIRouter, Request

from app.providers import build_provider
from app.schemas.models import AnalyzeRequest, AnalyzeResponse
from app.workflow import WorkflowOrchestrator

router = APIRouter(prefix="/api/v1", tags=["analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest, request: Request) -> AnalyzeResponse:
    settings = request.app.state.settings
    provider = build_provider(payload.options.provider_mode, settings)
    response = await WorkflowOrchestrator(settings=settings, provider=provider).run(payload)
    repository = request.app.state.repository
    repository.put("workflow_runs", response.workflow_run_id, response)
    repository.put(
        "results",
        response.workflow_run_id,
        {
            "result_id": response.workflow_run_id,
            "result_type": "analysis",
            "created_at": (
                response.workflow_trace_details[-1].completed_at.isoformat()
                if response.workflow_trace_details
                else datetime.now(UTC).isoformat()
            ),
            "provider_mode": response.mode.value,
            "payload": response.model_dump(mode="json"),
        },
    )
    for event in response.audit_events:
        repository.put_audit(response.case_id, event.event_id, event)
    return response
