import "server-only";

import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { cache } from "react";
import type reveriePromptLabShape from "../../../docs/submission/reverie-prompt-lab.json";
import type submissionResultsShape from "../../../docs/submission/results.json";

export type ReveriePromptLabArtifact = typeof reveriePromptLabShape;
export type SubmissionResultsArtifact = typeof submissionResultsShape;

export type ReverieLiveEvaluationMetrics = {
  schema_valid: boolean;
  available_source_span_count: number;
  cited_source_span_count: number;
  exact_citation_count: number;
  invalid_citation_count: number;
  exact_citation_validity: number | null;
  source_span_coverage: number | null;
  supported_field_count: number;
  unsupported_field_count: number;
  missed_field_count: number;
  identity_outcome: string;
  outcome_within_accepted_set: boolean;
  deterministic_conflict_handling: boolean;
  provider_call_count: number;
  transport_attempt_count: number;
  latency_ms: number;
  token_usage: number | null;
};

export type ReverieLiveEvaluationSystemRun = {
  system_run_id: string;
  case_id: string;
  repetition: number;
  system_id: "structured_one_shot" | "full_threadline";
  status: "ok" | "error" | "not_run";
  input_manifest: unknown;
  same_input_verified: boolean;
  safe_provider_config_sha256: string;
  logical_call_ids: string[];
  resumed_logical_call_ids: string[];
  started_at: string;
  completed_at: string | null;
  raw_output: unknown;
  validated_output: unknown;
  metrics: ReverieLiveEvaluationMetrics | null;
  error: unknown;
};

export type ReverieLiveEvaluationArtifact = {
  schema_version: "threadline-reverie-live-evaluation-results/1.0.0";
  artifact_id: string;
  status: "complete" | "partial" | "failed";
  evaluation_label: "Measured live-provider comparison";
  synthetic_only: true;
  safety_scope: string;
  spec_id: string;
  spec_path: string;
  spec_sha256: string;
  source_commit: string;
  provider: {
    mode: string;
    base_url: string;
    model: string;
    temperature: number;
    timeout_seconds: number;
    max_transport_retries: number;
    max_schema_repair_attempts: number;
    max_concurrent_calls: number;
    seed: null;
    seed_status: string;
    response_format_policy: string;
  };
  same_input_and_config_verified: boolean;
  expected_system_runs: number;
  completed_system_runs: number;
  failed_system_runs: number;
  started_at: string;
  updated_at: string;
  completed_at: string | null;
  recorder_artifact_path: string;
  recorder_artifact_sha256: string;
  cases: Array<{
    case_id: string;
    kind: string;
    repetition: number;
    input_manifest: unknown;
    systems: {
      structured_one_shot?: ReverieLiveEvaluationSystemRun;
      full_threadline?: ReverieLiveEvaluationSystemRun;
    };
  }>;
  aggregate: unknown;
  limitations: string[];
};

export type ReverieLiveEvaluationRunSummary = Pick<
  ReverieLiveEvaluationSystemRun,
  "system_run_id" | "status" | "same_input_verified" | "metrics"
> & { technical_output_sha256: string | null };

export type ReverieLiveRunTechnicalOutput = Pick<
  ReverieLiveEvaluationSystemRun,
  | "system_run_id"
  | "case_id"
  | "repetition"
  | "system_id"
  | "status"
  | "same_input_verified"
  | "safe_provider_config_sha256"
  | "logical_call_ids"
  | "resumed_logical_call_ids"
  | "started_at"
  | "completed_at"
  | "raw_output"
  | "validated_output"
  | "metrics"
  | "error"
>;

export type ReverieLiveEvaluationSummary = Pick<
  ReverieLiveEvaluationArtifact,
  | "artifact_id"
  | "status"
  | "evaluation_label"
  | "safety_scope"
  | "spec_id"
  | "spec_sha256"
  | "source_commit"
  | "same_input_and_config_verified"
  | "expected_system_runs"
  | "completed_system_runs"
  | "failed_system_runs"
  | "completed_at"
  | "recorder_artifact_sha256"
  | "limitations"
> & {
  artifact_sha256: string;
  provider: Pick<ReverieLiveEvaluationArtifact["provider"], "mode" | "model" | "temperature" | "seed_status">;
  cases: Array<{
    case_id: string;
    kind: string;
    repetition: number;
    systems: {
      structured_one_shot?: ReverieLiveEvaluationRunSummary;
      full_threadline?: ReverieLiveEvaluationRunSummary;
    };
  }>;
};

