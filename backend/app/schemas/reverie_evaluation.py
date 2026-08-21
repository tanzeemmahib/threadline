from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from app.schemas.models import (
    AdjudicationModelOutput,
    AnalyzeRequest,
    Certainty,
    Classification,
    ExtractionModelOutput,
    HypothesisModelOutput,
    NormalizationModelOutput,
    ProsecutorModelOutput,
    SingleCallModelOutput,
    StrictModel,
)
from app.services.field_key_normalizer import CanonicalFieldKey

SHA256_PATTERN = r"^[0-9a-f]{64}$"
SPEC_SCHEMA_VERSION = "threadline-reverie-live-evaluation-spec/1.0.0"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json_sha256(value: object) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


class FilePin(StrictModel):
    path: str
    sha256: str = Field(pattern=SHA256_PATTERN)


class PromptPin(FilePin):
    template_id: str
    version: str


class OutputSchemaPin(StrictModel):
    schema_name: str
    sha256: str = Field(pattern=SHA256_PATTERN)


class ProviderPin(StrictModel):
    mode: Literal["openai_compatible"]
    base_url: str
    model: str
    temperature: float
    timeout_seconds: float = Field(gt=0)
    max_transport_retries: int = Field(ge=0)
    max_schema_repair_attempts: Literal[1]
    max_concurrent_calls: Literal[1]
    seed: None = None
    seed_status: Literal["not_supported_by_current_adapter"]
    response_format_policy: Literal["json_schema_then_json_object_fallback"]


class EvaluationSystemPin(StrictModel):
    system_id: Literal["structured_one_shot", "full_threadline"]
    implementation: str
    prompt_ids: list[str] = Field(min_length=1)
    output_schema_names: list[str] = Field(min_length=1)
    decision_authority: Literal["model_recommendation", "deterministic_policy"]


class SupersededSpecPin(StrictModel):
    spec_id: str
    path: str
    sha256: str = Field(pattern=SHA256_PATTERN)
    status: Literal["superseded_before_provider_observation"]
    reason: str


class OneShotEvidenceClaim(StrictModel):
    record_id: str
    field_key: CanonicalFieldKey
    value: str | int | list[str]
    quote: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    certainty: Certainty

    @model_validator(mode="after")
    def verify_offsets(self) -> OneShotEvidenceClaim:
        if self.end <= self.start:
            raise ValueError("claim end must be greater than start")
        return self


class OneShotContradiction(StrictModel):
    field_key: CanonicalFieldKey
    record_ids: list[str] = Field(min_length=2)
    evidence_claim_indexes: list[int] = Field(min_length=1)
    material: bool
    explanation: str


class ReverieOneShotModelOutput(StrictModel):
    evidence_claims: list[OneShotEvidenceClaim]
    candidate_record_ids: list[str]
    classification: Classification
    supporting_evidence_claim_indexes: list[int]
    contradictions: list[OneShotContradiction]
    uncertainty: list[str]
    rationale: str


class InputManifestPin(StrictModel):
    record_count: int = Field(ge=1)
    record_ids: list[str] = Field(min_length=1)
    text_sha256_by_record: dict[str, str]
    input_sha256: str = Field(pattern=SHA256_PATTERN)
    available_evidence_sha256: str = Field(pattern=SHA256_PATTERN)


class CaseGroundTruthPin(StrictModel):
    relation: Literal["same_identity", "different_identity", "genuinely_ambiguous"]
    expected_pair: list[str] = Field(min_length=2, max_length=2)
    expected_state: Literal[
        "link_recommended",
        "human_review_required",
        "insufficient_evidence",
        "blocked_by_conflict",
        "do_not_link",
    ]
    acceptable_states: list[str] = Field(min_length=1)
    acceptable_one_shot_classifications: list[Classification] = Field(default_factory=list)
    expected_blocking: list[str]
    safety_rationale: str


