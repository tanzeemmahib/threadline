from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from app.schemas.models import (
    AnalyzeResponse,
    AuditEvent,
    EvidenceContract,
    ReleaseState,
    ReviewCreate,
    ReviewOutcome,
    ReviewReceipt,
)

router = APIRouter(prefix="/api/v1", tags=["reviews"])


@router.post("/reviews", response_model=ReviewReceipt)
async def create_review(payload: ReviewCreate, request: Request) -> ReviewReceipt:
    now = datetime.now(UTC)
    review_id = f"REVIEW-{uuid4()}"
    event_id = f"AUDIT-{uuid4()}"
    repository = request.app.state.repository
    proof_scoped = bool(payload.workflow_run_id and payload.contract_id)
    if bool(payload.workflow_run_id) != bool(payload.contract_id):
        raise HTTPException(
            status_code=422,
            detail="workflow_run_id and contract_id are required together",
        )
    contract_ids = [payload.contract_id] if proof_scoped and payload.contract_id else []
    response = None
    if proof_scoped and payload.contract_id and payload.workflow_run_id:
        response_value = repository.get("workflow_runs", payload.workflow_run_id)
        if response_value is None:
            raise HTTPException(status_code=404, detail="Workflow run not found")
        response = AnalyzeResponse.model_validate(response_value)
        contract_value = repository.get("evidence_contracts", payload.contract_id)
        if contract_value is None:
            raise HTTPException(status_code=404, detail="Evidence contract not found")
        contract = EvidenceContract.model_validate(contract_value)
        if contract.case_id != payload.case_id or (
            payload.candidate_id and contract.candidate_id != payload.candidate_id
        ):
            raise HTTPException(status_code=409, detail="Review scope does not match contract")
        if response.case_id != payload.case_id or payload.contract_id not in {
            item.contract_id for item in response.evidence_contracts
        }:
            raise HTTPException(
                status_code=409,
                detail="Review contract does not belong to workflow run",
            )
    in_progress = payload.outcome in {
        ReviewOutcome.additional_evidence_required,
        ReviewOutcome.candidate_thread_remains_plausible,
        ReviewOutcome.escalate_to_authorized_case_process,
        ReviewOutcome.request_more_information,
        ReviewOutcome.escalate_for_authorized_review,
    }
    release_state = (
        ReleaseState(
            state=(
                "authorized_review_in_progress"
                if in_progress
                else "authorized_disposition_recorded"
            ),
            contract_ids=contract_ids,
            review_id=review_id,
            reviewer_id=payload.reviewer_id,
            disposition=None if in_progress else payload.outcome.value,
        )
        if proof_scoped
        else ReleaseState(state="draft")
    )
    chain_event = None
    if proof_scoped and payload.workflow_run_id and response is not None:
        chain_event = repository.append_chain_event(
            workflow_run_id=payload.workflow_run_id,
            event_type=(
                "human_review_requested" if in_progress else "authorized_disposition_recorded"
            ),
            payload={
                "review_id": review_id,
                "outcome": payload.outcome.value,
                "rationale": payload.rationale or payload.notes,
                "remaining_uncertainty": payload.remaining_uncertainty,
                "requested_evidence": payload.requested_evidence,
            },
            created_at=now,
            actor_type="human",
            actor_id=payload.reviewer_id,
            contract_id=payload.contract_id,
            candidate_id=payload.candidate_id,
            case_id=payload.case_id,
            referenced_artifact_ids=payload.referenced_artifact_ids,
        )
        response.release_state = release_state
        repository.put("workflow_runs", payload.workflow_run_id, response)
        repository.refresh_workflow_audit(payload.workflow_run_id)
    receipt = ReviewReceipt(
        review_id=review_id,
        case_id=payload.case_id,
        candidate_id=payload.candidate_id,
        created_at=now,
        outcome=payload.outcome,
        audit_event_id=event_id,
        audit_chain_event_id=chain_event.event_id if chain_event else None,
        release_state=release_state,
    )
    repository.put(
        "reviews",
        review_id,
        {
            **payload.model_dump(mode="json"),
            **receipt.model_dump(mode="json"),
            "proof_scope": "workflow_contract" if proof_scoped else "legacy_unscoped",
        },
    )
    event = AuditEvent(
        event_id=event_id,
        timestamp=now,
        event_type="reviewer decision saved",
        actor=payload.reviewer_id,
        action=payload.outcome.value,
        detail=payload.rationale or payload.notes or "Authorized reviewer outcome recorded.",
        workflow_version=request.app.state.settings.app_version,
        prompt_version=None,
        source_record_ids=[],
        before="review_required",
        after=payload.outcome.value,
        before_value="review_required",
        after_value=payload.outcome.value,
        reason=payload.rationale or payload.notes or "Authorized reviewer action",
        machine_or_human="human",
        origin="human",
        synthetic_mode=True,
    )
    repository.put_audit(payload.case_id, event_id, event)
    return receipt
