from __future__ import annotations

import random
import statistics
from collections import defaultdict
from collections.abc import Awaitable, Callable
from time import perf_counter

from app.benchmark import BenchmarkRunner, generate_benchmark
from app.config import Settings
from app.evaluation.adaptive_router import compare_adaptive_router
from app.evaluation.risk_coverage import calculate_risk_coverage
from app.providers import build_provider
from app.schemas.models import (
    BenchmarkJobRequest,
    ConfidenceInterval,
    EvaluationResult,
    MultiSeedMetric,
    MultiSeedSummary,
)


def _bootstrap(values: list[float], *, iterations: int = 1_000) -> ConfidenceInterval:
    if not values:
        return ConfidenceInterval(lower=0, upper=0)
    rng = random.Random(904_221)
    means = sorted(statistics.fmean(rng.choice(values) for _ in values) for _ in range(iterations))
    lower = means[int(iterations * 0.025)]
    upper = means[min(iterations - 1, int(iterations * 0.975))]
    return ConfidenceInterval(lower=round(lower, 4), upper=round(upper, 4))


def _progress_adapter(
    callback: Callable[[int, int, str], Awaitable[None]] | None,
    offset: int,
    total_cases: int,
) -> Callable[[int, int, str], Awaitable[None]]:
    async def report(completed: int, total: int, stage: str) -> None:
        del total
        if callback is not None:
            await callback(offset + completed, total_cases, stage)

    return report


async def run_evaluation_suite(
    payload: BenchmarkJobRequest,
    settings: Settings,
    progress_callback: Callable[[int, int, str], Awaitable[None]] | None = None,
) -> EvaluationResult:
    started = perf_counter()
    runs = []
    datasets = []
    metric_values: dict[str, list[float]] = defaultdict(list)
    total_cases = 0
    model_calls = 0
    failures = 0
    completed_offset = 0
    for seed in payload.seeds:
        configuration = payload.configuration.model_copy(update={"seed": seed})
        dataset = generate_benchmark(configuration)
        datasets.append(dataset)
        provider = build_provider(payload.provider_mode, settings)
        runner = BenchmarkRunner(settings=settings, provider=provider)
        seed_offset = completed_offset
        case_total = len(dataset.ground_truth)
        all_cases = case_total * len(payload.seeds)

        try:
            run = await runner.run(
                dataset,
                mode=payload.provider_mode,
                candidate_k=payload.candidate_k,
                progress_callback=_progress_adapter(progress_callback, seed_offset, all_cases),
            )
        except Exception:
            failures += 1
            completed_offset += len(dataset.ground_truth)
            continue
        runs.append(run)
        completed_offset += len(dataset.ground_truth)
        total_cases += len(dataset.ground_truth)
        threadline = next(item for item in run.systems if item.system_id == "threadline")
        model_calls += int(threadline.operational.get("model_calls", 0))
        for metric in threadline.metrics:
            metric_values[metric.metric_id].append(metric.value)
    aggregates = [
        MultiSeedMetric(
            metric_id=metric_id,
            mean=round(statistics.fmean(values), 4),
            standard_deviation=round(statistics.pstdev(values), 4),
            minimum=round(min(values), 4),
            maximum=round(max(values), 4),
            confidence_interval=_bootstrap(values),
        )
        for metric_id, values in sorted(metric_values.items())
    ]
    summary = MultiSeedSummary(
        seeds=payload.seeds,
        metrics=aggregates,
        successful_runs=len(runs),
        failed_runs=failures,
        total_cases=total_cases,
        provider_mode=payload.provider_mode,
        configured_model=settings.openai_model if payload.provider_mode.value != "mock" else None,
        model_calls=model_calls,
        duration_ms=round((perf_counter() - started) * 1000, 3),
    )
    risk = []
    adaptive = None
    if runs:
        first_threadline = next(item for item in runs[0].systems if item.system_id == "threadline")
        if payload.include_risk_coverage:
            risk = calculate_risk_coverage(datasets[0].ground_truth, first_threadline.outputs)
        if payload.include_adaptive_router:
            adaptive = await compare_adaptive_router(
                datasets[0],
                first_threadline.outputs,
                mode=payload.provider_mode,
                candidate_k=payload.candidate_k,
                settings=settings,
                provider=build_provider(payload.provider_mode, settings),
            )
    return EvaluationResult(
        runs=runs, multi_seed=summary, risk_coverage=risk, adaptive_router=adaptive
    )
