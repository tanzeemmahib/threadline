from datetime import UTC, datetime

from fastapi import APIRouter, Request

from app.providers import build_provider
from app.schemas.models import AnalyzeRequest, AnalyzeResponse, ProviderMode
from app.services.evidence_contracts import build_release_view
from app.services.replay import build_replay_manifest
from app.workflow import WorkflowOrchestrator

router = APIRouter(prefix="/api/v1", tags=["analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest, request: Request) -> AnalyzeResponse:
    settings = request.app.state.settings
    repository = request.app.state.repository
    provider = build_provider(payload.options.provider_mode, settings)
    internal_response = await WorkflowOrchestrator(settings=settings, provider=provider).run(payload)
    if internal_response.mode == ProviderMode.mock:
        stored_input = repository.get("analysis_inputs", internal_response.workflow_run_id)
        stored_response = repository.get("workflow_runs", internal_response.workflow_run_id)
        if stored_input is not None and stored_response is not None:
            previous_request = AnalyzeRequest.model_validate(stored_input)
            if previous_request.model_dump(mode="json") == payload.model_dump(mode="json"):
                refreshed = repository.refresh_workflow_audit(
                    internal_response.workflow_run_id
                )
                if refreshed is not None:
                    safe_response = build_release_view(refreshed)
                    repository.put(
                        "workflow_runs", safe_response.workflow_run_id, safe_response
                    )
                    return repository.refresh_workflow_audit(
                        safe_response.workflow_run_id
                    ) or safe_response
    response = build_release_view(internal_response)
    response.replay_manifest = build_replay_manifest(payload, response)
    repository.persist_analysis_bundle(
        request=payload,
        response=response,
        result={
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
