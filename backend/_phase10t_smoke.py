"""Phase 10T — progressive Featherless smoke tests (Phases B & C).

Test 1: provider/model availability request (GET /models)
Test 2: minimal JSON completion (chat/completions with tiny payload)
Test 3: minimal structured completion through the real extraction path
Test 4: live extraction on a small benchmark subset (Phase C records)

Never prints API keys or raw record text containing identifiers.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from time import perf_counter

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import Settings
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.schemas.models import (
    ExtractionModelOutput, ProviderResult,
)
from app.services.identity_benchmark import load_benchmark
from app.prompts.loader import load_prompt
from app.providers.openai_compatible import _format_schema_for_prompt

SETTINGS = Settings()

# Recommended Phase C smoke subset
SMOKE_INCIDENTS = [
    "INC-CLEAR-MATCH-GOV-ID",
    "INC-CLEAR-NONMATCH-DIFFERENT-IDS",
    "INC-PHONE-FORMAT-VARIATION",
    "INC-SPARSE-REPORT",
]


def classify_http(status: int | None, body: str) -> str:
    if status is None:
        return "provider_transport_failure"
    if status == 401 or status == 403:
        return "provider_auth_failure"
    if status == 404:
        return "model_unavailable"
    if status == 429:
        return "provider_rate_limit"
    if status in (500, 502, 503, 504):
        return "provider_error"
    if status >= 400:
        return "provider_error"
    return "ok"


async def test1_connectivity() -> dict:
    """GET /models — auth + endpoint + model existence."""
    out: dict = {"test": "1-connectivity"}
    started = perf_counter()
    try:
        async with httpx.AsyncClient(timeout=SETTINGS.llm_timeout_seconds) as client:
            resp = await client.get(
                f"{SETTINGS.openai_base_url}/models",
                headers={"Authorization": f"Bearer {SETTINGS.openai_api_key}"},
            )
        out["latency_ms"] = round((perf_counter() - started) * 1000)
        out["http_status"] = resp.status_code
        body = resp.text
        out["classification"] = classify_http(resp.status_code, body)
        if resp.status_code == 200:
            try:
                data = resp.json()
                models = [m.get("id") for m in data.get("data", [])]
                out["models_count"] = len(models)
                out["model_present"] = SETTINGS.openai_model in models
                out["sample_model_ids"] = models[:5]
            except Exception:
                out["parse_error"] = "non-json body"
        else:
            out["response_preview"] = body[:200]
    except httpx.TimeoutException:
        out["classification"] = "provider_timeout"
        out["latency_ms"] = round((perf_counter() - started) * 1000)
    except httpx.ConnectError:
        out["classification"] = "provider_transport_failure"
        out["error"] = "connect error"
    except Exception as exc:
        out["classification"] = "provider_transport_failure"
        out["error"] = type(exc).__name__
    return out


async def test2_minimal_completion() -> dict:
    """Minimal chat/completions completion — no structured schema yet."""
    out: dict = {"test": "2-minimal-completion"}
    started = perf_counter()
    try:
        async with httpx.AsyncClient(timeout=SETTINGS.llm_timeout_seconds) as client:
            resp = await client.post(
                f"{SETTINGS.openai_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {SETTINGS.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": SETTINGS.openai_model,
                    "messages": [
                        {"role": "system", "content": "Reply with exactly the JSON object {\"ok\": true}."},
                        {"role": "user", "content": "Confirm."},
                    ],
                    "temperature": SETTINGS.llm_temperature,
                    "max_tokens": 32,
                },
            )
        out["latency_ms"] = round((perf_counter() - started) * 1000)
        out["http_status"] = resp.status_code
        out["classification"] = classify_http(resp.status_code, resp.text)
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            finish = data["choices"][0].get("finish_reason")
            out["finish_reason"] = finish
            out["content_preview"] = content[:80]
            out["usage"] = data.get("usage")
            try:
                parsed = json.loads(content)
                out["json_parses"] = True
                out["json_ok_key"] = parsed.get("ok") is True
            except json.JSONDecodeError:
                out["json_parses"] = False
                out["classification"] = "invalid_json"
        else:
            out["response_preview"] = resp.text[:200]
    except httpx.TimeoutException:
        out["classification"] = "provider_timeout"
        out["latency_ms"] = round((perf_counter() - started) * 1000)
    except httpx.ConnectError:
        out["classification"] = "provider_transport_failure"
        out["error"] = "connect error"
    except Exception as exc:
        out["classification"] = "provider_transport_failure"
        out["error"] = type(exc).__name__
    return out


async def test3_structured_extraction() -> dict:
    """Minimal structured extraction through the real provider path."""
    out: dict = {"test": "3-structured-extraction"}
    template = load_prompt("extraction", "v1")
    schema_block = _format_schema_for_prompt(ExtractionModelOutput.model_json_schema())
    system_prompt = f"{template.content}\n{schema_block}"
    user_prompt = (
        "<untrusted_evidence record_id='SMOKE-001'>\n"
        "Name: Youssef Al Hassan. Date of birth: 1985-04-15. "
        "Phone: +1-555-1234567.\n"
        "</untrusted_evidence>"
    )
    provider = OpenAICompatibleProvider(
        base_url=SETTINGS.openai_base_url,
        api_key=SETTINGS.openai_api_key or "",
        model=SETTINGS.openai_model,
        temperature=SETTINGS.llm_temperature,
        timeout_seconds=SETTINGS.llm_timeout_seconds,
        max_retries=SETTINGS.llm_max_retries,
    )
    started = perf_counter()
    try:
        pr: ProviderResult = await provider.generate_structured(
            template_id="extraction",
            template_version="v1",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ExtractionModelOutput,
            mock_payload={},
        )
        out["latency_ms"] = round((perf_counter() - started) * 1000)
        out["classification"] = "ok"
        out["attempts"] = pr.metadata.attempts
        out["token_usage"] = pr.metadata.token_usage
        out["model"] = pr.metadata.model
        out["field_keys"] = [f.key for f in pr.output.fields]
        out["field_count"] = len(pr.output.fields)
    except Exception as exc:
        out["latency_ms"] = round((perf_counter() - started) * 1000)
        cls = type(exc).__name__
        msg = str(exc)[:200]
        out["exception"] = cls
        if "SCHEMA" in cls or "schema" in msg:
            out["classification"] = "schema_validation"
        elif "TRUNCATED" in cls:
            out["classification"] = "truncated_response"
        elif "TIMEOUT" in cls:
            out["classification"] = "provider_timeout"
        elif "HTTP" in msg or "status" in msg:
            out["classification"] = "provider_error"
        else:
            out["classification"] = "provider_error"
        out["error_preview"] = msg
    return out


async def test4_benchmark_records() -> list[dict]:
    """Live extraction on the Phase C smoke subset records."""
    benchmark = load_benchmark()
    subset = [inc for inc in benchmark if inc["incident_id"] in SMOKE_INCIDENTS]
    template = load_prompt("extraction", "v1")
    schema_block = _format_schema_for_prompt(ExtractionModelOutput.model_json_schema())
    system_prompt = f"{template.content}\n{schema_block}"
    provider = OpenAICompatibleProvider(
        base_url=SETTINGS.openai_base_url,
        api_key=SETTINGS.openai_api_key or "",
        model=SETTINGS.openai_model,
        temperature=SETTINGS.llm_temperature,
        timeout_seconds=SETTINGS.llm_timeout_seconds,
        max_retries=SETTINGS.llm_max_retries,
    )

    results = []
    for inc in subset:
        for rec in inc["records"]:
            user_prompt = (
                f"<untrusted_evidence record_id={rec['record_id']!r}>\n"
                f"{rec['text']}\n</untrusted_evidence>"
            )
            entry = {
                "incident_id": inc["incident_id"],
                "record_id": rec["record_id"],
            }
            started = perf_counter()
            try:
                pr = await provider.generate_structured(
                    template_id="extraction",
                    template_version="v1",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_model=ExtractionModelOutput,
                    mock_payload={},
                )
                entry["latency_ms"] = round((perf_counter() - started) * 1000)
                entry["status"] = "ok"
                entry["field_keys"] = [f.key for f in pr.output.fields]
                entry["attempts"] = pr.metadata.attempts
                entry["tokens"] = pr.metadata.token_usage
                # Canonical-key validity via the shared field key normalizer
                from app.services.field_key_normalizer import normalize_field_key
                keys = [f.key for f in pr.output.fields]
                normalized = [normalize_field_key(k) for k in keys]
                entry["canonical_keys"] = [
                    nk.canonical_key.value if nk.canonical_key else None
                    for nk in normalized
                ]
                entry["unknown_keys"] = [
                    k for k, nk in zip(keys, normalized)
                    if nk.canonical_key is None
                ]
            except Exception as exc:
                entry["latency_ms"] = round((perf_counter() - started) * 1000)
                cls = type(exc).__name__
                msg = str(exc)[:200]
                entry["status"] = "error"
                entry["exception"] = cls
                if "SCHEMA" in cls:
                    entry["classification"] = "schema_validation"
                elif "TRUNCATED" in cls:
                    entry["classification"] = "truncated_response"
                elif "TIMEOUT" in cls:
                    entry["classification"] = "provider_timeout"
                else:
                    entry["classification"] = "provider_error"
                entry["error_preview"] = msg
            results.append(entry)
    return results


async def main() -> int:
    print("=" * 70)
    print("PHASE 10T — LIVE FEATHERLESS SMOKE TESTS")
    print("=" * 70)
    print(f"base_url: {SETTINGS.openai_base_url}")
    print(f"model: {SETTINGS.openai_model}")
    print(f"temperature: {SETTINGS.llm_temperature}")
    print(f"timeout: {SETTINGS.llm_timeout_seconds}s")
    print(f"max_retries: {SETTINGS.llm_max_retries}")
    print(f"api_key_present: {bool(SETTINGS.openai_api_key)}")
    print()

    t1 = await test1_connectivity()
    print("[TEST 1] connectivity")
    print(" ", json.dumps(t1, indent=2, default=str))
    print()

    t2 = await test2_minimal_completion()
    print("[TEST 2] minimal completion")
    print(" ", json.dumps(t2, indent=2, default=str))
    print()

    t3 = await test3_structured_extraction()
    print("[TEST 3] structured extraction")
    print(" ", json.dumps(t3, indent=2, default=str))
    print()

    print("[TEST 4] benchmark-record extraction (Phase C subset)")
    t4 = await test4_benchmark_records()
    for entry in t4:
        print(" ", json.dumps(entry, indent=2, default=str))
    print()

    # Summary
    classifications = [
        t1.get("classification", "unknown"),
        t2.get("classification", "unknown"),
        t3.get("classification", "unknown"),
    ] + [e.get("classification", "unknown") for e in t4]
    print("=" * 70)
    print("SUMMARY")
    ok_count = sum(1 for c in classifications if c == "ok")
    print(f"  ok: {ok_count}/{len(classifications)}")
    from collections import Counter
    print("  by class:", dict(Counter(classifications)))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
