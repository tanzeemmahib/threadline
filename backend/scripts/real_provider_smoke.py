from __future__ import annotations

import asyncio

from app.config import get_settings
from app.demo import demo_request
from app.providers import build_provider
from app.schemas.models import ProviderMode
from app.workflow import WorkflowOrchestrator


async def main() -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        raise SystemExit("Set LLM_API_KEY before running the opt-in real-provider smoke test.")
    request = demo_request().model_copy(deep=True)
    request.options.provider_mode = ProviderMode.openai_compatible
    provider = build_provider(ProviderMode.openai_compatible, settings)
    result = await WorkflowOrchestrator(settings=settings, provider=provider).run(request)
    print(
        {
            "workflow_run_id": result.workflow_run_id,
            "status": result.status,
            "provider_mode": result.mode,
            "configured_model": settings.openai_model,
            "candidate_count": len(result.candidates),
            "model_calls": result.operational.get("model_calls", 0),
            "safety": result.human_review_requirement,
        }
    )


if __name__ == "__main__":
    asyncio.run(main())
