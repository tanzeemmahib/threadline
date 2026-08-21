from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from app.baselines.reverie_one_shot import run_reverie_one_shot
from app.baselines.single_call import build_input_manifest
from app.config import Settings
from app.providers.base import ProviderFailure
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.schemas.models import AnalyzeResponse, ProviderMetadata, ProviderResult
from app.schemas.reverie_evaluation import (
    FrozenEvaluationCase,
    FrozenLiveEvaluationSpec,
    LiveCaseRepetition,
    LiveEvaluationArtifact,
    LiveEvaluationWorkState,
    LiveSystemMetrics,
    LiveSystemRunResult,
    ProviderRecorderCheckpoint,
    ProviderTransportAttempt,
    RecordedProviderCall,
    ReverieOneShotModelOutput,
    SanitizedProviderError,
)
from app.services.canonical_json import canonical_sha256
from app.services.field_key_normalizer import normalize_field_key
from app.services.identity_benchmark import RECORD_EXPECTED_FIELDS
from app.workflow import WorkflowOrchestrator

ModelT = TypeVar("ModelT", bound=BaseModel)
SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "access_token",
    "refresh_token",
    "token",
    "secret",
    "password",
}


def utcnow() -> datetime:
    return datetime.now(UTC)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_write_json(path: Path, value: BaseModel | dict[str, Any]) -> str:
    """Write JSON durably in the destination directory and return its SHA-256."""

    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return sha256_bytes(encoded)


def _safe_value(value: Any, *, credential: str | None = None) -> Any:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        return {
            str(key): _safe_value(item, credential=credential)
            for key, item in value.items()
            if str(key).lower() not in SENSITIVE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_safe_value(item, credential=credential) for item in value]
    if isinstance(value, str) and credential:
        return value.replace(credential, "[REDACTED]")
    return value


def safe_provider_config(spec: FrozenLiveEvaluationSpec) -> dict[str, Any]:
    provider = spec.provider
    return {
        "mode": provider.mode,
        "base_url": provider.base_url,
        "model": provider.model,
        "temperature": provider.temperature,
        "timeout_seconds": provider.timeout_seconds,
        "max_transport_retries": provider.max_transport_retries,
        "max_schema_repair_attempts": provider.max_schema_repair_attempts,
        "max_concurrent_calls": provider.max_concurrent_calls,
        "seed": provider.seed,
        "seed_status": provider.seed_status,
        "response_format_policy": provider.response_format_policy,
    }


def assert_environment_matches_spec(spec: FrozenLiveEvaluationSpec, settings: Settings) -> None:
    observed = {
        "mode": settings.provider_mode,
        "base_url": settings.openai_base_url.rstrip("/"),
        "model": settings.openai_model,
        "temperature": settings.llm_temperature,
        "timeout_seconds": settings.llm_timeout_seconds,
        "max_transport_retries": settings.llm_max_retries,
        "max_concurrent_calls": settings.llm_max_concurrent_calls,
    }
    expected = {
        "mode": spec.provider.mode,
        "base_url": spec.provider.base_url.rstrip("/"),
        "model": spec.provider.model,
        "temperature": spec.provider.temperature,
        "timeout_seconds": spec.provider.timeout_seconds,
        "max_transport_retries": spec.provider.max_transport_retries,
        "max_concurrent_calls": spec.provider.max_concurrent_calls,
    }
    drift = {
        key: {"expected": expected[key], "observed": observed[key]}
        for key in expected
        if observed[key] != expected[key]
    }
    if drift:
        raise ValueError(f"live provider configuration drift: {drift}")
    if not settings.openai_api_key:
        raise ValueError("live provider credential is not configured")


def _provider_error(exc: Exception, *, raw_body: Any | None = None) -> SanitizedProviderError:
    return SanitizedProviderError(
        error_class=type(exc).__name__,
        error_code=getattr(exc, "code", None),
        message=str(exc),
        http_status=(exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None),
        retryable=getattr(exc, "retryable", None),
        raw_body=raw_body,
    )


