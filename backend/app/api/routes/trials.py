from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.providers import build_provider
from app.schemas.models import (
    StoredResult,
    TrialCase,
    TrialCreateRequest,
    TrialPreview,
    TrialRerunRequest,
    TrialRunRequest,
    TrialRunResponse,
)
from app.trials import TrialRunner, create_preview, get_trial_case, trial_cases

router = APIRouter(prefix="/api/v1", tags=["trials"])


def _case_or_404(case_id: str) -> TrialCase:
    try:
        return get_trial_case(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Trial case not found") from exc


@router.get("/trials/cases", response_model=list[TrialCase])
async def list_trial_cases() -> list[TrialCase]:
    return [item.model_copy(deep=True) for item in trial_cases()]


@router.post("/trials/preview", response_model=TrialPreview)
async def preview_trial(payload: TrialCreateRequest, request: Request) -> TrialPreview:
    preview = create_preview(
        _case_or_404(payload.case_id), payload.mutation_types, payload.seed, payload.provider_mode
    )
    request.app.state.repository.put("trial_previews", preview.trial_id, preview)
    return preview


@router.post("/trials/run", response_model=TrialRunResponse)
async def run_trial(payload: TrialRunRequest, request: Request) -> TrialRunResponse:
    repository = request.app.state.repository
    stored_preview = (
        repository.get("trial_previews", payload.trial_id) if payload.trial_id else None
    )
    preview = (
        TrialPreview.model_validate(stored_preview)
        if stored_preview is not None
        else create_preview(
            _case_or_404(payload.case_id),
            payload.mutation_types,
            payload.seed,
            payload.provider_mode,
        )
    )
    provider = build_provider(preview.provider_mode, request.app.state.settings)
    result = await TrialRunner(settings=request.app.state.settings, provider=provider).run(preview)
    repository.put("trial_runs", result.trial_run_id, result)
    repository.put("trial_previews", preview.trial_id, preview)
    repository.put(
        "results",
        result.result_id,
        StoredResult(
            result_id=result.result_id,
            result_type="trial",
            created_at=result.created_at,
            provider_mode=result.provider_mode.value,
            payload=result.model_dump(mode="json"),
        ),
    )
    full = next((item for item in result.systems if item.system_id == "threadline"), None)
    if full and result.workflow_run_id:
        details = full.output.get("workflow_response")
        if details:
            repository.put("workflow_runs", result.workflow_run_id, details)
    return result


@router.get("/trials/{trial_run_id}", response_model=TrialRunResponse)
async def get_trial_run(trial_run_id: str, request: Request) -> TrialRunResponse:
    value = request.app.state.repository.get("trial_runs", trial_run_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Trial run not found")
    return TrialRunResponse.model_validate(value)


@router.post("/trials/{trial_run_id}/rerun", response_model=TrialRunResponse)
async def rerun_trial(
    trial_run_id: str, payload: TrialRerunRequest, request: Request
) -> TrialRunResponse:
    previous = await get_trial_run(trial_run_id, request)
    return await run_trial(
        TrialRunRequest(
            case_id=previous.case_id,
            mutation_types=[item.mutation_type for item in previous.mutations],
            seed=payload.seed if payload.seed is not None else previous.seed,
            provider_mode=payload.provider_mode or previous.provider_mode,
        ),
        request,
    )
