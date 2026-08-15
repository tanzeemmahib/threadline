import { mockCaseData } from "@/data/mock-data";
import type {
  AblationNodeId,
  AuditIntegrityResult,
  AnalyzeRequest,
  AnalyzeResponse,
  BackendAblationRunResponse,
  BackendBenchmarkConfig,
  BackendBenchmarkDataset,
  BackendBenchmarkRunResponse,
  BaselineRunResponse,
  CounterfactualCertificate,
  CounterfactualType,
  EvidenceContract,
  ExportManifest,
  HealthResponse,
  JobStatus,
  ProviderMode,
  ReplayCertificate,
  ReviewDecision,
  StoredResult,
  StoredResultSummary,
  TrialCase,
  TrialCreateRequest,
  TrialPreview,
  TrialRunResponse,
} from "@/types";

export const FALLBACK_NOTICE = "Backend unavailable — synthetic fallback active";
export const MOCK_PROVIDER_LABEL = "Deterministic mock provider";
export const CONNECTED_PROVIDER_LABEL = "Connected model provider";
export const MOCK_EVALUATION_LABEL = "Deterministic mock evaluation — not real model performance";
export const MEASURED_EVALUATION_LABEL = "Measured provider evaluation";

export interface RequestOptions {
  signal?: AbortSignal;
}

export interface ReviewReceipt {
  review_id: string;
  case_id: string;
  candidate_id?: string | null;
  created_at: string;
  outcome: string;
  audit_event_id: string;
  audit_chain_event_id?: string | null;
  release_state: NonNullable<AnalyzeResponse["release_state"]>;
  safety_notice: string;
}

export interface BenchmarkJobRequest {
  configuration: BackendBenchmarkConfig;
  seeds: number[];
  provider_mode: ProviderMode;
  candidate_k: number;
  include_risk_coverage: boolean;
  include_adaptive_router: boolean;
}

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
    readonly requestId: string | null,
    readonly retryable: boolean,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

function fixtureRequest(): AnalyzeRequest {
  return {
    incident: {
      incident_id: mockCaseData.incident.incident_id,
      name: mockCaseData.incident.name,
      languages: mockCaseData.incident.languages,
      description: mockCaseData.incident.description,
      reviewer_constraints: ["Authorized human review required", "No autonomous identity determination"],
    },
    records: mockCaseData.records.map((record) => ({
      record_id: record.record_id,
      source_type: record.source_type,
      language: record.language,
      text: record.text,
      timestamp: record.timestamp,
      display_name: record.display_name,
      translated_text: record.translated_text,
      source_reliability_metadata: record.reliability_note,
    })),
    options: { provider_mode: "mock", include_workflow_trace: true, candidate_limit: 5 },
  };
}

function readErrorPayload(value: unknown): { message?: string; requestId?: string; retryable?: boolean } {
  if (!value || typeof value !== "object" || !("error" in value)) return {};
  const error = value.error;
  if (!error || typeof error !== "object") return {};
  return {
    message: "message" in error && typeof error.message === "string" ? error.message : undefined,
    requestId: "request_id" in error && typeof error.request_id === "string" ? error.request_id : undefined,
    retryable: "retryable" in error && typeof error.retryable === "boolean" ? error.retryable : undefined,
  };
}

export class ThreadlineApiClient {
  readonly configuredMode: "mock" | "backend";

  constructor(readonly apiUrl: string) {
    this.configuredMode = apiUrl ? "backend" : "mock";
  }