export type ReverieLiveEvaluationState =
  | { state: "not_measured"; message: string }
  | { state: "invalid"; message: string }
  | { state: "incomplete"; message: string; artifact: ReverieLiveEvaluationSummary; source: "locked_submission" }
  | { state: "complete"; artifact: ReverieLiveEvaluationSummary; source: "locked_submission" };

export class ReverieArtifactError extends Error {
  constructor(
    public readonly code:
      | "ARTIFACT_READ_FAILED"
      | "ARTIFACT_PARSE_FAILED"
      | "ARTIFACT_SCHEMA_INVALID"
      | "ARTIFACT_PROVENANCE_INVALID",
    message: string,
  ) {
    super(message);
    this.name = "ReverieArtifactError";
  }
}

type JsonObject = Record<string, unknown>;

const repositoryRoot = path.resolve(process.cwd(), "..");

const submissionArtifactPath = (filename: string) =>
  path.resolve(process.cwd(), "..", "docs", "submission", filename);

const lockedLiveEvaluationArtifactPath = submissionArtifactPath("reverie-live-evaluation-results.json");
const liveEvaluationManifestPath = submissionArtifactPath("reverie-live-evaluation-manifest.json");

function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requireArtifact(condition: unknown, message: string): asserts condition {
  if (!condition) throw new ReverieArtifactError("ARTIFACT_SCHEMA_INVALID", message);
}

function sameStringMembers(left: unknown, right: unknown) {
  return Array.isArray(left)
    && Array.isArray(right)
    && left.length === right.length
    && left.every((value, index) => typeof value === "string" && value === right[index]);
}

async function readSubmissionArtifact(filename: string): Promise<unknown> {
  let contents: string;
  try {
    contents = await readFile(submissionArtifactPath(filename), "utf8");
  } catch {
    throw new ReverieArtifactError("ARTIFACT_READ_FAILED", `Required submission artifact ${filename} is unavailable.`);
  }

  try {
    return JSON.parse(contents) as unknown;
  } catch {
    throw new ReverieArtifactError("ARTIFACT_PARSE_FAILED", `Required submission artifact ${filename} is malformed.`);
  }
}

