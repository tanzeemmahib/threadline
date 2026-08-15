export type SourceType =
  | "family_report"
  | "shelter_record"
  | "hospital_intake"
  | "evacuation_log"
  | "transport_manifest"
  | "missing_person_registry"
  | "field_team_note"
  | "translated_witness_statement"
  | "scanned_document_metadata"
  | "translated_phone_submission"
  | "volunteer_note"
  | "family_tracing_report"
  | "shelter_intake"
  | "field_clinic_register"
  | "evacuation_manifest"
  | "aid_registration"
  | "translated_witness_note";

export type CandidateStatus =
  | "candidate"
  | "conflicting"
  | "insufficient"
  | "quarantined"
  | "unresolved";

export type EvidenceCertainty =
  | "exact"
  | "estimated"
  | "translated"
  | "inferred"
  | "missing";

export type CompatibilityStatus =
  | "compatible"
  | "soft_conflict"
  | "hard_conflict"
  | "missing"
  | "uncertain";

export interface Incident {
  incident_id: string;
  name: string;
  description: string;
  languages: string[];
  simulation_label: string;
}

export interface OriginalEvidenceSpan {
  span_id: string;
  record_id: string;
  quote: string;
  start: number;
  end: number;
  text: string;
  field: string;
  certainty: EvidenceCertainty;
  extraction_method: string;
  extraction_status: "extracted" | "review_required" | "quarantined";
  normalization_note?: string | null;
  valid: boolean;
  validation_error?: string | null;
  source_document_id?: string | null;
  content_hash?: string | null;
  language?: string | null;
  validation_status?: "unvalidated" | "valid" | "invalid";
  created_at?: string | null;
  created_by?: string;
  validated_at?: string | null;
}

export interface ExtractedField {
  field_id: string;
  key: string;
  label: string;
  value: string;
  certainty: EvidenceCertainty;
  source_span_id: string;
  normalized_value?: string;
}

export interface SourceRecord {
  record_id: string;
  source_type: SourceType;
  language: string;
  timestamp: string;
  display_name: string;
  text: string;
  translated_text?: string;
  translation_provenance?: string;
  translation_warning?: string;
  status: CandidateStatus;
  quarantined: boolean;
  quarantine_reason?: string;
  fields: ExtractedField[];
  evidence_spans: OriginalEvidenceSpan[];
  reliability_note: string;
  source_organization?: string | null;
  created_at?: string | null;
  event_time?: string | null;
  provenance_metadata?: Record<string, JsonValue>;
  reliability_metadata?: Record<string, JsonValue>;
  ingestion_hash?: string | null;
}

export interface CompatibilityFactor {
  factor_id: string;
  field: string;
  record_a_value: string;
  record_b_value: string;
  status: CompatibilityStatus;
  interpretation: string;
  certainty_a: EvidenceCertainty;
  certainty_b: EvidenceCertainty;
  evidence_span_ids: string[];
}

export interface Conflict {
  conflict_id: string;
  field: string;
  severity: "soft" | "hard" | "unresolved";
  explanation: string;
  evidence_span_ids: string[];
}

export interface RivalCandidate {
  record_id: string;
  display_name: string;
  age: string;
  comparison: Record<
    | "name"
    | "age"
    | "language"
    | "location"
    | "timeline"
    | "clothing"
    | "distinctive_features"
    | "hard_conflicts",
    "stronger" | "weaker" | "unresolved" | "conflicting"
  >;
  summary: string;
}

export interface CandidateConnection {
  candidate_id: string;
  record_a_id: string;
  record_b_id: string;
  label: "Possible candidate connection" | "Strong candidate for review" | "Insufficient evidence" | "Conflicting evidence" | "Output withheld";
  classification?: "Strong candidate for review" | "Possible candidate" | "Insufficient evidence" | "Conflicting evidence" | null;
  classification_code?: ContractClassification | null;
  abstention_reasons?: string[];
  review_status: "review_required" | "escalated" | "dismissed" | "unrelated" | "more_information_requested";
  compatibility_factors: CompatibilityFactor[];
  conflicts: Conflict[];
  rivals: RivalCandidate[];
  supporting_summary: string;
  opposing_summary: string;
  verification_question: string;
  verification_explanation: string;
  additional_questions: string[];
}

