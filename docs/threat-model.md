# Threat model

THREADLINE is a synthetic research demonstration for proposed record connections. It does not confirm identity, declare a person found, or autonomously merge records. The fuller data-flow and control inventory is in [`docs/submission/data-responsibility.md`](submission/data-responsibility.md).

The project acknowledges existing humanitarian practice, including the ICRC [Missing Persons Digital Matching tool](https://www.icrc.org/sites/default/files/media_file/2024-12/MPDM_tool_A4_1%20pager.pdf), the ICRC [Handbook on Data Protection in Humanitarian Action](https://www.icrc.org/en/data-protection-humanitarian-action-handbook), and the [revised OCHA Data Responsibility Guidelines](https://centre.humdata.org/revised-ocha-data-responsibility-guidelines/). These references inform scope and risk framing; they are not evidence of endorsement, compliance, or operational validation.

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

## Data-flow boundary

The default mock path sends no evidence to an external provider. In connected mode, five stages can send quarantined record text or structured evidence to the configured OpenAI-compatible endpoint: extraction, normalization, hypothesis, contradiction challenge, and adjudication. The privacy gate runs after those model stages and minimizes reviewer-facing text; it is not provider-side minimization.

The current demonstration has no authentication, role-based authorization, encryption at rest, automatic retention/deletion, data residency policy, or production secret manager. Local SQLite persists inputs, outputs, contracts, audit events, replay/counterfactual artifacts, reviews, and research results. Export scrubbing removes credential-shaped keys only; it does not generally redact record evidence.

| Threat | Detection | Mitigation | Remaining limitation |
| --- | --- | --- | --- |
| Modified audit-event metadata or payload | Payload and event hash mismatch at first invalid sequence | Fail-closed EC-014 and withheld classification | Offline modification cannot be prevented by application code |
| Modified persisted contract or result row | Not covered by the event-chain verifier in V1 | Restrict database access; compare replay/contract evidence before action | External signing or artifact-hash anchoring is required to detect arbitrary row replacement |
| Reordered, deleted, or duplicated audit event | Previous-hash, sequence-gap, and duplicate-sequence checks | Append transaction plus unique run/sequence constraint | Multi-host consensus is out of scope |
| Fabricated quote or invalid offset | EC-001 exact half-open span validation | Unsupported claims block release | Extraction coverage can still miss real facts |
| Unsupported audit/rule schema | Typed unsupported status and EC-014/EC-015 | Fail closed; require supported version | Manual migration is required for future versions |
| Altered normalized data or stale configuration | Replay manifest checkpoint divergence | Diverged replay is not verified or released | Exact connected-model replay is not yet supported |
| Prompt/model version drift | Manifested template and model identifiers | Connected replay requires frozen structured outputs | Provider internals may remain nondeterministic |
| Classification leakage after blocking | Schema permits null classification; withheld UI omits recommendation/actions | Contract clearing and API integration tests | Downstream consumers must honor contract status |
| Corrupted certificate data in UI | Missing/invalid contract renders fail-closed unavailable state | No recommendation without a valid contract | TypeScript is not a cryptographic validator |
| Removed decision-critical evidence | Persisted counterfactual reruns and before/after certificate | Human review sees first responsible node and changed outcomes | Tested mutations do not cover all combinations |

## Residual risk

Pattern quarantine is not universal prompt-injection protection. Translation and extraction coverage are limited. SQLite does not provide distributed multi-worker coordination. Authentication, authorization, encryption, retention, backups, incident response, provider governance, and field validation remain deployment responsibilities. No benchmark result establishes operational safety, humanitarian efficacy, fairness, or regulatory compliance.
