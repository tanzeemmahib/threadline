from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SAFETY_NOTICE = (
    "THREADLINE proposes candidate record connections for authorized human review and "
    "does not autonomously determine identity."
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Certainty(StrEnum):
    exact = "exact"
    estimated = "estimated"
    translated = "translated"
    inferred = "inferred"
    missing = "missing"


class Classification(StrEnum):
    strong_candidate_for_review = "strong_candidate_for_review"
    possible_candidate = "possible_candidate"
    insufficient_evidence = "insufficient_evidence"
    conflicting_evidence = "conflicting_evidence"


class ProviderMode(StrEnum):
    mock = "mock"
    openai_compatible = "openai_compatible"


class IncidentInput(StrictModel):
    incident_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    languages: list[str] = Field(min_length=1)
    description: str | None = None
    approximate_region: str | None = None
    known_locations: list[str] = Field(default_factory=list)
    time_window: str | None = None
    reviewer_constraints: list[str] = Field(default_factory=list)


class RecordInput(StrictModel):
    record_id: str = Field(min_length=1, max_length=100)
    source_type: str = Field(min_length=1, max_length=100)
    language: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1)
    timestamp: datetime | None = None
    display_name: str | None = None
    source_reliability_metadata: str | None = None
    translated_text: str | None = None


class AnalyzeOptions(StrictModel):
    provider_mode: ProviderMode = ProviderMode.mock
    include_workflow_trace: bool = True
    candidate_limit: int = Field(default=5, ge=1, le=10)
    disabled_nodes: list[str] = Field(default_factory=list)
    adjudicator_count: int = Field(default=2, ge=1, le=3)

    @field_validator("disabled_nodes")
    @classmethod
    def normalize_disabled_node_names(cls, value: list[str]) -> list[str]:
        aliases = {
            "evidence_quarantine": "quarantine",
            "normalization": "normalize",
            "multilingual_normalization": "normalize",
            "timeline_reconstruction": "timeline",
            "contradiction_prosecutor": "prosecutor",
            "rival_candidate_test": "rivals",
            "independent_adjudication": "adjudicate",
            "privacy_gate": "privacy",
        }
        return [aliases.get(item, item) for item in value]