export type WorkflowCategory =
  | "Human input"
  | "LLM transformation"
  | "LLM reasoning"
  | "Deterministic validation"
  | "Retrieval"
  | "Privacy/safety"
  | "Human decision";

export interface WorkflowNode {
  node_id: string;
  order: number;
  name: string;
  short_name: string;
  category: WorkflowCategory;
  input: string;
  purpose: string;
  output: string;
  method: "Configured LLM" | "Deterministic rules" | "Indexed retrieval" | "Authorized human procedure";
  failure_condition: string;
  human_input_requirement: string;
  constraints: string[];
  downstream_consumer: string;
  demo_duration_ms?: number;
}

export interface WorkflowRun {
  workflow_run_id: string;
  case_id: string;
  status: "ready" | "processing" | "partial_failure" | "review_required" | "complete";
  nodes: Array<
    WorkflowNode & {
      run_status: "pending" | "active" | "complete" | "warning";
    }
  >;
}

export type ReviewOutcome =
  | "additional_evidence_required"
  | "candidate_thread_not_supported"
  | "candidate_thread_remains_plausible"
  | "escalate_to_authorized_case_process"
  | "request_more_information"
  | "dismiss_candidate"
  | "escalate_authorized_review"
  | "mark_unrelated"
  | "record_authorized_verification_outcome";

export interface ReviewDecision {
  decision_id: string;
  candidate_id: string;
  outcome: ReviewOutcome;
  notes: string;
  remaining_uncertainty?: string[];
  requested_evidence?: string[];
  workflow_run_id?: string;
  contract_id?: string;
  referenced_artifact_ids?: string[];
  reviewer_role: string;
  timestamp: string;
}

export interface AuditEvent {
  event_id: string;
  timestamp: string;
  actor: string;
  action: string;
  detail: string;
  event_type?: AuditEventType;
  workflow_version?: string;
  prompt_version?: string;
  source_record_ids?: string[];
  before_value?: string;
  after_value?: string;
  reason?: string;
  origin?: "human" | "machine";
}

export type TimestampKind = "exact" | "estimated" | "inferred" | "contradiction" | "missing";
export type LocationKind = "verified" | "approximate" | "inferred" | "contradiction" | "missing";

export interface ReconstructionLocation {
  location_id: string;
  label: string;
  x: number;
  y: number;
  kind: LocationKind;
  record_ids: string[];
  description: string;
}

export interface ReconstructionEvent {
  event_id: string;
  time: string;
  timestamp_kind: TimestampKind;
  location_id: string;
  title: string;
  description: string;
  record_ids: string[];
  evidence_span_ids: string[];
}

export interface ReconstructionData {
  locations: ReconstructionLocation[];
  events: ReconstructionEvent[];
  route_location_ids: string[];
  estimated_travel_window: string;
  text_alternative: string;
}

export type WorkflowInspectorTab = "Overview" | "Input" | "Prompt" | "Output" | "Validation" | "Evidence" | "Diff";

export interface SyntheticTraceMeasurement {
  value: number | null;
  label: string;
}

export interface WorkflowNodeTrace {
  node_id: string;
  node_version: string;
  input_record_ids: string[];
  input_schema: string;
  prompt_template: string;
  prompt_variables: Record<string, string>;
  configured_model: "Configured LLM" | "Not applicable";
  structured_output: string;
  output_schema: string;
  deterministic_checks: string[];
  evidence_span_ids: string[];
  warnings: string[];
  failure_conditions: string[];
  abstention_reason: string | null;
  duration: SyntheticTraceMeasurement;
  token_usage: SyntheticTraceMeasurement;
  estimated_cost: SyntheticTraceMeasurement;
  next_node: string | null;
  human_review_requirement: string;
  before_state: string;
  after_state: string;
}

