"""Strict, versioned schemas and provenance checks for Reverie judge artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.reverie_evaluation import (
    LiveEvaluationArtifact,
    ProviderRecorderCheckpoint,
    load_frozen_live_evaluation_spec,
)

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class StrictArtifactModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PromptLabInputManifest(StrictArtifactModel):
    record_count: int = Field(ge=1)
    record_ids: list[str] = Field(min_length=1)
    text_sha256_by_record: dict[str, str]
    input_sha256: str = Field(pattern=SHA256_PATTERN)
    available_evidence_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def verify_record_ids(self) -> PromptLabInputManifest:
        if len(self.record_ids) != self.record_count:
            raise ValueError("input manifest record count drift")
        if len(set(self.record_ids)) != self.record_count:
            raise ValueError("input manifest record IDs are not unique")
        if set(self.text_sha256_by_record) != set(self.record_ids):
            raise ValueError("input manifest text hashes do not cover its records")
        if any(
            len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
            for value in self.text_sha256_by_record.values()
        ):
            raise ValueError("input manifest contains an invalid text SHA-256")
        return self


class PromptLabSourceSpan(StrictArtifactModel):
    span_id: str
    record_id: str
    field: str
    quote: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    certainty: Literal["exact", "estimated", "translated", "inferred", "missing"]
    extraction_method: str
    valid: bool
    validation_error: str | None

    @model_validator(mode="after")
    def verify_offsets(self) -> PromptLabSourceSpan:
        if self.end <= self.start:
            raise ValueError("source span end must follow start")
        if len(self.quote) != self.end - self.start:
            raise ValueError("source span quote length does not match its offsets")
        return self


class ArchivedLiveExtraction(StrictArtifactModel):
    evidence_track: Literal["archived_live_provider_extraction"]
    run_id: str
    prompt_version: str
    status: str
    attempts: int = Field(ge=0)
    latency_ms: float | None = Field(default=None, ge=0)
    token_usage: int | None = Field(default=None, ge=0)
    fields: list[dict[str, Any]]
    raw_provider_output: Any
    expected_field_keys: list[str]
    supported_field_keys: list[str]
    unsupported_field_keys: list[str]
    missed_field_keys: list[str]


class PromptLabRecord(StrictArtifactModel):
    record_id: str
    source_type: str
    language: str
    text: str
    timestamp: str | None
    display_name: str | None
    source_reliability_metadata: str | None
    translated_text: str | None
    source_organization: str | None
    created_at: str | None
    event_time: str | None
    provenance_metadata: dict[str, Any]
    reliability_metadata: dict[str, Any]
    ingestion_hash: str | None
    text_sha256: str = Field(pattern=SHA256_PATTERN)
    archived_live_v2_extraction: ArchivedLiveExtraction


class WinningStoryRecord(StrictArtifactModel):
    record_id: str
    source_type: str
    language: str
    text: str


class PromptPinArtifact(StrictArtifactModel):
    template_id: str
    version: str
    sha256: str = Field(pattern=SHA256_PATTERN)
    source_path: str
    text: str


class PromptLabModelConfig(StrictArtifactModel):
    provider: Literal["mock"]
    model: Literal["deterministic-fixture"]
    temperature: float
    network_required: Literal[False]


class PromptLabSystemMetrics(StrictArtifactModel):
    schema_valid: bool
    supported_field_count: int = Field(ge=0)
    unsupported_field_count: int = Field(ge=0)
    exact_citation_count: int = Field(ge=0)
    available_source_span_count: int = Field(ge=0)
    source_span_coverage: float | None = Field(default=None, ge=0, le=1)


class PromptLabSystemResult(StrictArtifactModel):
    system_id: str
    system_name: str
    evaluation_label: Literal["Deterministic mock replay - not model performance."]
    classification: str
    candidate_record_ids: list[str]
    model_calls: int = Field(ge=0)
    prompt: PromptPinArtifact
    provider_config: PromptLabModelConfig = Field(
        alias="model_config", serialization_alias="model_config"
    )
    raw_provider_output: dict[str, Any] | None
    validated_structured_output: dict[str, Any]
    metrics: PromptLabSystemMetrics
    cited_evidence: list[PromptLabSourceSpan]
    candidate: dict[str, Any] | None
    evidence_contract: dict[str, Any] | None
    workflow_trace: list[dict[str, Any]]


class PromptLabDecision(StrictArtifactModel):
    state: str
    reason_codes: list[str]
    blocking_conflicts: list[dict[str, Any]]
    release_allowed_for_authorized_review: bool
    safety_notice: str


class PromptLabCase(StrictArtifactModel):
    case_id: str
    kind: Literal[
        "cross_script_partial",
        "shared_contact_insufficient",
        "blocking_identity_conflict",
    ]
    fixture_incident_id: str
    title: str
    question: str
    synthetic_only: Literal[True]
    ground_truth: dict[str, Any]
    input_manifest: PromptLabInputManifest
    identical_input_verified: Literal[True]
    records: list[PromptLabRecord] = Field(min_length=2)
    source_spans: list[PromptLabSourceSpan] = Field(min_length=1)
    systems: dict[str, PromptLabSystemResult]
    comparison_dimensions: dict[str, Any]
    decision: PromptLabDecision

    @model_validator(mode="after")
    def verify_systems(self) -> PromptLabCase:
        if set(self.systems) != {"one_shot", "threadline"}:
            raise ValueError("Prompt Lab case must contain one-shot and THREADLINE systems")
        return self


class WinningContractProvenance(StrictArtifactModel):
    contract_id: str
    candidate_id: str
    contract_status: str
    release_allowed_for_authorized_review: bool


class WinningAuditIntegrity(StrictArtifactModel):
    status: Literal["verified"]
    valid: Literal[True]
    verified_event_count: int = Field(ge=1)
    terminal_hash: str = Field(pattern=SHA256_PATTERN)
    hash_algorithm: Literal["sha256"]
    verifier_version: str
    limitation: str


class WinningReplayManifest(StrictArtifactModel):
    manifest_version: str
    original_input_package_hash: str = Field(pattern=SHA256_PATTERN)
    configuration_hash: str = Field(pattern=SHA256_PATTERN)
    prompt_template_versions: dict[str, str]
    model_identifiers: list[str]
    final_candidate_set_hash: str = Field(pattern=SHA256_PATTERN)
    final_contract_hash: str = Field(pattern=SHA256_PATTERN)
    final_response_hash: str = Field(pattern=SHA256_PATTERN)
    audit_chain_terminal_hash: str = Field(pattern=SHA256_PATTERN)


class WinningStoryProvenance(StrictArtifactModel):
    workflow_run_id: str
    case_id: str
    evidence_contracts: list[WinningContractProvenance]
    audit_integrity: WinningAuditIntegrity
    replay_manifest: WinningReplayManifest
    replay_certificate: dict[str, Any] | Literal["Not recorded"]
    export_artifact: dict[str, Any] | Literal["Not recorded"]


class PromptLabWinningStory(StrictArtifactModel):
    case_id: Literal["THREADLINE-WINNING-STORY-V1"]
    scenario: Literal["rival"]
    synthetic_only: Literal[True]
    input_manifest: PromptLabInputManifest
    records: list[WinningStoryRecord] = Field(min_length=3)
    source_spans: list[PromptLabSourceSpan] = Field(min_length=1)
    candidates: list[dict[str, Any]] = Field(min_length=2)
    evidence_contracts: list[dict[str, Any]] = Field(min_length=2)
    provenance: WinningStoryProvenance
    supported_pair: list[str] = Field(min_length=2, max_length=2)
    blocked_rival_pair: list[str] = Field(min_length=2, max_length=2)
    language_limitation: str
    climax: str


class PromptIterationRun(StrictArtifactModel):
    run_id: str
    execution_mode: str
    provider: str
    model: str
    temperature: float
    prompt_version: str
    prompt_sha256: str = Field(pattern=SHA256_PATTERN)
    fixture_sha256: str = Field(pattern=SHA256_PATTERN)
    run_timestamp_utc: str
    record_count: int = Field(ge=1)
    extraction_quality: dict[str, Any]
    decision_metrics: dict[str, Any]
    retrieval: dict[str, Any] | None
    safety: dict[str, Any]
    operational: dict[str, Any]
    source_files: dict[str, str]


class PromptIterationCohort(StrictArtifactModel):
    cohort_id: str
    comparable_versions: list[str] = Field(min_length=2)
    runs: list[PromptIterationRun] = Field(min_length=2)
    interpretation: str


class PromptPromotionDecision(StrictArtifactModel):
    production_version: Literal["v2"]
    not_promoted: Literal["v3"]
    reason_code: Literal["PRECISION_REGRESSION"]
    same_full_cohort: Literal[True]
    v2_precision: float = Field(ge=0, le=1)
    v3_precision: float = Field(ge=0, le=1)
    v2_recall: float = Field(ge=0, le=1)
    v3_recall: float = Field(ge=0, le=1)
    v2_f1: float = Field(ge=0, le=1)
    v3_f1: float = Field(ge=0, le=1)
    v2_false_positive_fields: int = Field(ge=0)
    v3_false_positive_fields: int = Field(ge=0)


class PromptIterations(StrictArtifactModel):
    headline: str
    cohorts: list[PromptIterationCohort] = Field(min_length=2)
    prompt_summaries: dict[str, str]
    prompts: dict[str, PromptPinArtifact]
    promotion_decision: PromptPromotionDecision
    comparison_limit: str


class PromptLabArtifact(StrictArtifactModel):
    artifact_id: Literal["THREADLINE-REVERIE-PROMPT-LAB-V1"]
    schema_version: Literal["threadline-reverie-prompt-lab/1.0.0"]
    generated_at: str
    timestamp_basis: str
    synthetic_only: Literal[True]
    safety_scope: str
    source_artifacts: dict[str, str]
    winning_story: PromptLabWinningStory
    cases: list[PromptLabCase] = Field(min_length=3, max_length=3)
    prompt_iterations: PromptIterations
    limitations: list[str] = Field(min_length=1)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolved_source(repository_root: Path, relative_path: str) -> Path:
    path = (repository_root / relative_path).resolve()
    try:
        path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ValueError(f"Prompt Lab source path escapes repository: {relative_path}") from exc
    if not path.is_file():
        raise ValueError(f"Prompt Lab source is missing: {relative_path}")
    return path


def _records_input_sha(records: list[PromptLabRecord] | list[WinningStoryRecord]) -> str:
    encoded = json.dumps(
        [{"record_id": record.record_id, "text": record.text} for record in records],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _verify_manifest(
    manifest: PromptLabInputManifest,
    records: list[PromptLabRecord] | list[WinningStoryRecord],
) -> None:
    if [record.record_id for record in records] != manifest.record_ids:
        raise ValueError("Prompt Lab record order/IDs drifted from the input manifest")
    if _records_input_sha(records) != manifest.input_sha256:
        raise ValueError("Prompt Lab identical-input SHA does not match its records")
    for record in records:
        observed = hashlib.sha256(record.text.encode("utf-8")).hexdigest()
        if observed != manifest.text_sha256_by_record[record.record_id]:
            raise ValueError(f"Prompt Lab text SHA drift for {record.record_id}")
        if isinstance(record, PromptLabRecord) and observed != record.text_sha256:
            raise ValueError(f"Prompt Lab record text SHA drift for {record.record_id}")


def _verify_spans(
    records: list[PromptLabRecord] | list[WinningStoryRecord],
    spans: list[PromptLabSourceSpan],
) -> None:
    record_text = {record.record_id: record.text for record in records}
    if len({span.span_id for span in spans}) != len(spans):
        raise ValueError("Prompt Lab source span IDs are not unique")
    for span in spans:
        source = record_text.get(span.record_id)
        if source is None or span.end > len(source):
            raise ValueError(f"Prompt Lab span references missing source: {span.span_id}")
        if source[span.start : span.end] != span.quote:
            raise ValueError(f"Prompt Lab source span drift: {span.span_id}")
        if not span.valid or span.validation_error is not None:
            raise ValueError(f"Prompt Lab published an invalid source span: {span.span_id}")


def validate_prompt_lab_artifact(artifact: PromptLabArtifact, *, repository_root: Path) -> None:
    for relative_path, expected_sha in artifact.source_artifacts.items():
        if _sha256_file(_resolved_source(repository_root, relative_path)) != expected_sha:
            raise ValueError(f"Prompt Lab source artifact SHA drift: {relative_path}")

    expected_kinds = {
        "cross_script_partial",
        "shared_contact_insufficient",
        "blocking_identity_conflict",
    }
    if {case.kind for case in artifact.cases} != expected_kinds:
        raise ValueError("Prompt Lab cases do not cover the frozen three-case design")
    if len({case.case_id for case in artifact.cases}) != len(artifact.cases):
        raise ValueError("Prompt Lab case IDs are not unique")
    for case in artifact.cases:
        _verify_manifest(case.input_manifest, case.records)
        _verify_spans(case.records, case.source_spans)
        for system in case.systems.values():
            if system.candidate_record_ids != case.input_manifest.record_ids:
                raise ValueError(f"Prompt Lab systems received different input: {case.case_id}")
            _verify_spans(case.records, system.cited_evidence)
            if system.metrics.exact_citation_count != len(system.cited_evidence):
                raise ValueError(f"Prompt Lab citation metric drift: {case.case_id}")
            if system.metrics.available_source_span_count != len(case.source_spans):
                raise ValueError(f"Prompt Lab citation denominator drift: {case.case_id}")
        if (
            case.kind in {"cross_script_partial", "shared_contact_insufficient"}
            and case.decision.state == "link_recommended"
        ):
            raise ValueError(f"unsafe autonomous link state in {case.case_id}")
        if case.kind == "blocking_identity_conflict" and (
            case.decision.state != "blocked_by_conflict"
            or case.decision.release_allowed_for_authorized_review
            or not case.decision.blocking_conflicts
        ):
            raise ValueError("blocking-conflict case lost its deterministic stop")

    story = artifact.winning_story
    _verify_manifest(story.input_manifest, story.records)
    _verify_spans(story.records, story.source_spans)
    if story.provenance.audit_integrity.terminal_hash != (
        story.provenance.replay_manifest.audit_chain_terminal_hash
    ):
        raise ValueError("winning-story audit and replay terminal hashes differ")
    candidates = {
        frozenset(candidate.get("record_ids", [])): candidate for candidate in story.candidates
    }
    supported = candidates.get(frozenset(story.supported_pair))
    blocked = candidates.get(frozenset(story.blocked_rival_pair))
    if not supported or (supported.get("linkage_decision") or {}).get("state") != (
        "link_recommended"
    ):
        raise ValueError("winning-story supported pair provenance drift")
    if not blocked or (blocked.get("linkage_decision") or {}).get("state") != (
        "blocked_by_conflict"
    ):
        raise ValueError("winning-story blocked-rival provenance drift")

    iterations = artifact.prompt_iterations
    if set(iterations.prompts) != {"v1", "v2", "v3"}:
        raise ValueError("Prompt Lab prompt-version set drift")
    for version, prompt in iterations.prompts.items():
        if prompt.version != version:
            raise ValueError(f"Prompt Lab prompt version drift: {version}")
        if _sha256_file(_resolved_source(repository_root, prompt.source_path)) != prompt.sha256:
            raise ValueError(f"Prompt Lab prompt SHA drift: {version}")
    for cohort in iterations.cohorts:
        if [run.prompt_version for run in cohort.runs] != cohort.comparable_versions:
            raise ValueError(f"Prompt Lab cohort version order drift: {cohort.cohort_id}")
        for run in cohort.runs:
            for relative_path, expected_sha in run.source_files.items():
                if _sha256_file(_resolved_source(repository_root, relative_path)) != expected_sha:
                    raise ValueError(f"Prompt Lab run source SHA drift: {relative_path}")
    promotion = iterations.promotion_decision
    if not (
        promotion.v3_precision < promotion.v2_precision
        and promotion.v3_f1 < promotion.v2_f1
        and promotion.v3_false_positive_fields > promotion.v2_false_positive_fields
    ):
        raise ValueError("Prompt V3 precision-regression decision no longer matches metrics")


def load_prompt_lab_artifact(path: Path, *, repository_root: Path) -> PromptLabArtifact:
    artifact = PromptLabArtifact.model_validate_json(path.read_bytes())
    validate_prompt_lab_artifact(artifact, repository_root=repository_root)
    return artifact


def _repository_artifact_path(repository_root: Path, value: str) -> Path:
    candidate = Path(value)
    path = (candidate if candidate.is_absolute() else repository_root / candidate).resolve()
    try:
        path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise ValueError(f"Reverie artifact path escapes repository: {value}") from exc
    return path


def load_live_evaluation_artifact(path: Path, *, repository_root: Path) -> LiveEvaluationArtifact:
    artifact = LiveEvaluationArtifact.model_validate_json(path.read_bytes())
    spec_path = _repository_artifact_path(repository_root, artifact.spec_path)
    spec, spec_sha = load_frozen_live_evaluation_spec(spec_path, repository_root=repository_root)
    if artifact.spec_sha256 != spec_sha or artifact.spec_id != spec.spec_id:
        raise ValueError("live result does not match its validated frozen spec")
    if artifact.source_commit != spec.source_commit:
        raise ValueError("live result source commit drift")

    recorder_path = _repository_artifact_path(repository_root, artifact.recorder_artifact_path)
    recorder_bytes = recorder_path.read_bytes()
    if hashlib.sha256(recorder_bytes).hexdigest() != artifact.recorder_artifact_sha256:
        raise ValueError("live result recorder SHA drift")
    recorder = ProviderRecorderCheckpoint.model_validate_json(recorder_bytes)
    if recorder.contains_credentials:
        raise ValueError("live result recorder contains credentials")
    if recorder.spec_sha256 != spec_sha or recorder.spec_id != spec.spec_id:
        raise ValueError("live result recorder belongs to another frozen spec")
    if artifact.provider != recorder.safe_provider_config:
        raise ValueError("live result provider configuration drift")

    frozen_cases = {case.case_id: case for case in spec.cases}
    expected_case_repetitions = {
        (case.case_id, repetition)
        for case in spec.cases
        for repetition in range(1, spec.schedule.repetitions + 1)
    }
    if {(case.case_id, case.repetition) for case in artifact.cases} != (
        expected_case_repetitions
    ) or len(artifact.cases) != len(expected_case_repetitions):
        raise ValueError("live result case/repetition schedule drift")
    for case_repetition in artifact.cases:
        frozen = frozen_cases[case_repetition.case_id]
        if case_repetition.input_manifest != frozen.input_manifest:
            raise ValueError("live result case input manifest drift")
        for system_id, run in case_repetition.systems.items():
            if system_id not in {system.system_id for system in spec.systems}:
                raise ValueError("live result contains an unknown system")
            if (
                run.input_manifest != frozen.input_manifest
                or not run.same_input_verified
                or run.safe_provider_config_sha256 != recorder.safe_provider_config_sha256
            ):
                raise ValueError("live result contains an unverified system input/config")
            for call_id in run.logical_call_ids:
                call = recorder.calls.get(call_id)
                if call is None or call.system_run_id != run.system_run_id:
                    raise ValueError("live result references missing or foreign provider call")
    if artifact.status == "complete":
        expected_runs = spec.schedule.repetitions * len(spec.cases) * len(spec.systems)
        observed_runs = [
            run for case_repetition in artifact.cases for run in case_repetition.systems.values()
        ]
        if (
            artifact.expected_system_runs != expected_runs
            or artifact.completed_system_runs != expected_runs
            or artifact.failed_system_runs != 0
            or len(observed_runs) != expected_runs
            or any(run.status != "ok" or run.metrics is None for run in observed_runs)
        ):
            raise ValueError("complete live result does not cover every frozen system run")
    return artifact
