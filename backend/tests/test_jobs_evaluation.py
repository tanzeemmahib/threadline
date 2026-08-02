from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.schemas.models import JobKind
from app.services.jobs import JobManager
from app.services.storage import SQLiteRepository


def _benchmark_job_payload() -> dict[str, object]:
    return {
        "configuration": {"seed": 104, "identities": 2, "records_per_identity": 2},
        "seeds": [104],
        "provider_mode": "mock",
        "candidate_k": 3,
        "include_risk_coverage": True,
        "include_adaptive_router": False,
    }


def test_benchmark_job_persists_progress_and_result(client: TestClient) -> None:
    created = client.post("/api/v1/jobs/benchmark", json=_benchmark_job_payload())
    assert created.status_code == 200
    job_id = created.json()["job_id"]
    status = created.json()
    for _ in range(100):
        status = client.get(f"/api/v1/jobs/{job_id}").json()
        if status["state"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.02)
    assert status["state"] == "completed"
    assert status["progress"] == 1
    assert status["result_id"]
    stored = client.get(f"/api/v1/results/{status['result_id']}")
    assert stored.status_code == 200
    payload = stored.json()["payload"]
    assert payload["multi_seed"]["seeds"] == [104]
    assert len(payload["risk_coverage"]) == 3


@pytest.mark.asyncio
async def test_queued_or_running_job_can_be_cancelled(tmp_path: Path) -> None:
    manager = JobManager(SQLiteRepository(str(tmp_path / "jobs.db")))
    release = asyncio.Event()

    async def work(progress: object) -> tuple[str, object]:
        del progress
        await release.wait()
        return "RESULT-NEVER", {}

    created = manager.submit(JobKind.benchmark, work, total_cases=5)  # type: ignore[arg-type]
    await asyncio.sleep(0)
    cancelled = manager.cancel(created.job_id)
    assert cancelled is not None
    assert cancelled.state == "cancelled"
    assert cancelled.retryable is True