export interface SyntheticBenchmarkConfig {
  seed: number;
  identities: number;
  records_per_identity: number;
  languages: Array<"English" | "Arabic" | "French">;
  transliteration_severity: number;
  spelling_corruption: number;
  missing_field_percentage: number;
  estimated_age_variance: number;
  changed_location_frequency: number;
  duplicate_record_frequency: number;
  contradictory_timestamp_frequency: number;
  rival_candidate_count: number;
  prompt_injection_frequency: number;
  common_name_frequency: number;
}

export interface GeneratedSyntheticRecord {
  record_id: string;
  fictional_identity_id: string;
  language: "English" | "Arabic" | "French";
  display_name: string;
  source_type: SourceType;
  fields_present: string[];
  flags: string[];
}

export interface BenchmarkComposition {
  identities: number;
  total_records: number;
  languages: number;
  positive_record_pairs: number;
  negative_record_pairs: number;
  ambiguous_cases: number;
  injected_records: number;
  hard_cases: number;
}

export type BaselineSystemId = "fuzzy" | "generic" | "structured" | "threadline";
export type CandidateClassification = "Strong candidate for review" | "Possible candidate" | "Insufficient evidence" | "Conflicting evidence";

export interface BaselineCaseResult {
  system_id: BaselineSystemId;
  system_name: string;
  output_origin: "Synthetic example output" | "Actual backend output";
  candidate_output: string;
  classification: CandidateClassification;
  supporting_evidence: string[];
  contradictions_found: string[];
  rival_candidates_considered: string[];
  abstention_behaviour: string;
  unsupported_claims: string[];
  injection_behaviour: string;
  human_review_routing: string;
}

export type AblationNodeId = "quarantine" | "normalization" | "timeline" | "prosecutor" | "rivals" | "adjudication" | "privacy";

export interface AblationCaseImpact {
  metric_id: "false_link_rate" | "candidate_recall" | "correct_abstentions" | "evidence_faithfulness";
  case_ids: string[];
  explanation: string;
}

export type ErrorCategory =
  | "missed true candidate"
  | "incorrect candidate link"
  | "failed abstention"
  | "unsupported evidence"
  | "timeline reasoning failure"
  | "transliteration failure"
  | "rival-candidate confusion"
  | "prompt-injection failure"
  | "privacy exposure"
  | "extraction error";

export interface ErrorAnalysisCase {
  error_id: string;
  case_id: string;
  category: ErrorCategory;
  severity: "low" | "medium" | "high" | "critical";
  system_id: BaselineSystemId;
  language: "English" | "Arabic" | "French";
  workflow_configuration: string;
  affected_records: string[];
  expected_result: string;
  system_result: string;
  first_divergence_node: string;
  supporting_evidence: string[];
  possible_correction: string;
  reviewer_notes: string;
}

export type AuditEventType =
  | "source ingested"
  | "injection quarantined"
  | "field extracted"
  | "translation created"
  | "normalization variant added"
  | "candidate retrieved"
  | "hypothesis produced"
  | "contradiction found"
  | "rival evaluated"
  | "adjudication produced"
  | "privacy field redacted"
  | "human review requested"
  | "reviewer decision saved";

export interface BenchmarkMetric {
  metric_id: string;
  label: string;
  unit: "percent" | "milliseconds" | "count";
  higher_is_better: boolean;
  description: string;
}

export interface BenchmarkSystemResult {
  system_id: string;
  system_name: string;
  values: Record<string, number>;
  status: "illustrative" | "measured";
}

export interface AblationResult {
  configuration_id: string;
  configuration_name: string;
  values: Record<string, number>;
  status: "illustrative" | "measured";
}

