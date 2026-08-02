from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from app.benchmark import AblationRunner, BenchmarkRunner, generate_benchmark
from app.evaluation import run_evaluation_suite
from app.providers import build_provider
from app.schemas.models import (
    AblationRunRequest,
    BenchmarkJobRequest,
    JobKind,
    JobStatus,
    StoredResult,
    TrialRunRequest,
)
from app.services.jobs import JobManager, ProgressCallback
from app.trials import TrialRunner, create_preview, get_trial_case

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _store_result(
    request: Request, result_id: str, result_type: str, provider_mode: str, payload: Any
) -> None:
    serialized = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    request.app.state.repository.put(
        "results",
        result_id,
        StoredResult(
            result_id=result_id,
            result_type=result_type,
            created_at=datetime.now(UTC),
            provider_mode=provider_mode,
            payload=serialized,
        ),
    )


@router.post("/benchmark", response_model=JobStatus)
async def create_benchmark_job(payload: BenchmarkJobRequest, request: Request) -> JobStatus:
    if payload.configuration.identities > request.app.state.settings.max_benchmark_identities:
        raise ValueError("Benchmark identity count exceeds configured maximum")

    async def work(progress: ProgressCallback) -> tuple[str, Any]:
        result = await run_evaluation_suite(payload, request.app.state.settings, progress)
        result_id = f"RESULT-{uuid4()}"
        _store_result(request, result_id, "benchmark_suite", payload.provider_mode.value, result)
        return result_id, result

    estimated = payload.configuration.identities * len(payload.seeds)
    manager: JobManager = request.app.state.job_manager
    return manager.submit(JobKind.benchmark, work, total_cases=estimated)


@router.post("/ablation", response_model=JobStatus)
async def create_ablation_job(payload: AblationRunRequest, request: Request) -> JobStatus:
    async def work(progress: ProgressCallback) -> tuple[str, Any]:
        await progress(0, len(payload.disabled_nodes) + 1, "generating_dataset")
        dataset = generate_benchmark(payload.configuration)
        provider = build_provider(payload.provider_mode, request.app.state.settings)
        result = await AblationRunner(
            BenchmarkRunner(settings=request.app.state.settings, provider=provider)
        ).run(dataset, mode=payload.provider_mode, selected_nodes=payload.disabled_nodes)
        await progress(
            len(payload.disabled_nodes) + 1, len(payload.disabled_nodes) + 1, "persisting"
        )
        result_id = f"RESULT-{uuid4()}"
        _store_result(request, result_id, "ablation", payload.provider_mode.value, result)
        return result_id, result

    manager: JobManager = request.app.state.job_manager
    return manager.submit(JobKind.ablation, work, total_cases=len(payload.disabled_nodes) + 1)


@router.post("/trial", response_model=JobStatus)
async def create_trial_job(payload: TrialRunRequest, request: Request) -> JobStatus:
    async def work(progress: ProgressCallback) -> tuple[str, Any]:
        await progress(0, 1, "mutating_records")
        preview = create_preview(
            get_trial_case(payload.case_id),
            payload.mutation_types,
            payload.seed,
            payload.provider_mode,
        )
        provider = build_provider(payload.provider_mode, request.app.state.settings)
        result = await TrialRunner(settings=request.app.state.settings, provider=provider).run(
            preview
        )
        request.app.state.repository.put("trial_previews", preview.trial_id, preview)
        request.app.state.repository.put("trial_runs", result.trial_run_id, result)
        _store_result(request, result.result_id, "trial", payload.provider_mode.value, result)
        await progress(1, 1, "persisting")
        return result.result_id, result

    manager: JobManager = request.app.state.job_manager
    return manager.submit(JobKind.trial, work, total_cases=1)


@router.get("/{job_id}", response_model=JobStatus)
async def get_job(job_id: str, request: Request) -> JobStatus:
    manager: JobManager = request.app.state.job_manager
    status = manager.get(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return status


@router.post("/{job_id}/cancel", response_model=JobStatus)
async def cancel_job(job_id: str, request: Request) -> JobStatus:
    manager: JobManager = request.app.state.job_manager
    status = manager.cancel(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return status
