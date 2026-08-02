from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Request

from app.schemas.models import AuditEvent, ReviewCreate, ReviewReceipt

router = APIRouter(prefix="/api/v1", tags=["reviews"])


@router.post("/reviews", response_model=ReviewReceipt)
async def create_review(payload: ReviewCreate, request: Request) -> ReviewReceipt:
    now = datetime.now(UTC)
    review_id = f"REVIEW-{uuid4()}"
    event_id = f"AUDIT-{uuid4()}"
    receipt = ReviewReceipt(
        review_id=review_id,
        case_id=payload.case_id,
        created_at=now,
        outcome=payload.outcome,
        audit_event_id=event_id,
    )
    repository = request.app.state.repository
    repository.put(
        "reviews",
        review_id,
        {**payload.model_dump(mode="json"), **receipt.model_dump(mode="json")},
    )
    event = AuditEvent(
        event_id=event_id,
        timestamp=now,
        event_type="reviewer decision saved",
        actor=payload.reviewer_id,
        action=payload.outcome.value,
        detail=payload.notes or "Authorized reviewer outcome recorded.",
        workflow_version=request.app.state.settings.app_version,
        prompt_version=None,
        source_record_ids=[],
        before="review_required",
        after=payload.outcome.value,
        before_value="review_required",
        after_value=payload.outcome.value,
        reason=payload.notes or "Authorized reviewer action",
        machine_or_human="human",
        origin="human",
        synthetic_mode=True,
    )
    repository.put_audit(payload.case_id, event_id, event)
    return receipt
