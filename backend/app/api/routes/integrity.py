from typing import cast

from fastapi import APIRouter, HTTPException, Request

from app.schemas.models import AuditChainEvent, AuditIntegrityResult, AuditTrailResponse
from app.services.audit_chain import verify_audit_chain

router = APIRouter(prefix="/api/v1", tags=["integrity"])


def _events(workflow_run_id: str, request: Request) -> list[AuditChainEvent]:
    events = request.app.state.repository.audit_chain(workflow_run_id)
    if not events and request.app.state.repository.get("workflow_runs", workflow_run_id) is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return cast(list[AuditChainEvent], events)


def _verifier_error(workflow_run_id: str) -> AuditIntegrityResult:
    return AuditIntegrityResult(
        workflow_run_id=workflow_run_id,
        status="verifier_error",
        valid=False,
        verified_event_count=0,
    )


@router.get("/runs/{workflow_run_id}/audit", response_model=AuditTrailResponse)
async def get_run_audit(workflow_run_id: str, request: Request) -> AuditTrailResponse:
    try:
        events = _events(workflow_run_id, request)
        integrity = verify_audit_chain(workflow_run_id, events)
    except HTTPException:
        raise
    except Exception:
        events = []
        integrity = _verifier_error(workflow_run_id)
    return AuditTrailResponse(
        workflow_run_id=workflow_run_id,
        events=events,
        integrity=integrity,
    )


@router.get("/runs/{workflow_run_id}/audit/verify", response_model=AuditIntegrityResult)
async def verify_run_audit(workflow_run_id: str, request: Request) -> AuditIntegrityResult:
    try:
        return verify_audit_chain(workflow_run_id, _events(workflow_run_id, request))
    except HTTPException:
        raise
    except Exception:
        return _verifier_error(workflow_run_id)