class RecordingOpenAICompatibleProvider(OpenAICompatibleProvider[BaseModel]):
    """OpenAI-compatible provider with resumable, sanitized, atomic call recording."""

    def __init__(
        self,
        *,
        settings: Settings,
        spec: FrozenLiveEvaluationSpec,
        spec_sha256: str,
        checkpoint_path: Path,
        system_run_id: str,
        retry_recorded_errors: bool,
    ) -> None:
        super().__init__(
            base_url=spec.provider.base_url,
            api_key=settings.openai_api_key or "",
            model=spec.provider.model,
            temperature=spec.provider.temperature,
            timeout_seconds=spec.provider.timeout_seconds,
            max_retries=spec.provider.max_transport_retries,
        )
        self._credential = settings.openai_api_key
        self._spec = spec
        self._spec_sha256 = spec_sha256
        self._checkpoint_path = checkpoint_path
        self._system_run_id = system_run_id
        self._retry_recorded_errors = retry_recorded_errors
        self._active_call_id: str | None = None
        self._occurrences: Counter[str] = Counter()
        self.resumed_call_ids: list[str] = []
        self.executed_call_ids: list[str] = []
        self._safe_config = safe_provider_config(spec)
        self._safe_config_sha256 = canonical_sha256(self._safe_config)
        self._checkpoint = self._load_or_create_checkpoint()

    @property
    def safe_config_sha256(self) -> str:
        return self._safe_config_sha256

    @property
    def checkpoint(self) -> ProviderRecorderCheckpoint:
        return self._checkpoint

    def calls_for_system_run(self) -> list[RecordedProviderCall]:
        return [
            call
            for call in self._checkpoint.calls.values()
            if call.system_run_id == self._system_run_id
        ]

    def _load_or_create_checkpoint(self) -> ProviderRecorderCheckpoint:
        if self._checkpoint_path.is_file():
            checkpoint = ProviderRecorderCheckpoint.model_validate_json(
                self._checkpoint_path.read_bytes()
            )
            if checkpoint.spec_id != self._spec.spec_id:
                raise ValueError("provider checkpoint spec ID drift")
            if checkpoint.spec_sha256 != self._spec_sha256:
                raise ValueError("provider checkpoint spec SHA drift")
            if checkpoint.safe_provider_config_sha256 != self._safe_config_sha256:
                raise ValueError("provider checkpoint configuration drift")
            return checkpoint
        now = utcnow()
        checkpoint = ProviderRecorderCheckpoint(
            schema_version="threadline-live-provider-recorder/1.0.0",
            spec_id=self._spec.spec_id,
            spec_sha256=self._spec_sha256,
            safe_provider_config=self._safe_config,
            safe_provider_config_sha256=self._safe_config_sha256,
            created_at=now,
            updated_at=now,
        )
        atomic_write_json(self._checkpoint_path, checkpoint)
        return checkpoint

    def _save(self) -> None:
        self._checkpoint.updated_at = utcnow()
        atomic_write_json(self._checkpoint_path, self._checkpoint)

    def _logical_call_identity(
        self,
        *,
        template_id: str,
        template_version: str,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
    ) -> tuple[str, str, str]:
        schema_sha = canonical_sha256(response_model.model_json_schema())
        request_sha = canonical_sha256(
            {
                "system_run_id": self._system_run_id,
                "template_id": template_id,
                "template_version": template_version,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "response_schema_name": response_model.__name__,
                "response_schema_sha256": schema_sha,
                "safe_provider_config_sha256": self._safe_config_sha256,
            }
        )
        self._occurrences[request_sha] += 1
        occurrence = self._occurrences[request_sha]
        call_digest = sha256_bytes(f"{self._system_run_id}|{request_sha}|{occurrence}".encode())[
            :24
        ]
        return f"CALL-{call_digest.upper()}", request_sha, schema_sha

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
        prompt_id = f"{template_id}:{template_version}"
        allowed_prompts = {
            f"{prompt.template_id}:{prompt.version}" for prompt in self._spec.prompts
        }
        if prompt_id not in allowed_prompts:
            raise ValueError(f"provider call used an unpinned prompt: {prompt_id}")
        allowed_schemas = {schema.schema_name for schema in self._spec.output_schemas}
        if response_model.__name__ not in allowed_schemas:
            raise ValueError(
                f"provider call used an unpinned output schema: {response_model.__name__}"
            )
        call_id, request_sha, schema_sha = self._logical_call_identity(
            template_id=template_id,
            template_version=template_version,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
        )
        existing = self._checkpoint.calls.get(call_id)
        if existing is not None:
            if existing.logical_request_sha256 != request_sha:
                raise ValueError(f"recorded request drift for {call_id}")
            if existing.response_schema_sha256 != schema_sha:
                raise ValueError(f"recorded schema drift for {call_id}")
            if existing.status == "ok":
                if existing.validated_output is None or existing.provider_metadata is None:
                    raise ValueError(f"recorded successful call is incomplete: {call_id}")
                output = response_model.model_validate(existing.validated_output)
                metadata = ProviderMetadata.model_validate(existing.provider_metadata)
                self.resumed_call_ids.append(call_id)
                return ProviderResult(output=output, metadata=metadata)
            if not self._retry_recorded_errors:
                error = existing.error
                raise ProviderFailure(
                    error.error_code if error and error.error_code else "RECORDED_PROVIDER_FAILURE",
                    error.message if error else "Recorded provider call did not complete.",
                    retryable=bool(error.retryable) if error else True,
                )

        now = utcnow()
        prior_transport_ids = existing.transport_attempt_ids if existing else []
        call = RecordedProviderCall(
            logical_call_id=call_id,
            system_run_id=self._system_run_id,
            template_id=template_id,
            template_version=template_version,
            response_schema_name=response_model.__name__,
            response_schema_sha256=schema_sha,
            logical_request_sha256=request_sha,
            system_prompt=_safe_value(system_prompt, credential=self._credential),
            user_prompt=_safe_value(user_prompt, credential=self._credential),
            started_at=existing.started_at if existing else now,
            status="in_flight",
            transport_attempt_ids=list(prior_transport_ids),
        )
        self._checkpoint.calls[call_id] = call
        self._active_call_id = call_id
        self.executed_call_ids.append(call_id)
        self._save()
        try:
            result = await super().generate_structured(
                template_id=template_id,
                template_version=template_version,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=response_model,
                mock_payload=mock_payload,
            )
            call.status = "ok"
            call.completed_at = utcnow()
            call.validated_output = _safe_value(result.output, credential=self._credential)
            call.validated_output_sha256 = canonical_sha256(call.validated_output)
            call.provider_metadata = _safe_value(result.metadata, credential=self._credential)
            call.error = None
            self._save()
            return result
        except Exception as exc:
            call.status = "error"
            call.completed_at = utcnow()
            call.error = _provider_error(exc)
            self._save()
            raise
        finally:
            self._active_call_id = None

    async def _do_request(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        call_id = self._active_call_id
        if call_id is None:
            raise RuntimeError("transport request started outside a recorded logical call")
        call = self._checkpoint.calls[call_id]
        ordinal = len(call.transport_attempt_ids) + 1
        attempt_id = f"{call_id}-TRANSPORT-{ordinal:02d}"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": response_format,
            "temperature": self.temperature,
        }
        sanitized_request = _safe_value(payload, credential=self._credential)
        started_at = utcnow()
        attempt = ProviderTransportAttempt(
            attempt_id=attempt_id,
            logical_call_id=call_id,
            started_at=started_at,
            status="in_flight",
            sanitized_request=sanitized_request,
            request_sha256=canonical_sha256(sanitized_request),
        )
        call.transport_attempt_ids.append(attempt_id)
        self._checkpoint.transport_attempts.append(attempt)
        self._save()
        started = perf_counter()
        try:
            response = await super()._do_request(system_prompt, user_prompt, response_format)
            safe_response = _safe_value(response, credential=self._credential)
            attempt.status = "ok"
            attempt.raw_response = safe_response
            attempt.response_sha256 = canonical_sha256(safe_response)
            return response
        except httpx.HTTPStatusError as exc:
            raw_body: Any
            try:
                raw_body = exc.response.json()
            except (json.JSONDecodeError, ValueError):
                raw_body = exc.response.text
            raw_body = _safe_value(raw_body, credential=self._credential)
            attempt.status = "error"
            attempt.error = _provider_error(exc, raw_body=raw_body)
            raise
        except Exception as exc:
            attempt.status = "error"
            attempt.error = _provider_error(exc)
            raise
        finally:
            attempt.completed_at = utcnow()
            attempt.duration_ms = round((perf_counter() - started) * 1000, 3)
            self._save()