function validatePromptLabArtifact(value: unknown): asserts value is ReveriePromptLabArtifact {
  requireArtifact(isObject(value), "Prompt Lab evidence must be a JSON object.");
  requireArtifact(value.artifact_id === "THREADLINE-REVERIE-PROMPT-LAB-V1", "Unexpected Prompt Lab artifact identity.");
  requireArtifact(value.schema_version === "threadline-reverie-prompt-lab/1.0.0", "Unsupported Prompt Lab artifact schema.");
  requireArtifact(value.synthetic_only === true, "Prompt Lab evidence must be explicitly synthetic.");
  requireArtifact(Array.isArray(value.cases) && value.cases.length === 3, "Prompt Lab requires exactly three locked comparison cases.");

  const requiredKinds = ["cross_script_partial", "shared_contact_insufficient", "blocking_identity_conflict"];
  for (const [index, rawCase] of value.cases.entries()) {
    requireArtifact(isObject(rawCase), `Prompt Lab case ${index + 1} is malformed.`);
    requireArtifact(rawCase.kind === requiredKinds[index], `Prompt Lab case ${index + 1} has an unexpected case kind.`);
    requireArtifact(rawCase.synthetic_only === true && rawCase.identical_input_verified === true, `Prompt Lab case ${index + 1} failed its synthetic or identical-input guard.`);
    requireArtifact(isObject(rawCase.input_manifest) && Array.isArray(rawCase.input_manifest.record_ids), `Prompt Lab case ${index + 1} has no input manifest.`);
    requireArtifact(Array.isArray(rawCase.records) && rawCase.records.length >= 2, `Prompt Lab case ${index + 1} has incomplete source records.`);
    requireArtifact(Array.isArray(rawCase.source_spans), `Prompt Lab case ${index + 1} has no source-span evidence.`);
    requireArtifact(isObject(rawCase.systems) && isObject(rawCase.systems.one_shot) && isObject(rawCase.systems.threadline), `Prompt Lab case ${index + 1} has incomplete system outputs.`);
    requireArtifact(sameStringMembers(rawCase.systems.one_shot.candidate_record_ids, rawCase.input_manifest.record_ids), `Prompt Lab case ${index + 1} one-shot input drifted.`);
    requireArtifact(sameStringMembers(rawCase.systems.threadline.candidate_record_ids, rawCase.input_manifest.record_ids), `Prompt Lab case ${index + 1} workflow input drifted.`);

    const records = new Map<string, string>();
    for (const rawRecord of rawCase.records) {
      requireArtifact(isObject(rawRecord) && typeof rawRecord.record_id === "string" && typeof rawRecord.text === "string", `Prompt Lab case ${index + 1} contains a malformed source record.`);
      records.set(rawRecord.record_id, rawRecord.text);
    }
    for (const rawSpan of rawCase.source_spans) {
      requireArtifact(isObject(rawSpan) && typeof rawSpan.record_id === "string" && typeof rawSpan.quote === "string" && typeof rawSpan.start === "number" && typeof rawSpan.end === "number", `Prompt Lab case ${index + 1} contains a malformed source span.`);
      const source = records.get(rawSpan.record_id);
      requireArtifact(rawSpan.valid === true && source?.slice(rawSpan.start, rawSpan.end) === rawSpan.quote, `Prompt Lab case ${index + 1} contains a source span that does not resolve exactly.`);
    }

    requireArtifact(isObject(rawCase.decision), `Prompt Lab case ${index + 1} has no deterministic decision.`);
    const expectedDecision = rawCase.kind === "blocking_identity_conflict" ? "blocked_by_conflict" : "human_review_required";
    requireArtifact(rawCase.decision.state === expectedDecision, `Prompt Lab case ${index + 1} has an unsafe decision state.`);
    if (expectedDecision === "blocked_by_conflict") {
      requireArtifact(rawCase.decision.release_allowed_for_authorized_review === false, "Blocking-conflict case must fail closed.");
    }
  }

  requireArtifact(isObject(value.winning_story), "Winning-story evidence is unavailable.");
  requireArtifact(sameStringMembers(value.winning_story.supported_pair, ["FAMILY-018", "SHELTER-204"]), "Winning-story supported pair drifted.");
  requireArtifact(sameStringMembers(value.winning_story.blocked_rival_pair, ["FAMILY-018", "HOSPITAL-052"]), "Winning-story blocked rival drifted.");
  requireArtifact(isObject(value.prompt_iterations) && isObject(value.prompt_iterations.promotion_decision), "Prompt promotion evidence is unavailable.");
  requireArtifact(value.prompt_iterations.promotion_decision.production_version === "v2" && value.prompt_iterations.promotion_decision.not_promoted === "v3", "Prompt promotion boundary drifted.");
  requireArtifact(value.prompt_iterations.promotion_decision.reason_code === "PRECISION_REGRESSION", "Prompt V3 rejection reason drifted.");
}

function validateSubmissionResults(value: unknown): asserts value is SubmissionResultsArtifact {
  requireArtifact(isObject(value), "Submission results must be a JSON object.");
  requireArtifact(value.artifact_id === "THREADLINE-SUBMISSION-EVIDENCE-V1", "Unexpected submission-results artifact identity.");
  requireArtifact(value.schema_version === "threadline-submission-evidence/1.0.0", "Unsupported submission-results artifact schema.");
  requireArtifact(value.synthetic_only === true, "Submission results must be explicitly synthetic.");
  requireArtifact(isObject(value.judge_case_comparison), "Judge comparison evidence is unavailable.");
  requireArtifact(isObject(value.judge_case_comparison.same_input_verification) && value.judge_case_comparison.same_input_verification.exact_input_shared === true, "Judge comparison input equality is not verified.");
  requireArtifact(
    isObject(value.archived_live_prompt_v2)
      && value.archived_live_prompt_v2.artifact_id === "THREADLINE-LIVE-PROMPT-V2-FULL-RUN-1"
      && value.archived_live_prompt_v2.execution_mode === "live_provider"
      && typeof value.archived_live_prompt_v2.evaluation_label === "string"
      && value.archived_live_prompt_v2.evaluation_label.startsWith("Archived measured live-provider extraction run"),
    "Archived Prompt V2 evidence is missing or mislabeled.",
  );
}