class FrozenEvaluationCase(StrictModel):
    case_id: str
    kind: Literal[
        "cross_script_partial",
        "shared_contact_insufficient",
        "blocking_identity_conflict",
    ]
    fixture_incident_id: str
    input_manifest: InputManifestPin
    request: AnalyzeRequest
    ground_truth: CaseGroundTruthPin

    @model_validator(mode="after")
    def verify_input_manifest(self) -> FrozenEvaluationCase:
        records = [
            {"record_id": record.record_id, "text": record.text} for record in self.request.records
        ]
        complete_evidence = [record.model_dump(mode="json") for record in self.request.records]
        manifest = self.input_manifest
        if manifest.record_count != len(records):
            raise ValueError("input manifest record_count does not match request")
        if manifest.record_ids != [record["record_id"] for record in records]:
            raise ValueError("input manifest record_ids do not match request order")
        text_hashes = {
            record["record_id"]: _sha256_bytes(record["text"].encode("utf-8")) for record in records
        }
        if manifest.text_sha256_by_record != text_hashes:
            raise ValueError("input manifest text hashes do not match request")
        if manifest.input_sha256 != _canonical_json_sha256(records):
            raise ValueError("input manifest input_sha256 does not match request")
        if manifest.available_evidence_sha256 != _canonical_json_sha256(complete_evidence):
            raise ValueError("available evidence hash does not match request")
        if self.fixture_incident_id != self.request.incident.incident_id:
            raise ValueError("fixture incident ID does not match request")
        if self.ground_truth.expected_pair != manifest.record_ids:
            raise ValueError("ground-truth pair must preserve frozen request order")
        return self


class SchedulePin(StrictModel):
    repetitions: Literal[3]
    case_order: list[str] = Field(min_length=1)
    system_order_by_repetition: list[list[Literal["structured_one_shot", "full_threadline"]]]
    checkpoint_granularity: Literal["provider_call"]
    retry_policy: Literal["identical_for_both_systems"]

    @model_validator(mode="after")
    def verify_schedule(self) -> SchedulePin:
        if len(self.system_order_by_repetition) != self.repetitions:
            raise ValueError("one system order is required for every repetition")
        expected = {"structured_one_shot", "full_threadline"}
        if any(
            set(order) != expected or len(order) != 2 for order in self.system_order_by_repetition
        ):
            raise ValueError("every repetition must run both systems exactly once")
        return self


class EvaluationPolicyPin(StrictModel):
    ground_truth_visible_to_provider: Literal[False]
    thresholds_mutable: Literal[False]
    raw_provider_content_retained: Literal[True]
    authorization_headers_retained: Literal[False]
    exact_source_span_validation_required: Literal[True]
    partial_run_publishable_as_complete: Literal[False]


class FrozenLiveEvaluationSpec(StrictModel):
    schema_version: Literal[
        "threadline-reverie-live-evaluation-spec/1.0.0",
        "threadline-reverie-live-evaluation-spec/1.1.0",
    ]
    spec_id: str
    frozen_at: str
    synthetic_only: Literal[True]
    safety_scope: str
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree_state: Literal["dirty_at_freeze"]
    supersedes: SupersededSpecPin | None = None
    origin_artifact: FilePin
    fixture: FilePin
    identity_assignments: FilePin
    identity_assignment_canonical_sha256: str = Field(pattern=SHA256_PATTERN)
    source_files: list[FilePin] = Field(min_length=1)
    prompts: list[PromptPin] = Field(min_length=1)
    output_schemas: list[OutputSchemaPin] = Field(min_length=1)
    provider: ProviderPin
    systems: list[EvaluationSystemPin] = Field(min_length=2, max_length=2)
    schedule: SchedulePin
    evaluation_policy: EvaluationPolicyPin
    metrics: list[str] = Field(min_length=1)
    metric_definitions: dict[str, str] = Field(default_factory=dict)
    cases: list[FrozenEvaluationCase] = Field(min_length=3, max_length=3)
    limitations: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def verify_cross_references(self) -> FrozenLiveEvaluationSpec:
        if self.schema_version.endswith("/1.1.0") and self.supersedes is None:
            raise ValueError("a v1.1 spec must identify the preregistration draft it supersedes")
        if self.schema_version.endswith("/1.1.0") and any(
            not case.ground_truth.acceptable_one_shot_classifications for case in self.cases
        ):
            raise ValueError("a v1.1 case must declare acceptable one-shot classifications")
        if self.schema_version.endswith("/1.1.0") and set(self.metrics) != set(
            self.metric_definitions
        ):
            raise ValueError("a v1.1 spec must define every registered metric exactly once")
        if self.schema_version.endswith("/1.0.0") and self.supersedes is not None:
            raise ValueError("the original v1 spec cannot supersede another spec")
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("case IDs must be unique")
        if self.schedule.case_order != case_ids:
            raise ValueError("schedule case order must equal frozen case order")
        system_ids = [system.system_id for system in self.systems]
        if set(system_ids) != {"structured_one_shot", "full_threadline"}:
            raise ValueError("spec must include the one-shot and full THREADLINE systems")
        prompt_ids = {f"{prompt.template_id}:{prompt.version}" for prompt in self.prompts}
        schema_names = {schema.schema_name for schema in self.output_schemas}
        for system in self.systems:
            if not set(system.prompt_ids).issubset(prompt_ids):
                raise ValueError(f"unknown prompt pin referenced by {system.system_id}")
            if not set(system.output_schema_names).issubset(schema_names):
                raise ValueError(f"unknown output schema pin referenced by {system.system_id}")
        return self


