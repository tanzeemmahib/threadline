import asyncio

from app.config import Settings
from app.providers.base import ModelProvider, ProviderFailure
from app.providers.mock_provider import MockProvider
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.schemas.models import ProviderMode

_provider_semaphores: dict[int, asyncio.Semaphore] = {}


def _semaphore(limit: int) -> asyncio.Semaphore:
    safe_limit = max(1, limit)
    if safe_limit not in _provider_semaphores:
        _provider_semaphores[safe_limit] = asyncio.Semaphore(safe_limit)
    return _provider_semaphores[safe_limit]


def build_provider(mode: ProviderMode, settings: Settings) -> ModelProvider:  # type: ignore[type-arg]
    if mode == ProviderMode.mock:
        return MockProvider()
    if not settings.openai_api_key:
        raise ProviderFailure(
            "PROVIDER_CREDENTIALS_MISSING",
            "Connected-provider mode requires LLM_API_KEY (legacy THREADLINE_OPENAI_API_KEY is also supported).",
        )
    return OpenAICompatibleProvider(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        temperature=settings.llm_temperature,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        semaphore=_semaphore(settings.llm_max_concurrent_calls),
    )