def _canonical_field_key(value: str) -> str:
    normalized = normalize_field_key(value)
    return normalized.canonical_key.value if normalized.canonical_key is not None else value


def _one_shot_metrics(
    case: FrozenEvaluationCase,
    output: ReverieOneShotModelOutput,
    *,
    calls: list[RecordedProviderCall],
) -> LiveSystemMetrics:
    records = {record.record_id: record.text for record in case.request.records}
    expected_pairs = {
        (record.record_id, field)
        for record in case.request.records
        for field in RECORD_EXPECTED_FIELDS.get(record.record_id, set())
    }
    valid_expected_pairs: set[tuple[str, str]] = set()
    unsupported_pairs: set[tuple[str, str]] = set()
    exact_citations = 0
    for claim in output.evidence_claims:
        pair = (claim.record_id, claim.field_key.value)
        source = records.get(claim.record_id)
        exact = (
            source is not None
            and claim.end <= len(source)
            and source[claim.start : claim.end] == claim.quote
        )
        if exact:
            exact_citations += 1
        if exact and pair in expected_pairs:
            valid_expected_pairs.add(pair)
        else:
            unsupported_pairs.add(pair)
    outcome = output.classification.value
    attempts = sum(len(call.transport_attempt_ids) for call in calls)
    tokens = sum(int((call.provider_metadata or {}).get("token_usage") or 0) for call in calls)
    return LiveSystemMetrics(
        schema_valid=True,
        available_source_span_count=len(expected_pairs),
        cited_source_span_count=len(output.evidence_claims),
        exact_citation_count=exact_citations,
        invalid_citation_count=len(output.evidence_claims) - exact_citations,
        exact_citation_validity=(
            exact_citations / len(output.evidence_claims) if output.evidence_claims else None
        ),
        source_span_coverage=(
            len(valid_expected_pairs) / len(expected_pairs) if expected_pairs else None
        ),
        supported_field_count=len(valid_expected_pairs),
        unsupported_field_count=len(unsupported_pairs),
        missed_field_count=len(expected_pairs - valid_expected_pairs),
        identity_outcome=outcome,
        outcome_within_accepted_set=(
            output.classification in case.ground_truth.acceptable_one_shot_classifications
        ),
        deterministic_conflict_handling=False,
        provider_call_count=len(calls),
        transport_attempt_count=attempts,
        latency_ms=sum(
            float((call.provider_metadata or {}).get("duration_ms") or 0) for call in calls
        ),
        token_usage=tokens or None,
    )


