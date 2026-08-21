from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.routes import reverie as reverie_routes
from app.baselines.reverie_one_shot import run_reverie_one_shot
from app.baselines.single_call import run_single_call
from app.config import Settings
from app.evaluation.reverie_live import (
    RecordingOpenAICompatibleProvider,
    _one_shot_metrics,
)
from app.main import create_app
from app.schemas.models import Classification, SingleCallModelOutput
from app.schemas.reverie_evaluation import (
    FrozenLiveEvaluationSpec,
    LiveEvaluationArtifact,
    OneShotEvidenceClaim,
    ProviderRecorderCheckpoint,
    ReverieOneShotModelOutput,
    load_frozen_live_evaluation_spec,
)
from app.services.extraction import extract_record

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPOSITORY_ROOT / "backend" / "fixtures" / "reverie_live_evaluation_v1.json"
FAIR_SPEC_PATH = REPOSITORY_ROOT / "backend" / "fixtures" / "reverie_live_evaluation_v1_1.json"


def _spec() -> tuple[FrozenLiveEvaluationSpec, str]:
    return load_frozen_live_evaluation_spec(SPEC_PATH, repository_root=REPOSITORY_ROOT)


def _fair_spec() -> tuple[FrozenLiveEvaluationSpec, str]:
    return load_frozen_live_evaluation_spec(FAIR_SPEC_PATH, repository_root=REPOSITORY_ROOT)


def _settings(spec: FrozenLiveEvaluationSpec, key: str = "unit-test-secret") -> Settings:
    return Settings(
        provider_mode=spec.provider.mode,
        openai_base_url=spec.provider.base_url,
        openai_api_key=key,
        openai_model=spec.provider.model,
        llm_temperature=spec.provider.temperature,
        llm_timeout_seconds=spec.provider.timeout_seconds,
        llm_max_retries=spec.provider.max_transport_retries,
        llm_max_concurrent_calls=spec.provider.max_concurrent_calls,
    )


def _fair_one_shot_spec() -> FrozenLiveEvaluationSpec:
    spec, _ = _fair_spec()
    return spec


def test_frozen_spec_validates_all_pins_and_identical_inputs() -> None:
    spec, digest = _spec()
    assert digest == "dccfb17115077a2869f88d00466825bf9b85d3969ae32aabcf2c3e1a5b811c99"
    assert [case.case_id for case in spec.cases] == spec.schedule.case_order
    assert all(case.input_manifest.record_count == 2 for case in spec.cases)
    assert spec.evaluation_policy.ground_truth_visible_to_provider is False
    assert spec.evaluation_policy.thresholds_mutable is False


def test_fair_spec_supersedes_draft_before_observation_and_freezes_symmetric_metrics() -> None:
    spec, digest = _fair_spec()
    assert digest == "458279a9595b79e3785af7004cf68a93223fde21e0934b4c432525bebdc786a1"
    assert spec.supersedes is not None
    assert spec.supersedes.sha256 == (
        "dccfb17115077a2869f88d00466825bf9b85d3969ae32aabcf2c3e1a5b811c99"
    )
    assert spec.supersedes.status == "superseded_before_provider_observation"
    assert set(spec.metrics) == set(spec.metric_definitions)
    assert "identical rule for both systems" in spec.metric_definitions["source_span_coverage"]
    one_shot = next(system for system in spec.systems if system.system_id == "structured_one_shot")
    assert one_shot.prompt_ids == ["reverie_one_shot:v1"]
    assert one_shot.output_schema_names == ["ReverieOneShotModelOutput"]
    assert all(case.ground_truth.acceptable_one_shot_classifications for case in spec.cases)


def test_frozen_spec_fails_closed_on_source_or_schema_drift(tmp_path: Path) -> None:
    raw = json.loads(SPEC_PATH.read_text("utf-8"))
    raw["fixture"]["sha256"] = "0" * 64
    drifted = tmp_path / "drifted-source.json"
    drifted.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="pinned source drift"):
        load_frozen_live_evaluation_spec(drifted, repository_root=REPOSITORY_ROOT)

    raw = json.loads(SPEC_PATH.read_text("utf-8"))
    raw["output_schemas"][0]["sha256"] = "0" * 64
    drifted = tmp_path / "drifted-schema.json"
    drifted.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="output schema drift"):
        load_frozen_live_evaluation_spec(drifted, repository_root=REPOSITORY_ROOT)


