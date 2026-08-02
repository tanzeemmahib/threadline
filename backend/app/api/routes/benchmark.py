from datetime import UTC, datetime

from fastapi import APIRouter, Request

from app.benchmark import BenchmarkRunner, generate_benchmark
from app.providers import build_provider
from app.schemas.models import (
    BenchmarkDataset,
    BenchmarkGenerateRequest,
    BenchmarkRunRequest,
    BenchmarkRunResponse,
)

router = APIRouter(prefix="/api/v1", tags=["evaluation"])


@router.post("/benchmark/generate", response_model=BenchmarkDataset)
async def generate(payload: BenchmarkGenerateRequest, request: Request) -> BenchmarkDataset:
    settings = request.app.state.settings
    repository = request.app.state.repository
    if payload.configuration.identities > settings.max_benchmark_identities:
        raise ValueError(
            f"identities exceeds MAX_BENCHMARK_IDENTITIES={settings.max_benchmark_identities}"
        )
    dataset = generate_benchmark(payload.configuration)
    repository.put("benchmark_configurations", dataset.benchmark_id, payload.configuration)
    repository.put("benchmark_datasets", dataset.benchmark_id, dataset)
    return dataset


@router.post("/benchmark/run", response_model=BenchmarkRunResponse)
async def run_benchmark(payload: BenchmarkRunRequest, request: Request) -> BenchmarkRunResponse:
    settings = request.app.state.settings
    repository = request.app.state.repository
    dataset = payload.dataset or generate_benchmark(payload.configuration)  # type: ignore[arg-type]
    if dataset.configuration.identities > settings.max_benchmark_identities:
        raise ValueError(
            f"identities exceeds MAX_BENCHMARK_IDENTITIES={settings.max_benchmark_identities}"
        )
    provider = build_provider(payload.provider_mode, settings)
    response = await BenchmarkRunner(settings=settings, provider=provider).run(
        dataset, mode=payload.provider_mode, candidate_k=payload.candidate_k
    )
    repository.put("benchmark_results", response.benchmark_run_id, response)
    repository.put(
        "results",
        response.benchmark_run_id,
        {
            "result_id": response.benchmark_run_id,
            "result_type": "benchmark",
            "created_at": datetime.now(UTC).isoformat(),
            "provider_mode": payload.provider_mode.value,
            "payload": response.model_dump(mode="json"),
        },
    )
    return response