def _workflow_metrics(
    case: FrozenEvaluationCase,
    response: AnalyzeResponse,
    *,
    calls: list[RecordedProviderCall],
) -> LiveSystemMetrics:
    records = {record.record_id: record.text for record in case.request.records}
    expected_pairs = {
        (record.record_id, field)
        for record in case.request.records
        for field in RECORD_EXPECTED_FIELDS.get(record.record_id, set())
    }
    valid_expected_pairs: set[tuple[str, str]] = set()
    unsupported_pairs: set[tuple[str, str]] = set()
    cited_fields = 0
    exact_citations = 0
    for record in response.records:
        spans = {span.span_id: span for span in record.evidence_spans}
        for field in record.fields:
            if field.value is None or field.unknown:
                continue
            cited_fields += 1
            canonical_key = _canonical_field_key(field.key)
            pair = (record.record_id, canonical_key)
            span = spans.get(field.source_span_id or "")
            source = records.get(record.record_id)
            exact = (
                span is not None
                and span.valid
                and source is not None
                and span.end <= len(source)
                and source[span.start : span.end] == span.quote
            )
            if exact:
                exact_citations += 1
            if exact and pair in expected_pairs:
                valid_expected_pairs.add(pair)
            else:
                unsupported_pairs.add(pair)
    candidate = response.candidates[0] if response.candidates else None
    outcome = (
        candidate.linkage_decision_state or (candidate.linkage_decision or {}).get("state")
        if candidate
        else "insufficient_evidence"
    )
    attempts = sum(len(call.transport_attempt_ids) for call in calls)
    tokens = sum(int((call.provider_metadata or {}).get("token_usage") or 0) for call in calls)
    return LiveSystemMetrics(
        schema_valid=True,
        available_source_span_count=len(expected_pairs),
        cited_source_span_count=cited_fields,
        exact_citation_count=exact_citations,
        invalid_citation_count=cited_fields - exact_citations,
        exact_citation_validity=(exact_citations / cited_fields if cited_fields else None),
        source_span_coverage=(
            len(valid_expected_pairs) / len(expected_pairs) if expected_pairs else None
        ),
        supported_field_count=len(valid_expected_pairs),
        unsupported_field_count=len(unsupported_pairs),
        missed_field_count=len(expected_pairs - valid_expected_pairs),
        identity_outcome=str(outcome),
        outcome_within_accepted_set=str(outcome) in case.ground_truth.acceptable_states,
        deterministic_conflict_handling=True,
        provider_call_count=len(calls),
        transport_attempt_count=attempts,
        latency_ms=sum(
            float((call.provider_metadata or {}).get("duration_ms") or 0) for call in calls
        ),
        token_usage=tokens or None,
    )


