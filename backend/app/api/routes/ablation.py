from datetime import UTC, datetime

from fastapi import APIRouter, Request

from app.benchmark import AblationRunner, BenchmarkRunner, generate_benchmark
from app.providers import build_provider
from app.schemas.models import AblationRunRequest, AblationRunResponse

router = APIRouter(prefix="/api/v1", tags=["evaluation"])


@router.post("/ablation/run", response_model=AblationRunResponse)
async def run_ablation(payload: AblationRunRequest, request: Request) -> AblationRunResponse:
    settings = request.app.state.settings
    repository = request.app.state.repository
    if payload.configuration.identities > settings.max_benchmark_identities:
        raise ValueError(
            f"identities exceeds MAX_BENCHMARK_IDENTITIES={settings.max_benchmark_identities}"
        )
    dataset = generate_benchmark(payload.configuration)
    provider = build_provider(payload.provider_mode, settings)
    benchmark_runner = BenchmarkRunner(settings=settings, provider=provider)
    response = await AblationRunner(benchmark_runner).run(
        dataset, mode=payload.provider_mode, selected_nodes=payload.disabled_nodes
    )
    repository.put("ablation_results", response.ablation_run_id, response)
    repository.put(
        "results",
        response.ablation_run_id,
        {
            "result_id": response.ablation_run_id,
            "result_type": "ablation",
            "created_at": datetime.now(UTC).isoformat(),
            "provider_mode": payload.provider_mode.value,
            "payload": response.model_dump(mode="json"),
        },
    )
    return response
