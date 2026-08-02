from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.baselines import BaselineRunner
from app.config import Settings
from app.providers.base import ModelProvider
from app.schemas.models import TrialPreview, TrialRunResponse
from app.trials.divergence import find_first_divergence


class TrialRunner:
    def __init__(self, *, settings: Settings, provider: ModelProvider) -> None:  # type: ignore[type-arg]
        self.settings = settings
        self.provider = provider

    async def run(self, preview: TrialPreview) -> TrialRunResponse:
        comparison = await BaselineRunner(settings=self.settings, provider=self.provider).run(
            preview.mutated_request
        )
        full = next((item for item in comparison.systems if item.system_id == "threadline"), None)
        workflow_run_id = (
            str(full.output.get("workflow_run_id"))
            if full and full.output.get("workflow_run_id")
            else None
        )
        run_id = f"TRIAL-RUN-{uuid4()}"
        result_id = f"RESULT-{uuid4()}"
        return TrialRunResponse(
            trial_run_id=run_id,
            trial_id=preview.trial_id,
            result_id=result_id,
            case_id=preview.case_id,
            seed=preview.seed,
            provider_mode=preview.provider_mode,
            mutations=preview.mutations,
            systems=comparison.systems,
            divergence=find_first_divergence(
                comparison.systems,
                preview.ground_truth,
                [item.mutation_type for item in preview.mutations],
            ),
            workflow_run_id=workflow_run_id,
            ground_truth=preview.ground_truth,
            created_at=datetime.now(UTC),
        )
