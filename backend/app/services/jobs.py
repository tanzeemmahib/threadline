from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.schemas.models import JobKind, JobState, JobStatus
from app.services.storage import Repository

ProgressCallback = Callable[[int, int, str], Awaitable[None]]
JobWork = Callable[[ProgressCallback], Awaitable[tuple[str, Any]]]


class JobManager:
    def __init__(self, repository: Repository, *, max_concurrent_jobs: int = 1) -> None:
        self.repository = repository
        self._semaphore = asyncio.Semaphore(max(1, max_concurrent_jobs))
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def submit(self, kind: JobKind, work: JobWork, *, total_cases: int = 0) -> JobStatus:
        now = datetime.now(UTC)
        status = JobStatus(
            job_id=f"JOB-{uuid4()}",
            kind=kind,
            state=JobState.queued,
            progress=0,
            total_cases=total_cases,
            stage="queued",
            created_at=now,
        )
        self._save(status)
        self._tasks[status.job_id] = asyncio.create_task(self._run(status.job_id, work))
        return status

    def get(self, job_id: str) -> JobStatus | None:
        value = self.repository.get("jobs", job_id)
        return None if value is None else JobStatus.model_validate(value)

    def cancel(self, job_id: str) -> JobStatus | None:
        status = self.get(job_id)
        if status is None:
            return None
        if status.state in {JobState.completed, JobState.failed, JobState.cancelled}:
            return status
        task = self._tasks.get(job_id)
        if task is not None:
            task.cancel()
        status.state = JobState.cancelled
        status.stage = "cancelled"
        status.completed_at = datetime.now(UTC)
        status.retryable = True
        self._save(status)
        return status

    async def _run(self, job_id: str, work: JobWork) -> None:
        status = self.get(job_id)
        if status is None:
            return
        try:
            async with self._semaphore:
                status = self.get(job_id) or status
                if status.state == JobState.cancelled:
                    return
                status.state = JobState.running
                status.stage = "starting"
                status.started_at = datetime.now(UTC)
                self._save(status)

                async def progress(completed: int, total: int, stage: str) -> None:
                    current = self.get(job_id)
                    if current is None or current.state == JobState.cancelled:
                        raise asyncio.CancelledError
                    current.completed_cases = max(0, completed)
                    current.total_cases = max(total, current.total_cases)
                    current.progress = min(1.0, completed / total) if total else 0
                    current.stage = stage
                    self._save(current)

                result_id, _ = await work(progress)
                current = self.get(job_id) or status
                if current.state != JobState.cancelled:
                    current.state = JobState.completed
                    current.progress = 1
                    current.completed_cases = current.total_cases
                    current.stage = "completed"
                    current.completed_at = datetime.now(UTC)
                    current.result_id = result_id
                    self._save(current)
        except asyncio.CancelledError:
            current = self.get(job_id) or status
            current.state = JobState.cancelled
            current.stage = "cancelled"
            current.completed_at = datetime.now(UTC)
            current.retryable = True
            self._save(current)
        except Exception as exc:
            current = self.get(job_id) or status
            current.state = JobState.failed
            current.stage = "failed"
            current.completed_at = datetime.now(UTC)
            current.error = str(exc)
            current.retryable = True
            self._save(current)
        finally:
            self._tasks.pop(job_id, None)

    def _save(self, status: JobStatus) -> None:
        self.repository.put("jobs", status.job_id, status)
