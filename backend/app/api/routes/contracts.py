from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request

from app.schemas.models import AnalyzeResponse, EvidenceContract

router = APIRouter(prefix="/api/v1", tags=["evidence-contracts"])


@router.get("/contracts/{contract_id}", response_model=EvidenceContract)
async def get_evidence_contract(contract_id: str, request: Request) -> EvidenceContract:
    value = request.app.state.repository.get("evidence_contracts", contract_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Evidence contract not found")
    return EvidenceContract.model_validate(value)


@router.post(
    "/runs/{workflow_run_id}/contracts/{contract_id}/export",
    response_model=EvidenceContract,
)
async def export_evidence_contract(
    workflow_run_id: str, contract_id: str, request: Request
) -> EvidenceContract:
    repository = request.app.state.repository
    run_value = repository.get("workflow_runs", workflow_run_id)
    if run_value is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    run = AnalyzeResponse.model_validate(run_value)
    if contract_id not in {item.contract_id for item in run.evidence_contracts}:
        raise HTTPException(status_code=409, detail="Contract does not belong to workflow run")
    value = repository.get("evidence_contracts", contract_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Evidence contract not found")
    contract = EvidenceContract.model_validate(value)
    repository.append_chain_event(
        workflow_run_id=workflow_run_id,
        event_type="certificate_exported",
        payload={"contract_id": contract_id, "format": "json"},
        created_at=datetime.now(UTC),
        contract_id=contract_id,
        candidate_id=contract.candidate_id,
    )
    repository.refresh_workflow_audit(workflow_run_id)
    return contract