export interface AnalysisSummary {
  records_processed: number;
  languages_detected: number;
  candidate_connections: number;
  awaiting_human_review: number;
  hard_conflicts: number;
  quarantined_instructions: number;
}

export type ContractClassification =
  | "strong_candidate_for_review"
  | "possible_candidate"
  | "insufficient_evidence"
  | "conflicting_evidence";

export type EvidenceClaimType =
  | "extracted_fact"
  | "normalized_representation"
  | "timeline_interpretation"
  | "compatibility_claim"
  | "contradiction_claim"
  | "rival_comparison_claim";

export interface EvidenceClaim {
  claim_id: string;
  candidate_id: string;
  claim_type: EvidenceClaimType;
  claim_text: string;
  source_record_ids: string[];
  source_spans: OriginalEvidenceSpan[];
  certainty_basis: Record<string, EvidenceCertainty>;
  generated_by_node: string;
  supported: boolean;
  support_reason: string;
  violations: string[];
  source_record_id?: string | null;
  source_span_ids?: string[];
  parent_claim_ids?: string[];
  transformation_type?: string;
  transformation_version?: string;
  prompt_template_version?: string | null;
  model_identifier?: string | null;
  created_by?: string;
  created_at?: string | null;
  claim_hash?: string | null;
  raw_value?: string | null;
  normalized_value?: string | null;
  certainty_category?: EvidenceCertainty;
  transformation_history?: Array<{
    transformation_id: string;
    transformation_type: string;
    transformation_version: string;
    input_claim_ids: string[];
    input_artifact_ids: string[];
    output_certainty: EvidenceCertainty;
    created_by_step: string;
    created_at?: string | null;
  }>;
  consumed_by_rule_ids?: string[];
  also_supports_candidate_ids?: string[];
  case_id?: string | null;
}

export interface ContractViolation {
  violation_id: string;
  rule_id: string;
  severity: "information" | "warning" | "critical";
  claim_id: string | null;
  message: string;
  blocks_release: boolean;
  suggested_resolution: string;
  rule_class?: "blocking" | "review_required" | "informational";
  evidence_span_ids?: string[];
}

export interface ContractRuleResult {
  rule_id: string;
  rule_class: "blocking" | "review_required" | "informational";
  severity: "information" | "warning" | "critical";
  passed: boolean;
  affected_claim_ids: string[];
  affected_evidence_span_ids: string[];
  operator_explanation: string;
  remediation_guidance: string;
  rule_name?: string;
  rule_version?: string;
  status?: "pass" | "warn" | "fail" | "block";
  reason_code?: string;
  input_artifact_ids?: string[];
  related_source_span_ids?: string[];
  evaluation_timestamp?: string | null;
  evaluator_version?: string;
}

export interface CandidateClaimLedger {
  ledger_id: string;
  case_id: string;
  candidate_id: string;
  supporting_claim_ids: string[];
  contradiction_claim_ids: string[];
  timeline_claim_ids: string[];
  compatibility_claim_ids: string[];
  rival_comparison_claim_ids: string[];
  missing_evidence: string[];
  required_follow_up_evidence: string[];
  safety_notices: string[];
  contract_result_ids: string[];
}

export interface EvidenceContract {
  contract_id: string;
  case_id: string;
  candidate_id: string;
  classification: ContractClassification | null;
  contract_status: "passed" | "passed_with_review_requirements" | "blocked" | "verifier_error";
  release_allowed: boolean;
  claims: EvidenceClaim[];
  violations: ContractViolation[];
  contradictions_considered: string[];
  rivals_considered: string[];
  decision_critical_evidence: Array<Record<string, JsonValue>>;
  audit_chain_status: Record<string, JsonValue>;
  created_at: string;
  verifier_version: string;
  safety_notice: string;
  schema_version?: string;
  rule_set_version?: string;
  rule_results?: ContractRuleResult[];
  candidate_ledger?: CandidateClaimLedger | null;
}