OUTPUT_SCHEMA_TYPES: dict[str, type[StrictModel]] = {
    "ReverieOneShotModelOutput": ReverieOneShotModelOutput,
    "SingleCallModelOutput": SingleCallModelOutput,
    "ExtractionModelOutput": ExtractionModelOutput,
    "NormalizationModelOutput": NormalizationModelOutput,
    "HypothesisModelOutput": HypothesisModelOutput,
    "ProsecutorModelOutput": ProsecutorModelOutput,
    "AdjudicationModelOutput": AdjudicationModelOutput,
}


def load_frozen_live_evaluation_spec(
    path: Path,
    *,
    repository_root: Path,
    verify_origin_artifact: bool = True,
) -> tuple[FrozenLiveEvaluationSpec, str]:
    """Load a live-evaluation spec and fail closed on any pinned-source drift."""

    raw = path.read_bytes()
    spec = FrozenLiveEvaluationSpec.model_validate_json(raw)
    pins = [spec.fixture, spec.identity_assignments, *spec.source_files, *spec.prompts]
    if verify_origin_artifact:
        pins.insert(0, spec.origin_artifact)
    seen: set[str] = set()
    for pin in pins:
        if pin.path in seen:
            continue
        seen.add(pin.path)
        source_path = (repository_root / pin.path).resolve()
        if not source_path.is_relative_to(repository_root.resolve()):
            raise ValueError(f"pinned path escapes repository root: {pin.path}")
        if not source_path.is_file():
            raise ValueError(f"pinned source file is missing: {pin.path}")
        observed = _sha256_bytes(source_path.read_bytes())
        if observed != pin.sha256:
            raise ValueError(f"pinned source drift: {pin.path}")
    for schema_pin in spec.output_schemas:
        schema_type = OUTPUT_SCHEMA_TYPES.get(schema_pin.schema_name)
        if schema_type is None:
            raise ValueError(f"unsupported output schema: {schema_pin.schema_name}")
        observed = _canonical_json_sha256(schema_type.model_json_schema())
        if observed != schema_pin.sha256:
            raise ValueError(f"output schema drift: {schema_pin.schema_name}")
    return spec, _sha256_bytes(raw)


class SanitizedProviderError(StrictModel):
    error_class: str
    error_code: str | None = None
    message: str
    http_status: int | None = None
    retryable: bool | None = None
    raw_body: Any | None = None


class ProviderTransportAttempt(StrictModel):
    attempt_id: str
    logical_call_id: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: float | None = None
    status: Literal["in_flight", "ok", "error"]
    sanitized_request: dict[str, Any]
    request_sha256: str = Field(pattern=SHA256_PATTERN)
    raw_response: Any | None = None
    response_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    error: SanitizedProviderError | None = None


