# THREADLINE API contract

Status: implemented by the FastAPI service under `backend/`. The existing frontend contract remains compatible; richer research fields are additive.

## Runtime modes

- Frontend synthetic demo mode remains the default when `NEXT_PUBLIC_API_URL` is unset.
- Connected mode uses the centralized client for all APIs. Failures are surfaced with retry/cancel state and the exact visible label `Backend unavailable — synthetic fallback active`; the client never silently substitutes fixture data.
- Backend `mock` mode is deterministic, credential-free, and network-free.
- Backend `openai_compatible` mode uses configured credentials server-side and never returns them.

## Durable resources and jobs

- `GET /api/v1/workflow-runs/{workflow_run_id}` reloads a complete analysis.
- `GET /api/v1/results` and `GET /api/v1/results/{result_id}` list/reload durable results.
- `POST /api/v1/reviews` persists an authorized review outcome; `GET /api/v1/cases/{case_id}/audit` returns its chronological ledger.
- `POST /api/v1/jobs/benchmark`, `/ablation`, and `/trial` queue bounded evaluation work.
- `GET /api/v1/jobs/{job_id}` returns queued/running/completed/failed/cancelled state, actual completed cases, stage, timestamps, result ID, error, and retryability.
- `POST /api/v1/jobs/{job_id}/cancel` cancels queued/running work while preserving completed artifacts.
- `POST /api/v1/results/{result_id}/export` emits JSON/CSV/Markdown manifests; `/report` emits a deterministic research summary.

## Trials

`GET /api/v1/trials/cases`, `POST /preview`, `POST /run`, `GET /{trial_run_id}`, and `POST /{trial_run_id}/rerun` implement the eight-fixture, 15-mutation trial contract described in [THREADLINE Trials](threadline-trials.md).

## Analysis

`POST /api/v1/analyze` accepts incident metadata, one or more narrative records, and optional `options`:

```json
{
  "incident": {
    "incident_id": "INCIDENT-NDE-001",
    "name": "North District Earthquake",
    "languages": ["English", "Arabic", "French"]
  },
  "records": [{
    "record_id": "FAMILY-018",
    "source_type": "family_report",
    "language": "English",
    "text": "My son Youssef Al Hassan, age 14..."
  }],
  "options": {
    "provider_mode": "mock",
    "include_workflow_trace": true,
    "candidate_limit": 5,
    "disabled_nodes": [],
    "adjudicator_count": 2
  }
}
```

The response retains frontend fields `case_id`, `workflow_run_id`, `status`, `summary`, `records`, `candidates`, and compact `workflow_trace`. Additive fields include `mode`, `workflow_trace_details`, `audit_events`, `safety_notices`, `human_review_requirement`, and measured `operational` counts.

Each candidate has a frontend display `classification` and an exact machine `classification_code`: `strong_candidate_for_review`, `possible_candidate`, `insufficient_evidence`, or `conflicting_evidence`. Prohibited identity claims and invented match probabilities are schema-invalid.

## Evaluation APIs

- `GET /health`
- `GET /api/v1/demo`
- `POST /api/v1/baselines/run` with `{ "case": AnalyzeRequest }`
- `POST /api/v1/benchmark/generate` with `{ "configuration": BenchmarkConfig }`
- `POST /api/v1/benchmark/run` with exactly one of `dataset` or `configuration`, plus `provider_mode` and `candidate_k`
- `POST /api/v1/ablation/run` with `configuration`, `disabled_nodes`, and `provider_mode`

The baseline endpoint always returns fuzzy, generic one-call, structured one-call, and full THREADLINE outputs on the identical case. Benchmark and ablation responses label mock output `Deterministic mock evaluation`, contain actual computed metrics, retain case-level outputs/errors, and include numerator, denominator, and formula for every metric.

## Errors

All API errors use:

```json
{
  "error": {
    "request_id": "...",
    "error_code": "INVALID_RECORD_INPUT",
    "message": "Request validation failed.",
    "retryable": false,
    "failed_stage": null,
    "preserved_data": true,
    "details": {}
  }
}
```

Codes include `INVALID_RECORD_INPUT`, `MODEL_RESPONSE_SCHEMA_FAILURE`, `EVIDENCE_VALIDATION_FAILURE`, `PROVIDER_TIMEOUT`, `BENCHMARK_CONFIGURATION_INVALID`, and `WORKFLOW_PARTIAL_FAILURE`. Raw stack traces are logged server-side and never returned.

## Compatibility

The frontend still assumes no authentication header and only the analysis endpoint. Its TypeScript `CandidateConnection` and `WorkflowNode` display fields are returned unchanged; backend snake-case classifications and rich traces are additive. Existing frontend source, routes, visual components, and types were not changed by the backend implementation.