  private async request<T>(path: string, init: RequestInit = {}, options: RequestOptions = {}): Promise<T> {
    if (!this.apiUrl) {
      throw new ApiRequestError(FALLBACK_NOTICE, null, null, true);
    }
    let response: Response;
    try {
      response = await fetch(`${this.apiUrl}${path}`, {
        ...init,
        signal: options.signal,
        headers: { Accept: "application/json", ...(init.body ? { "Content-Type": "application/json" } : {}), ...init.headers },
      });
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") throw reason;
      throw new ApiRequestError(FALLBACK_NOTICE, null, null, true);
    }
    const value: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = readErrorPayload(value);
      throw new ApiRequestError(
        detail.message ?? `THREADLINE API returned ${response.status}.`,
        response.status,
        detail.requestId ?? response.headers.get("x-request-id"),
        detail.retryable ?? response.status >= 500,
      );
    }
    return value as T;
  }

  async getHealth(options?: RequestOptions): Promise<HealthResponse> {
    if (!this.apiUrl) {
      return { status: "ok", application_version: "fixture", provider_mode: "mock", credentials_configured: false, provider_configured: true, configured_model: null };
    }
    return this.request<HealthResponse>("/health", {}, options);
  }

  async getDemoIncident(options?: RequestOptions): Promise<AnalyzeRequest> {
    if (!this.apiUrl) return fixtureRequest();
    return this.request<AnalyzeRequest>("/api/v1/demo", {}, options);
  }

  getV1DemoScenario(
    scenario: "passing" | "blocked" | "review" | "rival",
    options?: RequestOptions,
  ): Promise<AnalyzeRequest> {
    return this.request(`/api/v1/demo/v1/${scenario}`, {}, options);
  }

  async analyzeRecords(payload: AnalyzeRequest, options?: RequestOptions): Promise<AnalyzeResponse> {
    if (!this.apiUrl) return mockCaseData;
    return this.request<AnalyzeResponse>("/api/v1/analyze", { method: "POST", body: JSON.stringify(payload) }, options);
  }

  runBaselines(payload: AnalyzeRequest, options?: RequestOptions): Promise<BaselineRunResponse> {
    return this.request("/api/v1/baselines/run", { method: "POST", body: JSON.stringify({ case: payload }) }, options);
  }

  generateBenchmark(configuration: BackendBenchmarkConfig, options?: RequestOptions): Promise<BackendBenchmarkDataset> {
    return this.request("/api/v1/benchmark/generate", { method: "POST", body: JSON.stringify({ configuration }) }, options);
  }

  runBenchmark(
    payload: { dataset?: BackendBenchmarkDataset; configuration?: BackendBenchmarkConfig; provider_mode: ProviderMode; candidate_k: number },
    options?: RequestOptions,
  ): Promise<BackendBenchmarkRunResponse> {
    return this.request("/api/v1/benchmark/run", { method: "POST", body: JSON.stringify(payload) }, options);
  }

  runAblation(
    payload: { configuration: BackendBenchmarkConfig; disabled_nodes: AblationNodeId[] | string[]; provider_mode: ProviderMode },
    options?: RequestOptions,
  ): Promise<BackendAblationRunResponse> {
    return this.request("/api/v1/ablation/run", { method: "POST", body: JSON.stringify(payload) }, options);
  }

  getTrialCases(options?: RequestOptions): Promise<TrialCase[]> {
    return this.request("/api/v1/trials/cases", {}, options);
  }

  createTrial(payload: TrialCreateRequest, options?: RequestOptions): Promise<TrialPreview> {
    return this.request("/api/v1/trials/preview", { method: "POST", body: JSON.stringify(payload) }, options);
  }

  runTrial(payload: TrialCreateRequest & { trial_id?: string }, options?: RequestOptions): Promise<TrialRunResponse> {
    return this.request("/api/v1/trials/run", { method: "POST", body: JSON.stringify(payload) }, options);
  }

  getTrialRun(trialRunId: string, options?: RequestOptions): Promise<TrialRunResponse> {
    return this.request(`/api/v1/trials/${encodeURIComponent(trialRunId)}`, {}, options);
  }

  getWorkflowRun(workflowRunId: string, options?: RequestOptions): Promise<AnalyzeResponse> {
    return this.request(`/api/v1/workflow-runs/${encodeURIComponent(workflowRunId)}`, {}, options);
  }

  getEvidenceContract(contractId: string, options?: RequestOptions): Promise<EvidenceContract> {
    return this.request(`/api/v1/contracts/${encodeURIComponent(contractId)}`, {}, options);
  }

  exportEvidenceContract(
    workflowRunId: string,
    contractId: string,
    options?: RequestOptions,
  ): Promise<EvidenceContract> {
    return this.request(
      `/api/v1/runs/${encodeURIComponent(workflowRunId)}/contracts/${encodeURIComponent(contractId)}/export`,
      { method: "POST" },
      options,
    );
  }

  verifyAuditChain(workflowRunId: string, options?: RequestOptions): Promise<AuditIntegrityResult> {
    return this.request(`/api/v1/runs/${encodeURIComponent(workflowRunId)}/audit/verify`, {}, options);
  }

  replayWorkflowRun(workflowRunId: string, options?: RequestOptions): Promise<ReplayCertificate> {
    return this.request(`/api/v1/runs/${encodeURIComponent(workflowRunId)}/replay`, { method: "POST" }, options);
  }

  runCounterfactual(
    workflowRunId: string,
    payload: { candidate_id: string; counterfactual_type: CounterfactualType; evidence_span_id?: string; source_record_id?: string; claim_id?: string },
    options?: RequestOptions,
  ): Promise<CounterfactualCertificate> {
    return this.request(`/api/v1/runs/${encodeURIComponent(workflowRunId)}/counterfactuals`, { method: "POST", body: JSON.stringify(payload) }, options);
  }

  async submitReviewOutcome(caseId: string, decision: ReviewDecision, options?: RequestOptions): Promise<ReviewReceipt> {
    const aliases: Record<string, string> = {
      escalate_authorized_review: "escalate_for_authorized_review",
      mark_unrelated: "mark_records_unrelated",
    };
    return this.request("/api/v1/reviews", {
      method: "POST",
      body: JSON.stringify({
        case_id: caseId,
        candidate_id: decision.candidate_id,
        outcome: aliases[decision.outcome] ?? decision.outcome,
        reviewer_id: decision.reviewer_role,
        notes: decision.notes,
        rationale: decision.notes,
        remaining_uncertainty: decision.remaining_uncertainty ?? [],
        requested_evidence: decision.requested_evidence ?? [],
        workflow_run_id: decision.workflow_run_id,
        contract_id: decision.contract_id,
        referenced_artifact_ids: decision.referenced_artifact_ids ?? [],
      }),
    }, options);
  }

  getCaseAudit(caseId: string, options?: RequestOptions): Promise<import("@/types").AuditEvent[]> {
    return this.request(`/api/v1/cases/${encodeURIComponent(caseId)}/audit`, {}, options);
  }

  getStoredResult(resultId: string, options?: RequestOptions): Promise<StoredResult> {
    return this.request(`/api/v1/results/${encodeURIComponent(resultId)}`, {}, options);
  }

  listStoredResults(options?: RequestOptions): Promise<StoredResultSummary[]> {
    return this.request("/api/v1/results", {}, options);
  }

  exportResultManifest(resultId: string, format: ExportManifest["format"], options?: RequestOptions): Promise<ExportManifest> {
    return this.request(`/api/v1/results/${encodeURIComponent(resultId)}/export`, { method: "POST", body: JSON.stringify({ format }) }, options);
  }

  createBenchmarkJob(payload: BenchmarkJobRequest, options?: RequestOptions): Promise<JobStatus> {
    return this.request("/api/v1/jobs/benchmark", { method: "POST", body: JSON.stringify(payload) }, options);
  }

  createAblationJob(
    payload: { configuration: BackendBenchmarkConfig; disabled_nodes: string[]; provider_mode: ProviderMode },
    options?: RequestOptions,
  ): Promise<JobStatus> {
    return this.request("/api/v1/jobs/ablation", { method: "POST", body: JSON.stringify(payload) }, options);
  }

  createTrialJob(payload: TrialCreateRequest, options?: RequestOptions): Promise<JobStatus> {
    return this.request("/api/v1/jobs/trial", { method: "POST", body: JSON.stringify(payload) }, options);
  }

  getJob(jobId: string, options?: RequestOptions): Promise<JobStatus> {
    return this.request(`/api/v1/jobs/${encodeURIComponent(jobId)}`, {}, options);
  }

  cancelJob(jobId: string, options?: RequestOptions): Promise<JobStatus> {
    return this.request(`/api/v1/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" }, options);
  }
}

// Same-origin by default through the Next.js rewrite so a clean local checkout
// does not depend on a build-time public environment variable. Deployments may
// still provide an absolute public API URL when their topology requires one.
export const apiUrl =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "/backend-api";
export const threadlineService = new ThreadlineApiClient(apiUrl);