def _raw_call_view(
    checkpoint: ProviderRecorderCheckpoint,
    calls: list[RecordedProviderCall],
) -> dict[str, Any]:
    attempts_by_id = {attempt.attempt_id: attempt for attempt in checkpoint.transport_attempts}
    return {
        "provider_calls": [
            {
                "logical_call_id": call.logical_call_id,
                "template_id": call.template_id,
                "template_version": call.template_version,
                "response_schema_name": call.response_schema_name,
                "transport_attempts": [
                    attempts_by_id[attempt_id].model_dump(mode="json")
                    for attempt_id in call.transport_attempt_ids
                    if attempt_id in attempts_by_id
                ],
            }
            for call in calls
        ]
    }


class ReverieLiveEvaluationRunner:
    def __init__(
        self,
        *,
        spec: FrozenLiveEvaluationSpec,
        spec_path: Path,
        spec_sha256: str,
        settings: Settings,
        output_directory: Path,
        retry_errors: bool,
    ) -> None:
        assert_environment_matches_spec(spec, settings)
        self.spec = spec
        self.spec_path = spec_path
        self.spec_sha256 = spec_sha256
        self.settings = settings
        self.output_directory = output_directory
        self.retry_errors = retry_errors
        self.recorder_path = output_directory / "raw-provider-calls.json"
        self.work_state_path = output_directory / "run-state.json"
        self.results_path = output_directory / "results.json"
        self.safe_config = safe_provider_config(spec)
        self.safe_config_sha = canonical_sha256(self.safe_config)
        self.work_state = self._load_or_create_work_state()

    def _load_or_create_work_state(self) -> LiveEvaluationWorkState:
        if self.work_state_path.is_file():
            state = LiveEvaluationWorkState.model_validate_json(self.work_state_path.read_bytes())
            if state.spec_sha256 != self.spec_sha256:
                raise ValueError("run-state spec SHA drift")
            if state.safe_provider_config_sha256 != self.safe_config_sha:
                raise ValueError("run-state provider configuration drift")
            return state
        now = utcnow()
        state = LiveEvaluationWorkState(
            schema_version="threadline-reverie-live-evaluation-work-state/1.0.0",
            spec_id=self.spec.spec_id,
            spec_sha256=self.spec_sha256,
            safe_provider_config_sha256=self.safe_config_sha,
            created_at=now,
            updated_at=now,
        )
        atomic_write_json(self.work_state_path, state)
        return state

    def _save_work_state(self) -> None:
        self.work_state.updated_at = utcnow()
        atomic_write_json(self.work_state_path, self.work_state)

    async def run(self, *, max_system_runs: int | None = None) -> LiveEvaluationArtifact:
        executed = 0
        for repetition, system_order in enumerate(
            self.spec.schedule.system_order_by_repetition, start=1
        ):
            for case in self.spec.cases:
                for system_id in system_order:
                    run_id = f"REP-{repetition:02d}:{case.case_id}:{system_id}"
                    existing = self.work_state.system_runs.get(run_id)
                    if existing and existing.status == "ok":
                        continue
                    if existing and existing.status == "error" and not self.retry_errors:
                        continue
                    if max_system_runs is not None and executed >= max_system_runs:
                        return self.build_artifact()
                    await self._run_system(
                        case=case,
                        repetition=repetition,
                        system_id=system_id,
                        system_run_id=run_id,
                    )
                    executed += 1
                    self.write_artifact()
        return self.write_artifact()

    async def _run_system(
        self,
        *,
        case: FrozenEvaluationCase,
        repetition: int,
        system_id: str,
        system_run_id: str,
    ) -> None:
        provider = RecordingOpenAICompatibleProvider(
            settings=self.settings,
            spec=self.spec,
            spec_sha256=self.spec_sha256,
            checkpoint_path=self.recorder_path,
            system_run_id=system_run_id,
            retry_recorded_errors=self.retry_errors,
        )
        started_at = utcnow()
        result = LiveSystemRunResult(
            system_run_id=system_run_id,
            case_id=case.case_id,
            repetition=repetition,
            system_id=system_id,
            status="not_run",
            input_manifest=case.input_manifest,
            same_input_verified=(
                build_input_manifest(case.request) == case.input_manifest.model_dump()
            ),
            safe_provider_config_sha256=self.safe_config_sha,
            started_at=started_at,
        )
        self.work_state.system_runs[system_run_id] = result
        self._save_work_state()
        try:
            if system_id == "structured_one_shot":
                provider_result = await run_reverie_one_shot(case.request, provider)
                one_shot_output = ReverieOneShotModelOutput.model_validate(provider_result.output)
                calls = provider.calls_for_system_run()
                result.validated_output = one_shot_output.model_dump(mode="json")
                result.raw_output = _raw_call_view(provider.checkpoint, calls)
                result.metrics = _one_shot_metrics(case, one_shot_output, calls=calls)
            elif system_id == "full_threadline":
                workflow_output = await WorkflowOrchestrator(
                    settings=self.settings,
                    provider=provider,
                ).run(case.request)
                calls = provider.calls_for_system_run()
                result.validated_output = workflow_output.model_dump(mode="json")
                result.raw_output = _raw_call_view(provider.checkpoint, calls)
                result.metrics = _workflow_metrics(case, workflow_output, calls=calls)
            else:
                raise ValueError(f"unsupported evaluation system: {system_id}")
            result.status = "ok"
            result.logical_call_ids = [call.logical_call_id for call in calls]
            result.resumed_logical_call_ids = list(provider.resumed_call_ids)
            result.completed_at = utcnow()
        except Exception as exc:
            calls = provider.calls_for_system_run()
            result.status = "error"
            result.logical_call_ids = [call.logical_call_id for call in calls]
            result.resumed_logical_call_ids = list(provider.resumed_call_ids)
            result.error = _provider_error(exc)
            result.completed_at = utcnow()
        finally:
            self._save_work_state()

    def _case_repetitions(self) -> list[LiveCaseRepetition]:
        results: list[LiveCaseRepetition] = []
        for repetition in range(1, self.spec.schedule.repetitions + 1):
            for case in self.spec.cases:
                systems = {
                    result.system_id: result
                    for result in self.work_state.system_runs.values()
                    if result.case_id == case.case_id and result.repetition == repetition
                }
                results.append(
                    LiveCaseRepetition(
                        case_id=case.case_id,
                        kind=case.kind,
                        repetition=repetition,
                        input_manifest=case.input_manifest,
                        systems=systems,
                    )
                )
        return results

    def _aggregate(self) -> dict[str, Any]:
        ok = [result for result in self.work_state.system_runs.values() if result.status == "ok"]
        by_system: dict[str, Any] = {}
        for system_id in ("structured_one_shot", "full_threadline"):
            metrics = [
                result.metrics
                for result in ok
                if result.system_id == system_id and result.metrics is not None
            ]
            by_system[system_id] = {
                "completed_runs": len(metrics),
                "schema_valid_runs": sum(bool(metric.schema_valid) for metric in metrics),
                "outcomes_within_accepted_set": sum(
                    bool(metric.outcome_within_accepted_set) for metric in metrics
                ),
                "invalid_citations": sum(metric.invalid_citation_count for metric in metrics),
                "supported_fields": sum(metric.supported_field_count for metric in metrics),
                "unsupported_fields": sum(metric.unsupported_field_count for metric in metrics),
                "provider_calls": sum(metric.provider_call_count for metric in metrics),
                "transport_attempts": sum(metric.transport_attempt_count for metric in metrics),
                "token_usage": sum(metric.token_usage or 0 for metric in metrics),
                "latency_ms": sum(metric.latency_ms for metric in metrics),
            }
        return {
            "systems": by_system,
            "promotion_or_safety_claim": "Not evaluated by this three-case comparison.",
            "confidence_intervals": "Not measured; three repetitions are reported individually.",
            "approximate_api_cost": "Not measured; no authoritative provider price artifact is pinned.",
        }

    def build_artifact(self) -> LiveEvaluationArtifact:
        expected = self.spec.schedule.repetitions * len(self.spec.cases) * len(self.spec.systems)
        completed = sum(result.status == "ok" for result in self.work_state.system_runs.values())
        failed = sum(result.status == "error" for result in self.work_state.system_runs.values())
        status = (
            "complete"
            if completed == expected and failed == 0
            else "failed"
            if failed and completed == 0
            else "partial"
        )
        if self.recorder_path.is_file():
            recorder_sha = sha256_bytes(self.recorder_path.read_bytes())
        else:
            empty_checkpoint = ProviderRecorderCheckpoint(
                schema_version="threadline-live-provider-recorder/1.0.0",
                spec_id=self.spec.spec_id,
                spec_sha256=self.spec_sha256,
                safe_provider_config=self.safe_config,
                safe_provider_config_sha256=self.safe_config_sha,
                created_at=self.work_state.created_at,
                updated_at=self.work_state.updated_at,
            )
            recorder_sha = atomic_write_json(self.recorder_path, empty_checkpoint)
        return LiveEvaluationArtifact(
            schema_version="threadline-reverie-live-evaluation-results/1.0.0",
            artifact_id="THREADLINE-REVERIE-LIVE-EVAL-RESULTS-V1.1",
            status=status,
            evaluation_label="Measured live-provider comparison",
            synthetic_only=True,
            safety_scope=self.spec.safety_scope,
            spec_id=self.spec.spec_id,
            spec_path=str(self.spec_path).replace("\\", "/"),
            spec_sha256=self.spec_sha256,
            source_commit=self.spec.source_commit,
            provider=self.safe_config,
            same_input_and_config_verified=all(
                result.same_input_verified
                and result.safe_provider_config_sha256 == self.safe_config_sha
                for result in self.work_state.system_runs.values()
            ),
            expected_system_runs=expected,
            completed_system_runs=completed,
            failed_system_runs=failed,
            started_at=self.work_state.created_at,
            updated_at=self.work_state.updated_at,
            completed_at=utcnow() if status == "complete" else None,
            recorder_artifact_path=str(self.recorder_path).replace("\\", "/"),
            recorder_artifact_sha256=recorder_sha,
            cases=self._case_repetitions(),
            aggregate=self._aggregate(),
            limitations=list(self.spec.limitations),
        )

    def write_artifact(self) -> LiveEvaluationArtifact:
        artifact = self.build_artifact()
        atomic_write_json(self.results_path, artifact)
        return artifact