export interface AuditChainEvent {
  event_id: string;
  workflow_run_id: string;
  contract_id: string | null;
  candidate_id: string | null;
  sequence_number: number;
  event_type: string;
  actor_type: "system" | "model" | "human";
  actor_id: string | null;
  created_at: string;
  payload: Record<string, JsonValue>;
  payload_hash: string;
  previous_event_hash: string;
  event_hash: string;
  hash_algorithm: string;
  schema_version: string;
}

export interface AuditIntegrityResult {
  workflow_run_id: string;
  status: "verified" | "broken" | "incomplete" | "unsupported_schema" | "verifier_error";
  valid: boolean;
  first_invalid_event_id: string | null;
  first_invalid_sequence: number | null;
  expected_previous_hash: string | null;
  observed_previous_hash: string | null;
  expected_payload_hash: string | null;
  observed_payload_hash: string | null;
  expected_event_hash: string | null;
  observed_event_hash: string | null;
  missing_sequence_numbers: number[];
  duplicated_sequence_numbers: number[];
  verified_event_count: number;
  terminal_hash: string | null;
  hash_algorithm: string;
  verifier_version: string;
  limitation: string;
}

export interface ReplayCheckpoint {
  checkpoint_id: string;
  expected_hash: string;
  observed_hash: string | null;
  consistent: boolean | null;
}

export interface ReplayManifest {
  workflow_run_id: string;
  original_input_package_hash: string;
  canonical_normalized_input_hash: string;
  workflow_schema_version: string;
  contract_schema_version: string;
  scoring_version: string;
  rule_set_version: string;
  configuration_hash: string;
  prompt_template_versions: Record<string, string>;
  model_identifiers: string[];
  deterministic_seeds: number[];
  ordered_workflow_nodes: string[];
  node_checkpoints: ReplayCheckpoint[];
  final_candidate_set_hash: string;
  final_ranking_hash: string;
  final_contract_hash: string;
  final_response_hash: string;
  audit_chain_terminal_hash: string;
  created_at: string;
  manifest_version: string;
}

export interface ReplayCertificate {
  replay_id: string;
  source_workflow_run_id: string;
  replay_workflow_run_id: string | null;
  replay_status: "exact_match" | "equivalent_match" | "diverged" | "unsupported" | "replay_error";
  replay_mode: "deterministic" | "frozen_model_outputs" | "semantic" | "unsupported";
  started_at: string;
  completed_at: string;
  manifest_version: string;
  checkpoints: ReplayCheckpoint[];
  first_divergence: string | null;
  expected_hash: string | null;
  observed_hash: string | null;
  classification_consistent: boolean;
  ranking_consistent: boolean;
  contract_consistent: boolean;
  audit_chain_consistent: boolean;
  release_permitted: boolean;
  limitations: string[];
}

export type CounterfactualType =
  | "remove_evidence_span"
  | "remove_source_record"
  | "remove_compatibility_claim"
  | "remove_conflicting_claim"
  | "remove_rival_comparison_claim"
  | "reduce_evidence_certainty"
  | "mark_source_unavailable";

export interface CounterfactualCertificate {
  certificate_id: string;
  original_workflow_run_id: string;
  counterfactual_run_id: string;
  candidate_id: string;
  counterfactual_type: CounterfactualType;
  removed_or_altered_evidence_ids: string[];
  original_classification: ContractClassification | null;
  counterfactual_classification: ContractClassification | null;
  original_rank: number | null;
  counterfactual_rank: number | null;
  original_score: number | null;
  counterfactual_score: number | null;
  triggered_violations: string[];
  resolved_violations: string[];
  decision_changed: boolean;
  rank_changed: boolean;
  classification_changed: boolean;
  release_status: "released" | "withheld";
  explanation: string;
  first_responsible_node: string;
  created_at: string;
  limitations: string[];
}