function validateLiveEvaluationArtifact(value: unknown): asserts value is ReverieLiveEvaluationArtifact {
  requireArtifact(isObject(value), "Live evaluation must be a JSON object.");
  requireArtifact(value.schema_version === "threadline-reverie-live-evaluation-results/1.0.0", "Unsupported live-evaluation schema.");
  requireArtifact(typeof value.artifact_id === "string" && value.artifact_id.length > 0, "Live evaluation has no artifact identity.");
  requireArtifact(["complete", "partial", "failed"].includes(String(value.status)), "Live evaluation has an invalid status.");
  requireArtifact(value.evaluation_label === "Measured live-provider comparison" && value.synthetic_only === true, "Live evaluation is missing its measured or synthetic label.");
  requireArtifact(typeof value.same_input_and_config_verified === "boolean", "Live evaluation is missing its same-input/configuration guard.");
  requireArtifact(typeof value.expected_system_runs === "number" && typeof value.completed_system_runs === "number" && typeof value.failed_system_runs === "number", "Live evaluation run counts are malformed.");
  requireArtifact(value.expected_system_runs === 18 && value.completed_system_runs + value.failed_system_runs <= value.expected_system_runs, "Live evaluation run counts are inconsistent.");
  requireArtifact(isObject(value.provider) && typeof value.provider.model === "string" && typeof value.provider.temperature === "number", "Live evaluation provider configuration is malformed.");
  requireArtifact(Array.isArray(value.cases) && Array.isArray(value.limitations), "Live evaluation cases or limitations are malformed.");

  for (const rawCase of value.cases) {
    requireArtifact(isObject(rawCase) && typeof rawCase.case_id === "string" && typeof rawCase.repetition === "number" && isObject(rawCase.systems), "Live evaluation contains a malformed case run.");
    for (const systemName of ["structured_one_shot", "full_threadline"] as const) {
      const rawSystem = rawCase.systems[systemName];
      if (rawSystem === undefined) continue;
      requireArtifact(isObject(rawSystem) && rawSystem.system_id === systemName, `Live evaluation ${systemName} run is malformed.`);
      requireArtifact(["ok", "error", "not_run"].includes(String(rawSystem.status)), `Live evaluation ${systemName} run has an invalid status.`);
      requireArtifact(typeof rawSystem.same_input_verified === "boolean", `Live evaluation ${systemName} run has no input verification state.`);
      if (rawSystem.status === "ok") {
        requireArtifact(
          isObject(rawSystem.metrics)
            && typeof rawSystem.metrics.schema_valid === "boolean"
            && typeof rawSystem.metrics.identity_outcome === "string"
            && typeof rawSystem.metrics.available_source_span_count === "number"
            && typeof rawSystem.metrics.cited_source_span_count === "number"
            && typeof rawSystem.metrics.exact_citation_count === "number"
            && typeof rawSystem.metrics.unsupported_field_count === "number"
            && typeof rawSystem.metrics.deterministic_conflict_handling === "boolean",
          `Live evaluation ${systemName} metrics are malformed.`,
        );
      }
    }
  }

  if (value.status === "complete") {
    requireArtifact(value.completed_system_runs + value.failed_system_runs === value.expected_system_runs, "Complete live evaluation does not account for every expected system run.");
    requireArtifact(value.cases.length * 2 === value.expected_system_runs, "Complete live evaluation does not contain every case repetition.");
    for (const rawCase of value.cases) {
      requireArtifact(isObject(rawCase) && isObject(rawCase.systems) && isObject(rawCase.systems.structured_one_shot) && isObject(rawCase.systems.full_threadline), "Complete live evaluation is missing a system run for a case repetition.");
      for (const systemName of ["structured_one_shot", "full_threadline"] as const) {
        const rawSystem = rawCase.systems[systemName];
        requireArtifact(isObject(rawSystem) && rawSystem.status === "ok" && rawSystem.same_input_verified === true && isObject(rawSystem.metrics), "Complete live evaluation contains an unsuccessful or unverified system run.");
      }
    }
  }
}