class AnalyzeRequest(StrictModel):
    incident: IncidentInput
    records: list[RecordInput] = Field(min_length=1)
    options: AnalyzeOptions = Field(default_factory=AnalyzeOptions)

    @model_validator(mode="after")
    def unique_record_ids(self) -> AnalyzeRequest:
        record_ids = [record.record_id for record in self.records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("record_id values must be unique")
        return self


class EvidenceSpan(StrictModel):
    span_id: str
    record_id: str
    field: str
    quote: str
    text: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    certainty: Certainty
    extraction_method: str
    extraction_status: Literal["extracted", "review_required", "quarantined"] = "extracted"
    normalization_note: str | None = None
    valid: bool = True
    validation_error: str | None = None


class ExtractedField(StrictModel):
    field_id: str
    key: str
    label: str
    value: str | int | list[str] | None
    normalized_value: str | None = None
    certainty: Certainty
    source_span_id: str | None = None
    unknown: bool = False


class NormalizedRecord(StrictModel):
    record_id: str
    source_type: str
    language: str
    text: str
    timestamp: datetime | None = None
    display_name: str
    status: Literal["unresolved", "candidate", "conflicting", "insufficient", "quarantined"] = (
        "unresolved"
    )
    quarantined: bool = False
    quarantine_reason: str | None = None
    safe_text: str
    detected_instructions: list[EvidenceSpan] = Field(default_factory=list)
    fields: list[ExtractedField] = Field(default_factory=list)
    evidence_spans: list[EvidenceSpan] = Field(default_factory=list)
    normalized_names: list[str] = Field(default_factory=list)
    translated_text: str | None = None
    translation_warning: str | None = None
    source_reliability_metadata: str | None = None
    reliability_note: str | None = None


class ScoreComponent(StrictModel):
    field: str
    value: float = Field(ge=0, le=1)
    explanation: str


class CompatibilityFactor(StrictModel):
    factor_id: str
    field: str
    record_a_value: str
    record_b_value: str
    status: Literal["compatible", "soft_conflict", "hard_conflict", "uncertain", "missing"]
    interpretation: str
    certainty_a: Certainty
    certainty_b: Certainty
    evidence_span_ids: list[str]


class Conflict(StrictModel):
    conflict_id: str
    field: str
    severity: Literal["hard", "soft", "unresolved"]
    explanation: str
    evidence_span_ids: list[str]


class RivalComparison(StrictModel):
    record_id: str
    display_name: str
    age: str
    comparison: dict[str, Literal["stronger", "weaker", "conflicting", "unresolved"]]
    summary: str


class CandidateConnection(StrictModel):
    candidate_id: str
    record_a_id: str
    record_b_id: str
    label: str
    classification: str
    classification_code: Classification
    review_status: Literal["review_required"] = "review_required"
    supporting_summary: str
    opposing_summary: str
    verification_question: str
    verification_explanation: str
    additional_questions: list[str] = Field(default_factory=list)
    abstention_reasons: list[str] = Field(default_factory=list)
    compatibility_factors: list[CompatibilityFactor] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    rivals: list[RivalComparison] = Field(default_factory=list)
    retrieval_score: float = Field(ge=0)
    score_components: list[ScoreComponent] = Field(default_factory=list)
    rank: int = Field(ge=1)
    adjudicator_agreement: bool = True

    @field_validator("label", "classification")
    @classmethod
    def reject_identity_claims(cls, value: str) -> str:
        forbidden = {"confirmed_match", "identity_confirmed", "person_found", "guaranteed_match"}
        if value.lower().replace(" ", "_") in forbidden:
            raise ValueError("autonomous identity claims are prohibited")
        return value


class ValidationResult(StrictModel):
    check: str
    passed: bool
    detail: str


class WorkflowTrace(StrictModel):
    node_id: str
    order: int
    name: str
    short_name: str
    category: str
    input: str
    purpose: str
    output: str
    method: str
    failure_condition: str
    human_input_requirement: str
    constraints: list[str]
    downstream_consumer: str
    demo_duration_ms: int | None = None


class WorkflowTraceDetail(StrictModel):
    node_id: str
    node_version: str
    node_name: str
    category: str
    status: Literal["completed", "failed", "skipped"]
    uses_llm: bool
    requires_human_input: bool
    started_at: datetime
    completed_at: datetime
    duration_ms: float | None
    provider: str
    model: str | None
    prompt_template_id: str | None
    prompt_template_version: str | None
    input_record_ids: list[str]
    input_schema: str
    structured_input: dict[str, Any]
    structured_output: dict[str, Any]
    output_schema: str
    validation_results: list[ValidationResult]
    deterministic_checks: list[str]
    evidence_span_ids: list[str]
    warnings: list[str]
    failure_conditions: list[str]
    abstention_reason: str | None
    token_usage: int | None
    estimated_cost: float | None
    next_node: str | None
    human_review_requirement: str
    before_state: str
    after_state: str


class AuditEvent(StrictModel):
    event_id: str
    timestamp: datetime
    event_type: str
    actor: str
    action: str
    detail: str
    workflow_version: str
    prompt_version: str | None
    source_record_ids: list[str]
    before: str
    after: str
    before_value: str
    after_value: str
    reason: str
    machine_or_human: Literal["machine", "human"]
    origin: Literal["machine", "human"]
    synthetic_mode: bool


class AnalysisSummary(StrictModel):
    records_processed: int
    languages_detected: int
    candidate_connections: int
    awaiting_human_review: int
    hard_conflicts: int
    quarantined_instructions: int


class AnalyzeResponse(StrictModel):
    case_id: str
    workflow_run_id: str
    status: Literal["review_required", "insufficient_evidence", "complete"]
    mode: ProviderMode
    summary: AnalysisSummary
    records: list[NormalizedRecord]
    candidates: list[CandidateConnection]
    workflow_trace: list[WorkflowTrace]
    workflow_trace_details: list[WorkflowTraceDetail]
    audit_events: list[AuditEvent]
    safety_notices: list[str] = Field(default_factory=lambda: [SAFETY_NOTICE])
    human_review_requirement: str = SAFETY_NOTICE
    operational: dict[str, int | float] = Field(default_factory=dict)


class ProviderMetadata(StrictModel):
    provider: str
    model: str | None
    prompt_template_id: str
    prompt_template_version: str
    attempts: int
    duration_ms: float | None
    token_usage: int | None = None


class ProviderResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    output: Any
    metadata: ProviderMetadata


class ExtractionModelOutput(StrictModel):
    fields: list[ExtractedField]
    evidence_spans: list[EvidenceSpan]
    warnings: list[str] = Field(default_factory=list)


class NormalizationItem(StrictModel):
    record_id: str
    original_form: str
    normalized_comparison_form: str
    candidate_variants: list[str]
    language: str
    method: str
    evidence_span_ids: list[str]
    compatibility: Literal["compatible_representation", "incompatible_representation", "unresolved"]
    warning: str | None = None


class NormalizationModelOutput(StrictModel):
    items: list[NormalizationItem]


class HypothesisFactor(StrictModel):
    factor: str
    explanation: str
    evidence_span_ids: list[str]


class HypothesisModelOutput(StrictModel):
    supporting_factors: list[HypothesisFactor]
    uncertainty: list[str]
    missing_information: list[str]
    unsupported_hypothesis_claims: list[str]


class ProsecutorModelOutput(StrictModel):
    conflicts: list[Conflict]
    missing_information: list[str]
    unresolved_contradictions: list[str]
    suggested_clarification_questions: list[str]


class AdjudicationModelOutput(StrictModel):
    classification: Classification
    reasons: list[str]
    unresolved_issues: list[str]
    hard_conflict_count: int = Field(ge=0)
    evidence_coverage: Literal["complete", "partial", "insufficient"]
    rival_ambiguity: bool
    recommended_human_action: str


class SingleCallModelOutput(StrictModel):
    classification: Classification
    candidate_record_ids: list[str]
    cited_evidence_span_ids: list[str]
    supporting_evidence: list[str]
    contradictions: list[str]
    uncertainty: list[str]


class ErrorBody(StrictModel):
    request_id: str
    error_code: str
    message: str
    retryable: bool
    failed_stage: str | None
    preserved_data: bool
    details: dict[str, Any] = Field(default_factory=dict)


class ApiError(StrictModel):
    error: ErrorBody


class HealthResponse(StrictModel):
    status: Literal["ok"] = "ok"
    application_version: str
    provider_mode: str
    credentials_configured: bool
    provider_configured: bool
    configured_model: str | None


class BaselineRunRequest(StrictModel):
    case: AnalyzeRequest


class SystemOutput(StrictModel):
    case_id: str | None = None
    system_id: Literal["fuzzy", "generic", "structured", "threadline"]
    system_name: str
    evaluation_mode: str
    classification: Classification
    candidate_record_ids: list[str]
    cited_evidence: list[EvidenceSpan]
    output: dict[str, Any]
    duration_ms: float
    model_calls: int
    failures: int = 0
    retries: int = 0


class BaselineRunResponse(StrictModel):
    run_id: str
    systems: list[SystemOutput]
    safety_notice: str = SAFETY_NOTICE


class BenchmarkConfig(StrictModel):
    seed: int
    identities: int = Field(default=12, ge=2, le=500)
    records_per_identity: int = Field(default=3, ge=2, le=10)
    languages: list[str] = Field(default_factory=lambda: ["English", "Arabic", "French"])
    transliteration_severity: int = Field(default=35, ge=0, le=100)
    spelling_corruption: int = Field(default=12, ge=0, le=100)
    missing_field_percentage: int = Field(default=24, ge=0, le=100)
    estimated_age_variance: int = Field(default=2, ge=0, le=10)
    changed_location_frequency: int = Field(default=30, ge=0, le=100)
    duplicate_record_frequency: int = Field(default=8, ge=0, le=100)
    contradictory_timestamp_frequency: int = Field(default=10, ge=0, le=100)
    rival_candidate_count: int = Field(default=2, ge=0, le=10)
    prompt_injection_frequency: int = Field(default=5, ge=0, le=100)
    common_name_frequency: int = Field(default=18, ge=0, le=100)


class SyntheticIdentity(StrictModel):
    identity_id: str
    canonical_name: str
    age: int
    languages: list[str]
    home_location: str
    distinctive_feature: str


class GeneratedRecord(RecordInput):
    fictional_identity_id: str
    corruption_tags: list[str]


class GroundTruthCase(StrictModel):
    case_id: str
    record_ids: list[str]
    identity_ids: list[str]
    ground_truth_relation: Literal["same_identity", "different_identity", "genuinely_ambiguous"]
    expected_classification: Classification
    ambiguity_status: str
    difficulty_tags: list[str]
    corruption_tags: list[str]
    language_tags: list[str]
    expected_evidence_fields: list[str]


class BenchmarkDataset(StrictModel):
    benchmark_id: str
    configuration: BenchmarkConfig
    identities: list[SyntheticIdentity]
    records: list[GeneratedRecord]
    ground_truth: list[GroundTruthCase]
    content_hash: str
    synthetic_only: Literal[True] = True


class BenchmarkGenerateRequest(StrictModel):
    configuration: BenchmarkConfig


class MetricValue(StrictModel):
    metric_id: str
    value: float
    numerator: int | float
    denominator: int | float
    formula: str


class ErrorAnalysisCase(StrictModel):
    error_id: str
    case_id: str
    category: Literal[
        "missed_true_candidate",
        "incorrect_candidate_link",
        "failed_abstention",
        "unsupported_evidence",
        "timeline_reasoning_failure",
        "transliteration_failure",
        "rival_candidate_confusion",
        "prompt_injection_failure",
        "privacy_exposure",
        "extraction_error",
    ]
    record_ids: list[str]
    expected_result: str
    actual_result: str
    system: str
    workflow_configuration: str
    first_divergent_node: str
    evidence: list[str]
    severity: Literal["low", "medium", "high", "critical"]
    suggested_investigation: str


class BenchmarkSystemResult(StrictModel):
    system_id: str
    system_name: str
    evaluation_mode: str
    metrics: list[MetricValue]
    outputs: list[SystemOutput]
    errors: list[ErrorAnalysisCase]
    operational: dict[str, int | float]


class BenchmarkRunRequest(StrictModel):
    dataset: BenchmarkDataset | None = None
    configuration: BenchmarkConfig | None = None
    provider_mode: ProviderMode = ProviderMode.mock
    candidate_k: int = Field(default=5, ge=1, le=10)

    @model_validator(mode="after")
    def one_source(self) -> BenchmarkRunRequest:
        if (self.dataset is None) == (self.configuration is None):
            raise ValueError("provide exactly one of dataset or configuration")
        return self


class BenchmarkRunResponse(StrictModel):
    benchmark_run_id: str
    benchmark_id: str
    evaluation_mode: str
    systems: list[BenchmarkSystemResult]
    safety_notice: str = SAFETY_NOTICE


class AblationRunRequest(StrictModel):
    configuration: BenchmarkConfig
    disabled_nodes: list[str]
    provider_mode: ProviderMode = ProviderMode.mock

    @field_validator("disabled_nodes")
    @classmethod
    def normalize_ablation_node_names(cls, value: list[str]) -> list[str]:
        aliases = {
            "evidence_quarantine": "quarantine",
            "normalization": "normalize",
            "multilingual_normalization": "normalize",
            "timeline_reconstruction": "timeline",
            "contradiction_prosecutor": "prosecutor",
            "rival_candidate_test": "rivals",
            "independent_adjudication": "adjudicate",
            "privacy_gate": "privacy",
        }
        return [aliases.get(item, item) for item in value]


class AblationConfigurationResult(StrictModel):
    configuration_id: str
    enabled_nodes: list[str]
    disabled_nodes: list[str]
    metrics: list[MetricValue]
    changes_from_full: dict[str, float]
    newly_introduced_errors: list[ErrorAnalysisCase]
    resolved_errors: list[ErrorAnalysisCase]
    affected_case_ids: list[str]


class AblationRunResponse(StrictModel):
    ablation_run_id: str
    benchmark_id: str
    evaluation_mode: str
    configurations: list[AblationConfigurationResult]
    safety_notice: str = SAFETY_NOTICE


class ReviewOutcome(StrEnum):
    request_more_information = "request_more_information"
    dismiss_candidate = "dismiss_candidate"
    escalate_for_authorized_review = "escalate_for_authorized_review"
    mark_records_unrelated = "mark_records_unrelated"
    record_authorized_verification_outcome = "record_authorized_verification_outcome"


class ReviewCreate(StrictModel):
    case_id: str
    candidate_id: str | None = None
    outcome: ReviewOutcome
    reviewer_id: str = Field(min_length=1, max_length=120)
    notes: str = Field(default="", max_length=4_000)
    verification_reference: str | None = Field(default=None, max_length=500)


class ReviewReceipt(StrictModel):
    review_id: str
    case_id: str
    created_at: datetime
    outcome: ReviewOutcome
    audit_event_id: str
    safety_notice: str = SAFETY_NOTICE


class StoredResult(StrictModel):
    result_id: str
    result_type: str
    created_at: datetime
    provider_mode: str
    payload: dict[str, Any]


class StoredResultSummary(StrictModel):
    result_id: str
    result_type: str
    created_at: datetime
    provider_mode: str


class JobKind(StrEnum):
    benchmark = "benchmark"
    ablation = "ablation"
    trial = "trial"


class JobState(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class JobStatus(StrictModel):
    job_id: str
    kind: JobKind
    state: JobState
    progress: float = Field(ge=0, le=1)
    completed_cases: int = Field(default=0, ge=0)
    total_cases: int = Field(default=0, ge=0)
    stage: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result_id: str | None = None
    error: str | None = None
    retryable: bool = False


class MutationType(StrEnum):
    transliteration_corruption = "transliteration_corruption"
    spelling_corruption = "spelling_corruption"
    missing_surname = "missing_surname"
    estimated_age_shift = "estimated_age_shift"
    missing_location = "missing_location"
    changed_location = "changed_location"
    impossible_timeline = "impossible_timeline"
    conflicting_distinctive_feature = "conflicting_distinctive_feature"
    translation_detail_loss = "translation_detail_loss"
    common_name_collision = "common_name_collision"
    duplicate_submission = "duplicate_submission"
    equally_plausible_rivals = "equally_plausible_rivals"
    prompt_injection = "prompt_injection"
    source_reliability_noise = "source_reliability_noise"
    contradictory_relative_information = "contradictory_relative_information"


class TrialGroundTruth(StrictModel):
    relation: Literal["same_identity", "different_identity", "genuinely_ambiguous"]
    expected_classifications: list[Classification]
    rationale: str
    protected_fact: str


class TrialCase(StrictModel):
    case_id: str
    title: str
    challenge: str
    default_mutations: list[MutationType]
    request: AnalyzeRequest
    ground_truth: TrialGroundTruth


class MutationRecord(StrictModel):
    mutation_id: str
    mutation_type: MutationType
    seed: int
    affected_record_ids: list[str]
    affected_fields: list[str]
    before: dict[str, str]
    after: dict[str, str]
    challenge: str
    ground_truth_relation: str
    ground_truth_changed: Literal[False] = False
    difficulty: Literal["low", "medium", "high", "adversarial"]
    safety_note: str


class TrialCreateRequest(StrictModel):
    case_id: str
    mutation_types: list[MutationType] = Field(default_factory=list)
    seed: int = 104
    provider_mode: ProviderMode = ProviderMode.mock


class TrialPreview(StrictModel):
    trial_id: str
    case_id: str
    seed: int
    provider_mode: ProviderMode
    original_request: AnalyzeRequest
    mutated_request: AnalyzeRequest
    mutations: list[MutationRecord]
    ground_truth: TrialGroundTruth
    safety_notice: str = SAFETY_NOTICE


class DivergenceFinding(StrictModel):
    category: Literal[
        "none",
        "candidate_retrieval",
        "classification",
        "evidence_support",
        "contradiction_handling",
        "rival_handling",
        "injection_quarantine",
        "privacy_gate",
        "abstention",
    ]
    first_divergent_system: str | None
    first_divergent_node: str | None
    expected: str
    observed: str
    explanation: str


class TrialRunRequest(TrialCreateRequest):
    trial_id: str | None = None


class TrialRerunRequest(StrictModel):
    seed: int | None = None
    provider_mode: ProviderMode | None = None


class TrialRunResponse(StrictModel):
    trial_run_id: str
    trial_id: str
    result_id: str
    case_id: str
    seed: int
    provider_mode: ProviderMode
    mutations: list[MutationRecord]
    systems: list[SystemOutput]
    divergence: DivergenceFinding
    workflow_run_id: str | None
    ground_truth: TrialGroundTruth
    created_at: datetime
    safety_notice: str = SAFETY_NOTICE


class ConfidenceInterval(StrictModel):
    lower: float
    upper: float
    level: float = 0.95
    method: Literal["fixed_seed_bootstrap"] = "fixed_seed_bootstrap"


class MultiSeedMetric(StrictModel):
    metric_id: str
    mean: float
    standard_deviation: float
    minimum: float
    maximum: float
    confidence_interval: ConfidenceInterval


class MultiSeedSummary(StrictModel):
    seeds: list[int]
    metrics: list[MultiSeedMetric]
    successful_runs: int
    failed_runs: int
    total_cases: int
    provider_mode: ProviderMode
    configured_model: str | None
    model_calls: int
    duration_ms: float


class RiskCoveragePoint(StrictModel):
    policy: Literal["exploratory", "balanced", "conservative"]
    review_priority_threshold: float
    coverage: float
    selective_risk: float
    reviewed_cases: int
    total_cases: int


class RouterDecision(StrictModel):
    case_id: str
    profile: Literal["deterministic_only", "reduced", "full"]
    observable_signals: list[str]
    disabled_nodes: list[str]


class AdaptiveRouterComparison(StrictModel):
    decisions: list[RouterDecision]
    full_metrics: list[MetricValue]
    adaptive_metrics: list[MetricValue]
    full_model_calls: int
    adaptive_model_calls: int
    full_duration_ms: float
    adaptive_duration_ms: float
    safety_notice: str = SAFETY_NOTICE


class BenchmarkJobRequest(StrictModel):
    configuration: BenchmarkConfig
    seeds: list[int] = Field(default_factory=lambda: [104, 205, 306, 407, 508])
    provider_mode: ProviderMode = ProviderMode.mock
    candidate_k: int = Field(default=5, ge=1, le=10)
    include_risk_coverage: bool = True
    include_adaptive_router: bool = True

    @field_validator("seeds")
    @classmethod
    def require_seeds(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("at least one seed is required")
        return list(dict.fromkeys(value))


class EvaluationResult(StrictModel):
    runs: list[BenchmarkRunResponse]
    multi_seed: MultiSeedSummary
    risk_coverage: list[RiskCoveragePoint]
    adaptive_router: AdaptiveRouterComparison | None


class ExportRequest(StrictModel):
    format: Literal["json", "csv", "markdown"] = "json"


class ExportManifest(StrictModel):
    export_id: str
    result_id: str
    format: Literal["json", "csv", "markdown"]
    created_at: datetime
    filename: str
    content_type: str
    content_sha256: str
    bytes: int
    provider_mode: str
    contains_credentials: Literal[False] = False
    content: str


class ReportResponse(StrictModel):
    report_id: str
    result_id: str
    created_at: datetime
    markdown: str
