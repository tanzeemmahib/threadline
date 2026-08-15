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

# ── Schema helpers ──────────────────────────────────────────────────────────


def _sanitize_schema_for_response_format(raw: dict[str, Any]) -> dict[str, Any]:
    """Strip keys unsupported by OpenAI-style strict json_schema response_format.

    Removes ``title``, ``default``, and ``$schema`` recursively.  Does **not**
    attempt full strict-mode normalisation (nullables, required lists, etc.)
    because Featherless / proxy tiers often accept a plain JSON Schema without
    ``strict: true``.
    """
    if not isinstance(raw, dict):
        return raw
    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        if key in {"title", "default", "$schema"}:
            continue
        if key == "$defs" and isinstance(value, dict):
            cleaned[key] = {k: _sanitize_schema_for_response_format(v) for k, v in value.items()}
        elif isinstance(value, dict):
            cleaned[key] = _sanitize_schema_for_response_format(value)
        elif isinstance(value, list):
            cleaned[key] = [
                _sanitize_schema_for_response_format(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            cleaned[key] = value
    return cleaned


def _format_schema_for_prompt(raw: dict[str, Any], indent: int = 0) -> str:
    """Render a Pydantic JSON Schema as readable prompt text.

    Describes required fields, types, enums, nested objects, and the
    ``additionalProperties: false`` constraint.
    """
    lines: list[str] = []
    prefix = "  " * indent

    if raw.get("additionalProperties") is False:
        lines.append(f"{prefix}No additional properties are allowed.")

    required: list[str] = raw.get("required", [])
    properties = raw.get("properties", {})

    if properties:
        lines.append(f"{prefix}Fields:")
        for name, spec in properties.items():
            req_mark = " (required)" if name in required else " (optional)"
            type_info = _describe_type(spec, indent + 1)
            lines.append(f"{prefix}  - {name}: {type_info}{req_mark}")

    if "$defs" in raw:
        for def_name, def_spec in raw["$defs"].items():
            lines.append(f"\n{prefix}Nested type `{def_name}`:")
            lines.append(_format_schema_for_prompt(def_spec, indent + 1))

    return "\n".join(lines)


def _describe_type(spec: dict[str, Any], indent: int) -> str:
    """Produce a short human-readable type label from a JSON Schema property."""
    prefix = "  " * indent
    type_val = spec.get("type", "any")

    if "enum" in spec:
        return f"enum: [{', '.join(repr(v) for v in spec['enum'])}]"
    if type_val == "array":
        items = spec.get("items", {})
        item_ref = items.get("$ref", "")
        if item_ref:
            return f"array of {item_ref.split('/')[-1]}"
        return f"array of {_describe_type(items, 0)}"
    if "anyOf" in spec:
        types = [_describe_type(t, 0) for t in spec["anyOf"]]
        return " or ".join(types)
    if type_val == "null":
        return "null"
    if isinstance(type_val, list):
        return " or ".join(type_val)
    return str(type_val)


def _summarize_error(exc: Exception) -> str:
    """Return a bounded representation of a parse or validation error."""
    text = str(exc)
    if len(text) > 800:
        text = text[:800] + "\n... (truncated)"
    return text

# ── Transport helpers ────────────────────────────────────────────────────────


_RETRYABLE_STATUSES = frozenset({429, 502, 503, 504})
_RESPONSE_FORMAT_ERROR_KEYWORDS = ("response_format", "json_schema", "structured output")


def _is_response_format_error(status: int, body: str) -> bool:
    """Return True when a 400 response body indicates unsupported response_format."""
    if status != 400:
        return False
    body_lower = body.lower()
    return any(kw in body_lower for kw in _RESPONSE_FORMAT_ERROR_KEYWORDS)

# ── Provider ─────────────────────────────────────────────────────────────────


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
        # Probe cache: None = unknown, True = supported, False = unsupported
        self._json_schema_supported: bool | None = None

    # ── Public API ───────────────────────────────────────────────────────

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

        raw_schema = response_model.model_json_schema()

        # ── 1. Transport request with retry ──────────────────────────
        data, transport_attempts = await self._request_with_retry(
            system_prompt, user_prompt, raw_schema
        )

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {}).get("total_tokens")
        finish_reason = data["choices"][0].get("finish_reason", "")

        # ── 2. Truncation guard ──────────────────────────────────────
        if finish_reason == "length":
            raise ProviderFailure(
                "MODEL_RESPONSE_TRUNCATED",
                "Model response was truncated (max_tokens limit). Cannot validate.",
                retryable=False,
            )

        # ── 3. Parse + validate ──────────────────────────────────────
        try:
            parsed = json.loads(content)
            output = response_model.model_validate(parsed)
            return ProviderResult(
                output=output,
                metadata=ProviderMetadata(
                    provider=self.mode,
                    model=self.model_name,
                    prompt_template_id=template_id,
                    prompt_template_version=template_version,
                    attempts=transport_attempts,
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                    token_usage=int(usage) if usage is not None else None,
                ),
            )
        except json.JSONDecodeError as exc:
            repair_error = _summarize_error(exc)
            invalid_content = content
        except ValidationError as exc:
            repair_error = _summarize_error(exc)
            invalid_content = content

        # ── 4. Schema repair (exactly one attempt) ────────────────────
        repair = await self._schema_repair(
            system_prompt, invalid_content, repair_error, response_model, raw_schema
        )
        if repair is not None:
            output, repair_usage, repair_attempts = repair
            return ProviderResult(
                output=output,
                metadata=ProviderMetadata(
                    provider=self.mode,
                    model=self.model_name,
                    prompt_template_id=template_id,
                    prompt_template_version=template_version,
                    attempts=transport_attempts + repair_attempts,
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                    token_usage=int(repair_usage) if repair_usage is not None else None,
                ),
            )

        # ── 5. Fail closed ───────────────────────────────────────────
        raise ProviderFailure(
            "MODEL_RESPONSE_SCHEMA_FAILURE",
            f"Model response failed schema validation and repair: {repair_error}",
        )

    # ── Transport request with retry ──────────────────────────────────

    async def _request_with_retry(
        self, system_prompt: str, user_prompt: str, raw_schema: dict[str, Any]
    ) -> tuple[dict[str, Any], int]:
        """Send the request, retrying on transient errors.

        Also handles the one-time json_schema → json_object fallback when
        the endpoint does not support structured response_format.
        """
        rf = self._build_response_format(raw_schema)
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 2):
            try:
                data = await self._do_request(system_prompt, user_prompt, rf)
                # If we got here with json_schema, it's supported
                if self._json_schema_supported is None and rf.get("type") == "json_schema":
                    self._json_schema_supported = True
                return data, attempt
            except httpx.HTTPStatusError as exc:
                body = exc.response.text if hasattr(exc.response, "text") else ""
                status = exc.response.status_code if hasattr(exc.response, "status_code") else 0

                # json_schema probe: any error on the first json_schema attempt → fall back
                if (self._json_schema_supported is None
                        and rf.get("type") == "json_schema"):
                    self._json_schema_supported = False
                    rf = {"type": "json_object"}
                    continue

                # Retry on transient errors (rate-limit, server errors, model busy)
                is_busy = status == 400 and "busy" in body.lower()
                if (status in _RETRYABLE_STATUSES or is_busy) and attempt <= self.max_retries:
                    last_error = exc
                    await asyncio.sleep(min(2**attempt, 30))
                    continue

                raise ProviderFailure(
                    "PROVIDER_REQUEST_FAILURE",
                    f"Model provider request failed (HTTP {status}).",
                    retryable=True,
                ) from exc
            except (httpx.TimeoutException, httpx.ReadError, httpx.ConnectError) as exc:
                last_error = exc
                if attempt <= self.max_retries:
                    await asyncio.sleep(min(2**attempt, 30))
                    continue
                raise ProviderFailure(
                    "PROVIDER_TIMEOUT",
                    "Model provider timed out.",
                    retryable=True,
                ) from exc

        raise ProviderFailure(
            "PROVIDER_REQUEST_FAILURE",
            "Model provider request failed after all retries.",
            retryable=True,
        ) from last_error

    # ── Schema repair ─────────────────────────────────────────────────

    async def _schema_repair(
        self,
        system_prompt: str,
        invalid_content: str,
        repair_error: str,
        response_model: type[ModelT],
        raw_schema: dict[str, Any],
    ) -> tuple[BaseModel, int | None, int] | None:
        """Send exactly one repair request.

        Returns ``(output, token_usage, attempt_count)`` on success, or
        ``None`` when repair also fails.
        """
        schema_text = json.dumps(
            _sanitize_schema_for_response_format(raw_schema), indent=2
        )
        # Limit the invalid content to avoid blowing the context window
        bounded_content = invalid_content if len(invalid_content) <= 3000 else (
            invalid_content[:3000] + "\n... (truncated)"
        )
        repair_prompt = (
            "The following JSON output failed validation.\n\n"
            "Invalid output:\n"
            f"{bounded_content}\n\n"
            "Validation errors:\n"
            f"{repair_error}\n\n"
            "Canonical JSON Schema:\n"
            f"{schema_text}\n\n"
            "Return ONLY the corrected JSON object. No explanation, no markdown."
        )

        rf = self._build_response_format(raw_schema)
        try:
            data, attempts = await self._request_with_retry(
                system_prompt, repair_prompt, raw_schema
            )
        except ProviderFailure:
            return None

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {}).get("total_tokens")
        finish_reason = data["choices"][0].get("finish_reason", "")

        if finish_reason == "length":
            return None

        try:
            parsed = json.loads(content)
            output = response_model.model_validate(parsed)
            return output, int(usage) if usage is not None else None, attempts
        except (json.JSONDecodeError, ValidationError):
            return None

    # ── Helpers ───────────────────────────────────────────────────────

    def _build_response_format(self, raw_schema: dict[str, Any]) -> dict[str, Any]:
        """Return the response_format payload to send."""
        if self._json_schema_supported is False:
            return {"type": "json_object"}
        # If unknown (None) or True, try json_schema
        cleaned = _sanitize_schema_for_response_format(raw_schema)
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "response",
                "schema": cleaned,
            },
        }

    async def _do_request(
        self, system_prompt: str, user_prompt: str, response_format: dict[str, Any]
    ) -> dict[str, Any]:
        """Single HTTP call — no retry logic."""
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": response_format,
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