async function validatePromptSources(artifact: ReveriePromptLabArtifact) {
  for (const prompt of Object.values(artifact.prompt_iterations.prompts)) {
    const sourcePath = path.resolve(repositoryRoot, prompt.source_path);
    const relative = path.relative(repositoryRoot, sourcePath);
    if (relative.startsWith("..") || path.isAbsolute(relative)) {
      throw new ReverieArtifactError("ARTIFACT_PROVENANCE_INVALID", "Prompt provenance resolves outside the repository.");
    }
    let contents: string;
    try {
      contents = await readFile(sourcePath, "utf8");
    } catch {
      throw new ReverieArtifactError("ARTIFACT_PROVENANCE_INVALID", `Prompt source ${prompt.source_path} is unavailable.`);
    }
    const digest = createHash("sha256").update(contents).digest("hex");
    if (digest !== prompt.sha256) {
      throw new ReverieArtifactError("ARTIFACT_PROVENANCE_INVALID", `Prompt source ${prompt.source_path} no longer matches its locked digest.`);
    }
  }
}

async function validateLockedLiveEvaluationProvenance(contents: string, artifact: ReverieLiveEvaluationArtifact) {
  let manifest: unknown;
  try {
    manifest = JSON.parse(await readFile(liveEvaluationManifestPath, "utf8")) as unknown;
  } catch {
    throw new ReverieArtifactError("ARTIFACT_PROVENANCE_INVALID", "The publication manifest for the live evaluation is unavailable or malformed.");
  }
  requireArtifact(
    isObject(manifest)
      && manifest.schema_version === "threadline-reverie-live-evaluation-publication/1.0.0"
      && manifest.artifact_id === artifact.artifact_id
      && manifest.status === "complete"
      && manifest.synthetic_only === true
      && manifest.same_input_and_config_verified === true,
    "The live evaluation publication manifest failed its identity or completion guard.",
  );
  requireArtifact(isObject(manifest.spec) && manifest.spec.path === artifact.spec_path && manifest.spec.sha256 === artifact.spec_sha256, "The live evaluation publication manifest does not pin the frozen spec.");
  requireArtifact(
    isObject(manifest.results)
      && manifest.results.submission_path === "docs/submission/reverie-live-evaluation-results.json"
      && manifest.results.byte_identical === true
      && typeof manifest.results.sha256 === "string",
    "The live evaluation publication manifest does not pin the submission result.",
  );
  requireArtifact(
    isObject(manifest.raw_provider_recorder)
      && manifest.raw_provider_recorder.sha256 === artifact.recorder_artifact_sha256
      && manifest.raw_provider_recorder.contains_credentials === false,
    "The live evaluation publication manifest does not pin a credential-free provider recorder.",
  );
  requireArtifact(
    isObject(manifest.validation)
      && manifest.validation.complete_system_runs === artifact.completed_system_runs
      && manifest.validation.expected_system_runs === artifact.expected_system_runs
      && manifest.validation.failed_system_runs === artifact.failed_system_runs,
    "The live evaluation publication manifest run-count validation drifted.",
  );
  const digest = createHash("sha256").update(contents).digest("hex");
  requireArtifact(manifest.results.sha256 === digest, "The published live evaluation no longer matches its publication-manifest digest.");
}

function technicalRunOutput(run: ReverieLiveEvaluationSystemRun): ReverieLiveRunTechnicalOutput {
  return {
    system_run_id: run.system_run_id,
    case_id: run.case_id,
    repetition: run.repetition,
    system_id: run.system_id,
    status: run.status,
    same_input_verified: run.same_input_verified,
    safe_provider_config_sha256: run.safe_provider_config_sha256,
    logical_call_ids: run.logical_call_ids,
    resumed_logical_call_ids: run.resumed_logical_call_ids,
    started_at: run.started_at,
    completed_at: run.completed_at,
    raw_output: run.raw_output,
    validated_output: run.validated_output,
    metrics: run.metrics,
    error: run.error,
  };
}

function serializeTechnicalRunOutput(run: ReverieLiveEvaluationSystemRun) {
  return JSON.stringify(technicalRunOutput(run), null, 2);
}

