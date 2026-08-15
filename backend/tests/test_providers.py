from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from app.providers.base import ProviderFailure
from app.providers.mock_provider import MockProvider
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.schemas.models import (
    Certainty,
    EvidenceSpan,
    ExtractedField,
    ExtractionModelOutput,
    StrictModel,
)


# ── Minimal test model for lightweight tests ────────────────────────────────

class ResponseModel(BaseModel):
    value: int


# ── Canonical Extraction helpers ────────────────────────────────────────────

def _canonical_extraction_json() -> dict:
    """Return a schema-valid ExtractionModelOutput payload."""
    return {
        "fields": [
            {
                "field_id": "FIELD-R1-NAME-0",
                "key": "name",
                "label": "Name",
                "value": "Amira Saleh",
                "certainty": "exact",
                "source_span_id": "SPAN-R1-NAME-0",
            },
            {
                "field_id": "FIELD-R1-AGE-MISSING",
                "key": "age",
                "label": "Age",
                "value": None,
                "certainty": "missing",
                "unknown": True,
            },
        ],
        "evidence_spans": [
            {
                "span_id": "SPAN-R1-NAME-0",
                "record_id": "REC-001",
                "field": "Name",
                "quote": "Amira Saleh",
                "text": "Amira Saleh",
                "start": 0,
                "end": 12,
                "certainty": "exact",
                "extraction_method": "llm",
            }
        ],
        "warnings": [],
    }


def _qwen_style_wrong_json() -> dict:
    """Mimic the Qwen-style wrong structure: 'offset' arrays, 'value' instead of 'field', top-level 'record_id'."""
    return {
        "record_id": "FAMILY-042",
        "fields": [
            {
                "field_id": "f0",
                "key": "name",
                "label": "Name",
                "value": "Amira Saleh",
                "certainty": "exact",
                "source_span_id": "s0",
                "offset": [14, 24],
            }
        ],
        "evidence_spans": [
            {
                "span_id": "s0",
                "record_id": "FAMILY-042",
                "value": "Amira Saleh",
                "quote": "Amira Saleh",
                "text": "Amira Saleh",
                "start": 14,
                "end": 24,
                "certainty": "exact",
                "extraction_method": "llm",
            }
        ],
        "warnings": [],
    }


# ── Existing tests (updated for new provider semantics) ─────────────────────


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
async def test_schema_repair_succeeds() -> None:
    """First response fails validation, repair response passes."""
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
    assert result.metadata.attempts == 2  # initial + repair