def test_frozen_spec_fails_closed_on_input_manifest_drift() -> None:
    raw = json.loads(SPEC_PATH.read_text("utf-8"))
    raw["cases"][0]["input_manifest"]["input_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="input manifest input_sha256"):
        FrozenLiveEvaluationSpec.model_validate(raw)


def test_live_evaluation_endpoint_has_explicit_missing_and_strict_states(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(reverie_routes, "_repository_root", lambda: tmp_path)
    client = TestClient(create_app(Settings(database_path=str(tmp_path / "threadline.db"))))
    missing = client.get("/api/v1/reverie/live-evaluation")
    assert missing.status_code == 404
    assert missing.json()["detail"]["error_code"] == "REVERIE_LIVE_EVALUATION_NOT_MEASURED"

    artifact_path = tmp_path / "backend" / "data" / "reverie_live_evaluation_v1_1" / "results.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text('{"schema_version":"wrong"}', encoding="utf-8")
    invalid = client.get("/api/v1/reverie/live-evaluation")
    assert invalid.status_code == 503
    assert invalid.json()["detail"]["error_code"] == "REVERIE_LIVE_EVALUATION_INVALID"

    spec, spec_sha = _spec()
    now = "2026-08-21T01:00:00Z"
    artifact = LiveEvaluationArtifact(
        schema_version="threadline-reverie-live-evaluation-results/1.0.0",
        artifact_id="TEST-LIVE-ARTIFACT",
        status="partial",
        evaluation_label="Measured live-provider comparison",
        synthetic_only=True,
        safety_scope=spec.safety_scope,
        spec_id=spec.spec_id,
        spec_path="backend/fixtures/reverie_live_evaluation_v1.json",
        spec_sha256=spec_sha,
        source_commit=spec.source_commit,
        provider={"model": spec.provider.model},
        same_input_and_config_verified=True,
        expected_system_runs=18,
        completed_system_runs=0,
        failed_system_runs=0,
        started_at=now,
        updated_at=now,
        recorder_artifact_path="backend/data/reverie_live_evaluation_v1_1/raw-provider-calls.json",
        recorder_artifact_sha256="0" * 64,
        cases=[],
        aggregate={},
        limitations=spec.limitations,
    )
    artifact_path.write_text(artifact.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(
        reverie_routes,
        "load_live_evaluation_artifact",
        lambda *_args, **_kwargs: artifact,
    )
    valid = client.get("/api/v1/reverie/live-evaluation")
    assert valid.status_code == 200
    assert valid.json()["status"] == "partial"


@pytest.mark.asyncio
async def test_recorder_sanitizes_raw_io_and_resumes_without_network(tmp_path: Path) -> None:
    spec, spec_sha = _spec()
    case = spec.cases[0]
    cited_ids = [
        span.span_id for record in case.request.records for span in extract_record(record)[1]
    ][:2]
    model_output = SingleCallModelOutput(
        classification=Classification.possible_candidate,
        candidate_record_ids=case.input_manifest.record_ids,
        cited_evidence_span_ids=cited_ids,
        supporting_evidence=["Synthetic cited fields overlap."],
        contradictions=[],
        uncertainty=["Authorized human review remains required."],
    )
    network_calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal network_calls
        network_calls += 1
        return httpx.Response(
            200,
            json={
                "id": "synthetic-provider-response",
                "choices": [
                    {
                        "message": {"content": json.dumps(model_output.model_dump(mode="json"))},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"total_tokens": 123},
            },
        )

    checkpoint = tmp_path / "raw-provider-calls.json"
    provider = RecordingOpenAICompatibleProvider(
        settings=_settings(spec),
        spec=spec,
        spec_sha256=spec_sha,
        checkpoint_path=checkpoint,
        system_run_id="REP-01:PROMPT-LAB-CROSS-SCRIPT:structured_one_shot",
        retry_recorded_errors=False,
    )
    first_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider._client = first_client
    first = await run_single_call(case.request, provider, structured=True)
    await first_client.aclose()
    assert first.classification == Classification.possible_candidate
    assert network_calls == 1

    serialized = checkpoint.read_text("utf-8")
    assert "unit-test-secret" not in serialized
    assert case.request.records[0].text in serialized
    saved = ProviderRecorderCheckpoint.model_validate_json(serialized)
    assert len(saved.calls) == 1
    assert len(saved.transport_attempts) == 1
    assert saved.transport_attempts[0].raw_response["id"] == "synthetic-provider-response"
    assert saved.contains_credentials is False

    def fail_if_called(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("resumed call reached the network")

    resumed = RecordingOpenAICompatibleProvider(
        settings=_settings(spec),
        spec=spec,
        spec_sha256=spec_sha,
        checkpoint_path=checkpoint,
        system_run_id="REP-01:PROMPT-LAB-CROSS-SCRIPT:structured_one_shot",
        retry_recorded_errors=False,
    )
    second_client = httpx.AsyncClient(transport=httpx.MockTransport(fail_if_called))
    resumed._client = second_client
    second = await run_single_call(case.request, resumed, structured=True)
    await second_client.aclose()
    assert second.output == first.output
    assert len(resumed.resumed_call_ids) == 1
    assert network_calls == 1


@pytest.mark.asyncio
async def test_recorder_keeps_sanitized_provider_errors(tmp_path: Path) -> None:
    spec, spec_sha = _spec()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "credential rejected"}})

    provider = RecordingOpenAICompatibleProvider(
        settings=_settings(spec),
        spec=spec,
        spec_sha256=spec_sha,
        checkpoint_path=tmp_path / "raw-provider-calls.json",
        system_run_id="REP-01:PROMPT-LAB-CROSS-SCRIPT:structured_one_shot",
        retry_recorded_errors=False,
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider._client = client
    with pytest.raises(Exception, match="Model provider request failed"):
        await provider.generate_structured(
            template_id="structured_baseline",
            template_version="v1",
            system_prompt="Return structured evidence.",
            user_prompt="Synthetic record.",
            response_model=SingleCallModelOutput,
            mock_payload={},
        )
    await client.aclose()
    checkpoint = provider.checkpoint
    call = next(iter(checkpoint.calls.values()))
    assert call.status == "error"
    assert len(checkpoint.transport_attempts) == 2
    assert all(attempt.status == "error" for attempt in checkpoint.transport_attempts)
    assert all(attempt.error is not None for attempt in checkpoint.transport_attempts)
    serialized = (tmp_path / "raw-provider-calls.json").read_text("utf-8")
    assert "unit-test-secret" not in serialized
    assert "credential rejected" in serialized


@pytest.mark.asyncio
async def test_fair_one_shot_receives_raw_records_and_returns_scoreable_spans(
    tmp_path: Path,
) -> None:
    spec = _fair_one_shot_spec()
    case = spec.cases[0]
    claims = []
    for record in case.request.records:
        quote = record.display_name or ""
        start = record.text.index(quote)
        claims.append(
            OneShotEvidenceClaim(
                record_id=record.record_id,
                field_key="name",
                value=quote,
                quote=quote,
                start=start,
                end=start + len(quote),
                certainty="exact",
            )
        )
    model_output = ReverieOneShotModelOutput(
        evidence_claims=claims,
        candidate_record_ids=case.input_manifest.record_ids,
        classification="possible_candidate",
        supporting_evidence_claim_indexes=[0, 1],
        contradictions=[],
        uncertainty=["Authorized human review remains required."],
        rationale="Native-script and transliterated names are supporting evidence only.",
    )
    captured_request = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request.content.decode("utf-8")
        return httpx.Response(
            200,
            json={
                "id": "fair-one-shot-response",
                "choices": [
                    {
                        "message": {"content": json.dumps(model_output.model_dump(mode="json"))},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"total_tokens": 150},
            },
        )

    provider = RecordingOpenAICompatibleProvider(
        settings=_settings(spec),
        spec=spec,
        spec_sha256="1" * 64,
        checkpoint_path=tmp_path / "raw-provider-calls.json",
        system_run_id="REP-01:PROMPT-LAB-CROSS-SCRIPT:structured_one_shot",
        retry_recorded_errors=False,
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider._client = client
    result = await run_reverie_one_shot(case.request, provider)
    await client.aclose()
    output = ReverieOneShotModelOutput.model_validate(result.output)
    assert all(record.text in captured_request for record in case.request.records)
    assert "SPAN-" not in captured_request
    assert "zero-based start and end character offsets" in captured_request
    metrics = _one_shot_metrics(case, output, calls=provider.calls_for_system_run())
    assert metrics.exact_citation_count == 2
    assert metrics.invalid_citation_count == 0
    assert metrics.supported_field_count == 2
