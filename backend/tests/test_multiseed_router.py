from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.evaluation import run_evaluation_suite
from app.schemas.models import BenchmarkConfig, BenchmarkJobRequest


@pytest.mark.asyncio
async def test_multi_seed_aggregate_and_bootstrap_are_reproducible(tmp_path: Path) -> None:
    settings = Settings(database_path=str(tmp_path / "db.sqlite"))
    request = BenchmarkJobRequest(
        configuration=BenchmarkConfig(seed=104, identities=2, records_per_identity=2),
        seeds=[104, 205],
        include_adaptive_router=False,
    )
    first = await run_evaluation_suite(request, settings)
    second = await run_evaluation_suite(request, settings)
    stable_ids = {"classification_accuracy", "false_link_rate", "correct_abstention_rate"}
    first_metrics = {
        item.metric_id: item.model_dump()
        for item in first.multi_seed.metrics
        if item.metric_id in stable_ids
    }
    second_metrics = {
        item.metric_id: item.model_dump()
        for item in second.multi_seed.metrics
        if item.metric_id in stable_ids
    }
    assert first_metrics == second_metrics
    assert all(
        item["confidence_interval"]["method"] == "fixed_seed_bootstrap"
        for item in first_metrics.values()
    )
    assert [point.policy for point in first.risk_coverage] == [
        "exploratory",
        "balanced",
        "conservative",
    ]


@pytest.mark.asyncio
async def test_adaptive_router_reports_actual_calls_and_safe_profiles(tmp_path: Path) -> None:
    settings = Settings(database_path=str(tmp_path / "db.sqlite"))
    request = BenchmarkJobRequest(
        configuration=BenchmarkConfig(seed=104, identities=2, records_per_identity=2),
        seeds=[104],
        include_adaptive_router=True,
    )
    result = await run_evaluation_suite(request, settings)
    comparison = result.adaptive_router
    assert comparison is not None
    assert comparison.full_model_calls >= 0
    assert comparison.adaptive_model_calls >= 0
    assert {item.profile for item in comparison.decisions} <= {
        "deterministic_only",
        "reduced",
        "full",
    }
    assert "does not autonomously determine identity" in comparison.safety_notice
