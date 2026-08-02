from __future__ import annotations

import asyncio
import json
from time import perf_counter
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.providers.base import ModelProvider, ProviderFailure
from app.schemas.models import ProviderMetadata, ProviderResult

ModelT = TypeVar("ModelT", bound=BaseModel)


class OpenAICompatibleProvider(ModelProvider[ModelT]):
    mode = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 30,
        temperature: float = 0,
        max_retries: int = 1,
        semaphore: asyncio.Semaphore | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.max_retries = max(0, max_retries)
        self._semaphore = semaphore or asyncio.Semaphore(1)
        self._client = client

    async def generate_structured(
        self,
        *,
        template_id: str,
        template_version: str,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ModelT],
        mock_payload: dict[str, Any],
    ) -> ProviderResult:
        del mock_payload
        started = perf_counter()
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            correction = ""
            if last_error is not None:
                correction = (
                    "\nThe previous response failed validation. Return only corrected JSON. "
                    f"Validation error: {last_error}"
                )
            try:
                data = await self._request(system_prompt, user_prompt + correction)
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                output = response_model.model_validate(parsed)
                usage = data.get("usage", {}).get("total_tokens")
                return ProviderResult(
                    output=output,
                    metadata=ProviderMetadata(
                        provider=self.mode,
                        model=self.model_name,
                        prompt_template_id=template_id,
                        prompt_template_version=template_version,
                        attempts=attempt,
                        duration_ms=round((perf_counter() - started) * 1000, 3),
                        token_usage=int(usage) if usage is not None else None,
                    ),
                )
            except (json.JSONDecodeError, ValidationError, KeyError, IndexError, TypeError) as exc:
                last_error = exc
                continue
            except httpx.TimeoutException as exc:
                raise ProviderFailure(
                    "PROVIDER_TIMEOUT", "Model provider timed out.", retryable=True
                ) from exc
            except httpx.HTTPError as exc:
                raise ProviderFailure(
                    "PROVIDER_REQUEST_FAILURE", "Model provider request failed.", retryable=True
                ) from exc
        attempt_label = "two" if self.max_retries + 1 == 2 else str(self.max_retries + 1)
        raise ProviderFailure(
            "MODEL_RESPONSE_SCHEMA_FAILURE",
            f"Model response failed schema validation after {attempt_label} attempts: {last_error}",
        )

    async def _request(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": self.temperature,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        async with self._semaphore:
            if self._client is not None:
                response = await self._client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                return dict(response.json())
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions", json=payload, headers=headers
                )
                response.raise_for_status()
                return dict(response.json())