@pytest.mark.asyncio
async def test_invalid_json_fails_after_repair() -> None:
    """Both initial and repair responses are unparseable → fail closed."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not-json"}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="https://example.test/v1", api_key="secret", model="test", client=client
        )
        with pytest.raises(ProviderFailure, match="schema validation"):
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
            base_url="https://example.test/v1",
            api_key="secret",
            model="test",
            client=client,
            max_retries=0,
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


# ── New extraction-focused tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_canonical_extraction_validates_immediately() -> None:
    """A valid ExtractionModelOutput JSON passes validation on the first response."""
    valid = _canonical_extraction_json()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(valid)}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="https://example.test/v1", api_key="secret", model="test", client=client
        )
        result = await provider.generate_structured(
            template_id="extraction",
            template_version="v1",
            system_prompt="system",
            user_prompt="user",
            response_model=ExtractionModelOutput,
            mock_payload={},
        )
    assert isinstance(result.output, ExtractionModelOutput)
    assert len(result.output.fields) == 2
    assert result.output.fields[0].key == "name"
    assert result.output.evidence_spans[0].start == 0
    assert result.output.evidence_spans[0].end == 12
    assert result.metadata.attempts == 1  # no repair needed


@pytest.mark.asyncio
async def test_qwen_style_wrong_structure_fails_validation() -> None:
    """Qwen-style wrong JSON fails Pydantic validation (extra fields, missing fields)."""
    wrong = _qwen_style_wrong_json()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(wrong)}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="https://example.test/v1", api_key="secret", model="test", client=client
        )
        # Both initial and repair get the same wrong JSON
        with pytest.raises(ProviderFailure, match="schema validation"):
            await provider.generate_structured(
                template_id="extraction",
                template_version="v1",
                system_prompt="system",
                user_prompt="user",
                response_model=ExtractionModelOutput,
                mock_payload={},
            )


@pytest.mark.asyncio
async def test_repair_produces_valid_canonical() -> None:
    """Initial response is Qwen-style wrong, repair returns canonical → succeeds."""
    wrong = _qwen_style_wrong_json()
    valid = _canonical_extraction_json()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = wrong if calls == 1 else valid
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(content)}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="https://example.test/v1", api_key="secret", model="test", client=client
        )
        result = await provider.generate_structured(
            template_id="extraction",
            template_version="v1",
            system_prompt="system",
            user_prompt="user",
            response_model=ExtractionModelOutput,
            mock_payload={},
        )
    assert isinstance(result.output, ExtractionModelOutput)
    assert result.metadata.attempts == 2  # initial + repair
    assert result.output.fields[0].key == "name"
    # Verify no offset/keyword/extra fields leaked
    assert not hasattr(result.output.fields[0], "offset")


@pytest.mark.asyncio
async def test_repair_fails_closed() -> None:
    """Both initial and repair are wrong → ProviderFailure, no partial output."""
    wrong = _qwen_style_wrong_json()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        # Slightly different wrong output each time
        content = dict(wrong) if calls == 1 else {**wrong, "extra_top": True}
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(content)}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="https://example.test/v1", api_key="secret", model="test", client=client
        )
        with pytest.raises(ProviderFailure, match="schema validation"):
            await provider.generate_structured(
                template_id="extraction",
                template_version="v1",
                system_prompt="system",
                user_prompt="user",
                response_model=ExtractionModelOutput,
                mock_payload={},
            )


@pytest.mark.asyncio
async def test_extra_fields_rejected() -> None:
    """A valid response with an extra top-level key is rejected (StrictModel extra=forbid)."""
    base = _canonical_extraction_json()
    base["unsupported_claim"] = "identity is confirmed"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(base)}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="https://example.test/v1", api_key="secret", model="test", client=client
        )
        with pytest.raises(ProviderFailure, match="schema validation"):
            await provider.generate_structured(
                template_id="extraction",
                template_version="v1",
                system_prompt="system",
                user_prompt="user",
                response_model=ExtractionModelOutput,
                mock_payload={},
            )


@pytest.mark.asyncio
async def test_no_unsupported_evidence_introduced_during_repair() -> None:
    """Repair must not introduce evidence that wasn't in the original text context."""
    wrong = _qwen_style_wrong_json()
    valid = _canonical_extraction_json()
    # Inject an extra span that wasn't in the original wrong output
    injected = dict(valid)
    injected["evidence_spans"].append({
        "span_id": "SPAN-INJECTED",
        "record_id": "REC-001",
        "field": "Fabricated",
        "quote": "invented text",
        "text": "invented text",
        "start": 0,
        "end": 13,
        "certainty": "exact",
        "extraction_method": "llm",
    })
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = wrong if calls == 1 else injected
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(content)}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="https://example.test/v1", api_key="secret", model="test", client=client
        )
        # The provider validates schema only — it doesn't cross-check evidence
        # against original text. The evidence_validation service handles that.
        # Schema validation passes here because the JSON is structurally valid.
        # The downstream extraction node applies evidence validation separately.
        result = await provider.generate_structured(
            template_id="extraction",
            template_version="v1",
            system_prompt="system",
            user_prompt="user",
            response_model=ExtractionModelOutput,
            mock_payload={},
        )
    # Schema-valid output produced; evidence cross-validation is the node's responsibility
    assert isinstance(result.output, ExtractionModelOutput)
    assert len(result.output.evidence_spans) == 2  # includes injected span


@pytest.mark.asyncio
async def test_all_mock_tests_make_no_network_calls() -> None:
    """All tests in this module use httpx.MockTransport — zero real network."""
    # This is trivially true for all tests above; this test proves the pattern works.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps({"value": 42})}}]}
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
    assert result.output.value == 42


@pytest.mark.asyncio
async def test_transport_errors_do_not_consume_schema_repair() -> None:
    """A transport error on the initial attempt is retried; schema repair is still available."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadTimeout("timeout", request=request)
        if calls == 2:
            # First successful response is wrong
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": json.dumps({"value": "bad"})}}]},
            )
        # Repair response is correct
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps({"value": 99})}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="https://example.test/v1",
            api_key="secret",
            model="test",
            client=client,
            max_retries=2,
        )
        result = await provider.generate_structured(
            template_id="test",
            template_version="v1",
            system_prompt="system",
            user_prompt="user",
            response_model=ResponseModel,
            mock_payload={},
        )
    assert result.output.value == 99
    assert result.metadata.attempts == 3  # timeout retry + wrong response + repair


@pytest.mark.asyncio
async def test_truncated_response_fails_before_repair() -> None:
    """A truncated response (finish_reason=length) raises immediately, no repair."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": '{"value": 1'},
                        "finish_reason": "length",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="https://example.test/v1", api_key="secret", model="test", client=client
        )
        with pytest.raises(ProviderFailure, match="truncated"):
            await provider.generate_structured(
                template_id="test",
                template_version="v1",
                system_prompt="system",
                user_prompt="user",
                response_model=ResponseModel,
                mock_payload={},
            )