class RecordedProviderCall(StrictModel):
    logical_call_id: str
    system_run_id: str
    template_id: str
    template_version: str
    response_schema_name: str
    response_schema_sha256: str = Field(pattern=SHA256_PATTERN)
    logical_request_sha256: str = Field(pattern=SHA256_PATTERN)
    system_prompt: str
    user_prompt: str
    started_at: datetime
    completed_at: datetime | None = None
    status: Literal["in_flight", "ok", "error"]
    transport_attempt_ids: list[str] = Field(default_factory=list)
    validated_output: dict[str, Any] | None = None
    validated_output_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    provider_metadata: dict[str, Any] | None = None
    error: SanitizedProviderError | None = None


class ProviderRecorderCheckpoint(StrictModel):
    schema_version: Literal["threadline-live-provider-recorder/1.0.0"]
    spec_id: str
    spec_sha256: str = Field(pattern=SHA256_PATTERN)
    safe_provider_config: dict[str, Any]
    safe_provider_config_sha256: str = Field(pattern=SHA256_PATTERN)
    created_at: datetime
    updated_at: datetime
    calls: dict[str, RecordedProviderCall] = Field(default_factory=dict)
    transport_attempts: list[ProviderTransportAttempt] = Field(default_factory=list)
    contains_credentials: Literal[False] = False


class LiveSystemMetrics(StrictModel):
    schema_valid: bool
    available_source_span_count: int = Field(ge=0)
    cited_source_span_count: int = Field(ge=0)
    exact_citation_count: int = Field(ge=0)
    invalid_citation_count: int = Field(ge=0)
    exact_citation_validity: float | None = Field(default=None, ge=0, le=1)
    source_span_coverage: float | None = Field(default=None, ge=0, le=1)
    supported_field_count: int = Field(ge=0)
    unsupported_field_count: int = Field(ge=0)
    missed_field_count: int = Field(ge=0)
    identity_outcome: str
    outcome_within_accepted_set: bool
    deterministic_conflict_handling: bool
    provider_call_count: int = Field(ge=0)
    transport_attempt_count: int = Field(ge=0)
    latency_ms: float = Field(ge=0)
    token_usage: int | None = Field(default=None, ge=0)


class LiveSystemRunResult(StrictModel):
    system_run_id: str
    case_id: str
    repetition: int = Field(ge=1)
    system_id: Literal["structured_one_shot", "full_threadline"]
    status: Literal["ok", "error", "not_run"]
    input_manifest: InputManifestPin
    same_input_verified: bool
    safe_provider_config_sha256: str = Field(pattern=SHA256_PATTERN)
    logical_call_ids: list[str] = Field(default_factory=list)
    resumed_logical_call_ids: list[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime | None = None
    raw_output: dict[str, Any] | None = None
    validated_output: dict[str, Any] | None = None
    metrics: LiveSystemMetrics | None = None
    error: SanitizedProviderError | None = None


class LiveCaseRepetition(StrictModel):
    case_id: str
    kind: str
    repetition: int = Field(ge=1)
    input_manifest: InputManifestPin
    systems: dict[str, LiveSystemRunResult]


class LiveEvaluationWorkState(StrictModel):
    schema_version: Literal["threadline-reverie-live-evaluation-work-state/1.0.0"]
    spec_id: str
    spec_sha256: str = Field(pattern=SHA256_PATTERN)
    safe_provider_config_sha256: str = Field(pattern=SHA256_PATTERN)
    created_at: datetime
    updated_at: datetime
    system_runs: dict[str, LiveSystemRunResult] = Field(default_factory=dict)


class LiveEvaluationArtifact(StrictModel):
    schema_version: Literal["threadline-reverie-live-evaluation-results/1.0.0"]
    artifact_id: str
    status: Literal["complete", "partial", "failed"]
    evaluation_label: Literal["Measured live-provider comparison"]
    synthetic_only: Literal[True]
    safety_scope: str
    spec_id: str
    spec_path: str
    spec_sha256: str = Field(pattern=SHA256_PATTERN)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    provider: dict[str, Any]
    same_input_and_config_verified: bool
    expected_system_runs: int = Field(ge=1)
    completed_system_runs: int = Field(ge=0)
    failed_system_runs: int = Field(ge=0)
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    recorder_artifact_path: str
    recorder_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    cases: list[LiveCaseRepetition]
    aggregate: dict[str, Any]
    limitations: list[str]
