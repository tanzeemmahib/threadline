from fastapi import APIRouter, Request

from app.baselines import BaselineRunner
from app.providers import build_provider
from app.schemas.models import BaselineRunRequest, BaselineRunResponse

router = APIRouter(prefix="/api/v1", tags=["evaluation"])


@router.post("/baselines/run", response_model=BaselineRunResponse)
async def run_baselines(payload: BaselineRunRequest, request: Request) -> BaselineRunResponse:
    settings = request.app.state.settings
    provider = build_provider(payload.case.options.provider_mode, settings)
    response = await BaselineRunner(settings=settings, provider=provider).run(payload.case)
    repository = request.app.state.repository
    repository.put("baseline_runs", response.run_id, response)
    return response