function summarizeLiveEvaluation(artifact: ReverieLiveEvaluationArtifact, contents: string): ReverieLiveEvaluationSummary {
  const summarizeRun = (run: ReverieLiveEvaluationSystemRun | undefined): ReverieLiveEvaluationRunSummary | undefined => run ? {
    system_run_id: run.system_run_id,
    status: run.status,
    same_input_verified: run.same_input_verified,
    metrics: run.metrics,
    technical_output_sha256: createHash("sha256").update(serializeTechnicalRunOutput(run)).digest("hex"),
  } : undefined;

  return {
    artifact_id: artifact.artifact_id,
    artifact_sha256: createHash("sha256").update(contents).digest("hex"),
    status: artifact.status,
    evaluation_label: artifact.evaluation_label,
    safety_scope: artifact.safety_scope,
    spec_id: artifact.spec_id,
    spec_sha256: artifact.spec_sha256,
    source_commit: artifact.source_commit,
    provider: {
      mode: artifact.provider.mode,
      model: artifact.provider.model,
      temperature: artifact.provider.temperature,
      seed_status: artifact.provider.seed_status,
    },
    same_input_and_config_verified: artifact.same_input_and_config_verified,
    expected_system_runs: artifact.expected_system_runs,
    completed_system_runs: artifact.completed_system_runs,
    failed_system_runs: artifact.failed_system_runs,
    completed_at: artifact.completed_at,
    recorder_artifact_sha256: artifact.recorder_artifact_sha256,
    cases: artifact.cases.map((item) => ({
      case_id: item.case_id,
      kind: item.kind,
      repetition: item.repetition,
      systems: {
        structured_one_shot: summarizeRun(item.systems.structured_one_shot),
        full_threadline: summarizeRun(item.systems.full_threadline),
      },
    })),
    limitations: artifact.limitations,
  };
}

export const loadReverieEvidence = cache(async (): Promise<ReveriePromptLabArtifact> => {
  const artifact = await readSubmissionArtifact("reverie-prompt-lab.json");
  validatePromptLabArtifact(artifact);
  await validatePromptSources(artifact);
  return artifact;
});

export const loadSubmissionResults = cache(async (): Promise<SubmissionResultsArtifact> => {
  const artifact = await readSubmissionArtifact("results.json");
  validateSubmissionResults(artifact);
  return artifact;
});

export const loadReverieLiveEvaluation = cache(async (): Promise<ReverieLiveEvaluationState> => {
  let contents: string;
  try {
    contents = await readFile(lockedLiveEvaluationArtifactPath, "utf8");
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return { state: "not_measured", message: "No locked same-model live evaluation artifact is present." };
    }
    return { state: "invalid", message: "The locked live evaluation artifact could not be read safely." };
  }

  let artifact: unknown;
  try {
    artifact = JSON.parse(contents) as unknown;
    validateLiveEvaluationArtifact(artifact);
    await validateLockedLiveEvaluationProvenance(contents, artifact);
  } catch {
    return { state: "invalid", message: "The live evaluation artifact failed schema or release-provenance validation." };
  }

  const summary = summarizeLiveEvaluation(artifact, contents);

  if (artifact.status !== "complete" || !artifact.same_input_and_config_verified) {
    return {
      state: "incomplete",
      message: artifact.status === "complete"
        ? "The run completed without a verified same-input and provider-configuration boundary. Comparative claims remain withheld."
        : `The measured live-provider comparison is ${artifact.status}; incomplete results are not promoted to headline evidence.`,
      artifact: summary,
      source: "locked_submission",
    };
  }
  return { state: "complete", artifact: summary, source: "locked_submission" };
});

export async function loadReverieLiveRunOutput(systemRunId: string): Promise<{ output: string; sha256: string } | null> {
  const state = await loadReverieLiveEvaluation();
  if (state.state !== "complete") return null;

  const contents = await readFile(lockedLiveEvaluationArtifactPath, "utf8");
  const artifact = JSON.parse(contents) as unknown;
  validateLiveEvaluationArtifact(artifact);
  await validateLockedLiveEvaluationProvenance(contents, artifact);
  const run = artifact.cases.flatMap((item) => Object.values(item.systems)).find((candidate) => candidate?.system_run_id === systemRunId);
  if (!run) return null;
  const output = serializeTechnicalRunOutput(run);
  const sha256 = createHash("sha256").update(output).digest("hex");
  const summaryRun = state.artifact.cases.flatMap((item) => Object.values(item.systems)).find((candidate) => candidate?.system_run_id === systemRunId);
  if (summaryRun?.technical_output_sha256 !== sha256) {
    throw new ReverieArtifactError("ARTIFACT_PROVENANCE_INVALID", "Live run technical output drifted after publication validation.");
  }
  return { output, sha256 };
}