export interface AnalyzeRequest {
  incident: Pick<Incident, "incident_id" | "name" | "languages"> & {
    description?: string;
    approximate_region?: string;
    known_locations?: string[];
    time_window?: string;
    reviewer_constraints?: string[];
  };
  records: Array<Pick<SourceRecord, "record_id" | "source_type" | "language" | "text"> & {
    timestamp?: string | null;
    display_name?: string | null;
    translated_text?: string | null;
    source_reliability_metadata?: string | null;
    source_organization?: string | null;
    created_at?: string | null;
    event_time?: string | null;
    provenance_metadata?: Record<string, JsonValue>;
    reliability_metadata?: Record<string, JsonValue>;
    ingestion_hash?: string | null;
  }>;
  options?: {
    provider_mode?: ProviderMode;
    include_workflow_trace?: boolean;
    candidate_limit?: number;
    disabled_nodes?: string[];
    adjudicator_count?: number;
  };
}

export interface AnalyzeResponse {
  case_id: string;
  workflow_run_id: string;
  status: "review_required" | "insufficient_evidence" | "complete";
  mode?: ProviderMode;
  summary: AnalysisSummary;
  records?: SourceRecord[];
  candidates: CandidateConnection[];
  workflow_trace: WorkflowNode[];
  workflow_trace_details?: BackendWorkflowTraceDetail[];
  audit_events?: AuditEvent[];
  audit_chain_events?: AuditChainEvent[];
  audit_integrity?: AuditIntegrityResult | null;
  replay_manifest?: ReplayManifest | null;
  latest_replay_certificate?: ReplayCertificate | null;
  counterfactual_certificates?: CounterfactualCertificate[];
  evidence_contract?: EvidenceContract | null;
  evidence_contracts?: EvidenceContract[];
  contract_release_status?: "released" | "withheld";
  release_state?:
    | { state: "draft" }
    | { state: "contract_evaluating"; contract_ids: string[] }
    | { state: "contract_blocked"; contract_ids: string[]; blocking_rule_ids: string[]; authorized_review_required: true }
    | { state: "authorized_review_required"; contract_ids: string[]; authorized_review_required: true }
    | { state: "authorized_review_in_progress"; contract_ids: string[]; review_id: string; reviewer_id: string }
    | { state: "authorized_disposition_recorded"; contract_ids: string[]; review_id: string; reviewer_id: string; disposition: string };
  safety_notices?: string[];
  human_review_requirement?: string;
  operational?: Record<string, number>;
}

export interface CaseData extends AnalyzeResponse {
  incident: Incident;
  records: SourceRecord[];
  audit_events: AuditEvent[];
}

export interface BenchmarkData {
  metrics: BenchmarkMetric[];
  systems: BenchmarkSystemResult[];
  ablations: AblationResult[];
  source_status: "illustrative" | "measured";
}

export type DataMode = "mock" | "backend";

export type ProviderMode = "mock" | "openai_compatible";
export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

export interface HealthResponse {
  status: "ok";
  application_version: string;
  provider_mode: string;
  credentials_configured: boolean;
  provider_configured: boolean;
  configured_model: string | null;
}

export interface BackendWorkflowTraceDetail {
  node_id: string;
  node_version: string;
  node_name: string;
  category: string;
  status: "completed" | "failed" | "skipped";
  uses_llm: boolean;
  requires_human_input: boolean;
  started_at: string;
  completed_at: string;
  duration_ms: number | null;
  provider: string;
  model: string | null;
  prompt_template_id: string | null;
  prompt_template_version: string | null;
  input_record_ids: string[];
  input_schema: string;
  structured_input: Record<string, JsonValue>;
  structured_output: Record<string, JsonValue>;
  output_schema: string;
  validation_results: Array<{ check: string; passed: boolean; detail: string }>;
  deterministic_checks: string[];
  evidence_span_ids: string[];
  warnings: string[];
  failure_conditions: string[];
  abstention_reason: string | null;
  token_usage: number | null;
  estimated_cost: number | null;
  next_node: string | null;
  human_review_requirement: string;
  before_state: string;
  after_state: string;
}

