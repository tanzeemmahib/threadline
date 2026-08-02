# Threat model

## Protected boundaries

- Untrusted record text is evidence, never instructions.
- Evaluation ground truth never enters model prompts.
- Original evidence and provenance remain immutable and cited by offsets.
- API keys remain server-side and are removed from exports.
- Candidate classifications cannot represent confirmed identity.
- Authorized human review is mandatory for external action.

## Considered threats

Prompt injection, schema-invalid model output, unsupported evidence, rival collapse, timeline mistakes, translation loss, common-name collisions, privacy leakage, accidental fixture/measurement confusion, runaway provider concurrency, oversized requests, cancelled jobs, restart data loss, and credential leakage through reports.

Controls include quarantine before model-backed stages, structured Pydantic validation, retries with bounded timeout/concurrency, deterministic evidence checks, contradiction/rival/adjudication stages, privacy gating, SQLite durability, persisted job states, export scrubbing, explicit mode labels, and synthetic-only tests.

## Residual risk

Pattern quarantine is not universal prompt-injection protection. Translation and extraction coverage are limited. SQLite does not provide distributed multi-worker coordination. Authentication, authorization, encryption, retention, backups, incident response, and field validation remain deployment responsibilities. No benchmark result establishes operational safety.
