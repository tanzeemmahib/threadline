from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.schemas.models import AnalyzeResponse, AuditEvent

router = APIRouter(prefix="/api/v1", tags=["persistence"])


@router.get("/workflow-runs/{workflow_run_id}", response_model=AnalyzeResponse)
async def get_workflow_run(workflow_run_id: str, request: Request) -> AnalyzeResponse:
    value = request.app.state.repository.get("workflow_runs", workflow_run_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return AnalyzeResponse.model_validate(value)


@router.get("/cases/{case_id}/audit", response_model=list[AuditEvent])
async def get_case_audit(case_id: str, request: Request) -> list[AuditEvent]:
    return [
        AuditEvent.model_validate(item) for item in request.app.state.repository.case_audit(case_id)
    ]