export interface BackendSystemOutput {
  case_id: string | null;
  system_id: BaselineSystemId;
  system_name: string;
  evaluation_mode: string;
  classification: "strong_candidate_for_review" | "possible_candidate" | "insufficient_evidence" | "conflicting_evidence";
  candidate_record_ids: string[];
  cited_evidence: OriginalEvidenceSpan[];
  output: Record<string, JsonValue>;
  duration_ms: number;
  model_calls: number;
  failures: number;
  retries: number;
}

export interface BaselineRunResponse {
  run_id: string;
  systems: BackendSystemOutput[];
  safety_notice: string;
}

export interface BackendBenchmarkConfig {
  seed: number;
  identities: number;
  records_per_identity: number;
  languages?: string[];
  transliteration_severity?: number;
  spelling_corruption?: number;
  missing_field_percentage?: number;
  estimated_age_variance?: number;
  changed_location_frequency?: number;
  duplicate_record_frequency?: number;
  contradictory_timestamp_frequency?: number;
  rival_candidate_count?: number;
  prompt_injection_frequency?: number;
  common_name_frequency?: number;
}

export interface BackendBenchmarkDataset {
  benchmark_id: string;
  configuration: BackendBenchmarkConfig;
  identities: Array<Record<string, JsonValue>>;
  records: Array<Record<string, JsonValue>>;
  ground_truth: Array<Record<string, JsonValue>>;
  content_hash: string;
  synthetic_only: true;
}

export interface BackendMetricValue {
  metric_id: string;
  value: number;
  numerator: number;
  denominator: number;
  formula: string;
}

export interface BackendErrorAnalysisCase {
  error_id: string;
  case_id: string;
  category: string;
  record_ids: string[];
  expected_result: string;
  actual_result: string;
  system: string;
  workflow_configuration: string;
  first_divergent_node: string;
  evidence: string[];
  severity: "low" | "medium" | "high" | "critical";
  suggested_investigation: string;
}

export interface BackendBenchmarkSystemResult {
  system_id: BaselineSystemId;
  system_name: string;
  evaluation_mode: string;
  metrics: BackendMetricValue[];
  outputs: BackendSystemOutput[];
  errors: BackendErrorAnalysisCase[];
  operational: Record<string, number>;
}

export interface BackendBenchmarkRunResponse {
  benchmark_run_id: string;
  benchmark_id: string;
  evaluation_mode: string;
  systems: BackendBenchmarkSystemResult[];
  safety_notice: string;
}

export interface BackendAblationResult {
  configuration_id: string;
  enabled_nodes: string[];
  disabled_nodes: string[];
  metrics: BackendMetricValue[];
  changes_from_full: Record<string, number>;
  newly_introduced_errors: BackendErrorAnalysisCase[];
  resolved_errors: BackendErrorAnalysisCase[];
  affected_case_ids: string[];
}

export interface BackendAblationRunResponse {
  ablation_run_id: string;
  benchmark_id: string;
  evaluation_mode: string;
  configurations: BackendAblationResult[];
  safety_notice: string;
}

export type MutationType =
  | "transliteration_corruption"
  | "spelling_corruption"
  | "missing_surname"
  | "estimated_age_shift"
  | "missing_location"
  | "changed_location"
  | "impossible_timeline"
  | "conflicting_distinctive_feature"
  | "translation_detail_loss"
  | "common_name_collision"
  | "duplicate_submission"
  | "equally_plausible_rivals"
  | "prompt_injection"
  | "source_reliability_noise"
  | "contradictory_relative_information";

export interface TrialGroundTruth {
  relation: "same_identity" | "different_identity" | "genuinely_ambiguous";
  expected_classifications: string[];
  rationale: string;
  protected_fact: string;
}

export interface TrialCase {
  case_id: string;
  title: string;
  challenge: string;
  default_mutations: MutationType[];
  request: AnalyzeRequest;
  ground_truth: TrialGroundTruth;
}

