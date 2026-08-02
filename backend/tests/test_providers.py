from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from app.providers.base import ProviderFailure
from app.providers.mock_provider import MockProvider
from app.providers.openai_compatible import OpenAICompatibleProvider


class ResponseModel(BaseModel):
    value: int


@pytest.mark.asyncio
async def test_mock_provider() -> None:
    result = await MockProvider().generate_structured(
        template_id="test",
        template_version="v1",
        system_prompt="system",
        user_prompt="user",
        response_model=ResponseModel,
        mock_payload={"value": 2},
    )
    assert result.output.value == 2
    assert result.metadata.attempts == 1


@pytest.mark.asyncio
async def test_schema_failure_retries_once() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = {"value": "bad"} if calls == 1 else {"value": 3}
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(content)}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="https://example.test/v1", api_key="secret", model="test", client=client
        )
        result = await provider.generate_structured(
            template_id="test",
            template_version="v1",
            system_prompt="system",
            user_prompt="user",
            response_model=ResponseModel,
            mock_payload={},
        )
    assert result.output.value == 3
    assert result.metadata.attempts == 2


@pytest.mark.asyncio
async def test_invalid_json_fails_after_retry() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not-json"}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="https://example.test/v1", api_key="secret", model="test", client=client
        )
        with pytest.raises(ProviderFailure, match="two attempts"):
            await provider.generate_structured(
                template_id="test",
                template_version="v1",
                system_prompt="system",
                user_prompt="user",
                response_model=ResponseModel,
                mock_payload={},
            )


@pytest.mark.asyncio
async def test_timeout_is_controlled() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="https://example.test/v1", api_key="secret", model="test", client=client
        )
        with pytest.raises(ProviderFailure) as captured:
            await provider.generate_structured(
                template_id="test",
                template_version="v1",
                system_prompt="system",
                user_prompt="user",
                response_model=ResponseModel,
                mock_payload={},
            )
    assert captured.value.code == "PROVIDER_TIMEOUT"