export interface MutationRecord {
  mutation_id: string;
  mutation_type: MutationType;
  seed: number;
  affected_record_ids: string[];
  affected_fields: string[];
  before: Record<string, string>;
  after: Record<string, string>;
  challenge: string;
  ground_truth_relation: string;
  ground_truth_changed: false;
  difficulty: "low" | "medium" | "high" | "adversarial";
  safety_note: string;
}

export interface TrialCreateRequest {
  case_id: string;
  mutation_types: MutationType[];
  seed: number;
  provider_mode: ProviderMode;
}

export interface TrialPreview {
  trial_id: string;
  case_id: string;
  seed: number;
  provider_mode: ProviderMode;
  original_request: AnalyzeRequest;
  mutated_request: AnalyzeRequest;
  mutations: MutationRecord[];
  ground_truth: TrialGroundTruth;
  safety_notice: string;
}

export interface DivergenceFinding {
  category: string;
  first_divergent_system: string | null;
  first_divergent_node: string | null;
  expected: string;
  observed: string;
  explanation: string;
}

export interface TrialRunResponse {
  trial_run_id: string;
  trial_id: string;
  result_id: string;
  case_id: string;
  seed: number;
  provider_mode: ProviderMode;
  mutations: MutationRecord[];
  systems: BackendSystemOutput[];
  divergence: DivergenceFinding;
  workflow_run_id: string | null;
  ground_truth: TrialGroundTruth;
  created_at: string;
  safety_notice: string;
}

export type JobState = "queued" | "running" | "completed" | "failed" | "cancelled";
export interface JobStatus {
  job_id: string;
  kind: "benchmark" | "ablation" | "trial";
  state: JobState;
  progress: number;
  completed_cases: number;
  total_cases: number;
  stage: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  result_id: string | null;
  error: string | null;
  retryable: boolean;
}

export interface StoredResult {
  result_id: string;
  result_type: string;
  created_at: string;
  provider_mode: string;
  payload: Record<string, JsonValue>;
}

export interface StoredResultSummary {
  result_id: string;
  result_type: string;
  created_at: string;
  provider_mode: string;
}

export interface ExportManifest {
  export_id: string;
  result_id: string;
  format: "json" | "csv" | "markdown";
  created_at: string;
  filename: string;
  content_type: string;
  content_sha256: string;
  bytes: number;
  provider_mode: string;
  contains_credentials: false;
  content: string;
}

export interface MultiSeedMetric {
  metric_id: string;
  mean: number;
  standard_deviation: number;
  minimum: number;
  maximum: number;
  confidence_interval: { lower: number; upper: number; level: number; method: "fixed_seed_bootstrap" };
}

export interface MultiSeedSummary {
  seeds: number[];
  metrics: MultiSeedMetric[];
  successful_runs: number;
  failed_runs: number;
  total_cases: number;
  provider_mode: ProviderMode;
  configured_model: string | null;
  model_calls: number;
  duration_ms: number;
}

export interface RiskCoveragePoint {
  policy: "exploratory" | "balanced" | "conservative";
  review_priority_threshold: number;
  coverage: number;
  selective_risk: number;
  reviewed_cases: number;
  total_cases: number;
}

export interface AdaptiveRouterComparison {
  decisions: Array<{ case_id: string; profile: "deterministic_only" | "reduced" | "full"; observable_signals: string[]; disabled_nodes: string[] }>;
  full_metrics: BackendMetricValue[];
  adaptive_metrics: BackendMetricValue[];
  full_model_calls: number;
  adaptive_model_calls: number;
  full_duration_ms: number;
  adaptive_duration_ms: number;
  safety_notice: string;
}

export interface EvaluationSuiteResult {
  runs: BackendBenchmarkRunResponse[];
  multi_seed: MultiSeedSummary;
  risk_coverage: RiskCoveragePoint[];
  adaptive_router: AdaptiveRouterComparison | null;
}
