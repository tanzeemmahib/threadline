# THREADLINE data responsibility and threat boundary

Status: synthetic research demonstration; not validated for operational humanitarian use  
Default execution: deterministic mock provider; no network or API key required

## Scope and prior work

THREADLINE does not claim to have invented digital missing-person record matching. The ICRC's [Missing Persons Digital Matching tool](https://www.icrc.org/sites/default/files/media_file/2024-12/MPDM_tool_A4_1%20pager.pdf) already describes multilingual matching, database search, human analysis of candidate results, and data-protection safeguards in operational humanitarian work.

THREADLINE's narrower research contribution is an inspectable safety and review layer around proposed record connections:

- exact claim-to-source lineage;
- adversarial contradiction analysis;
- retained rival hypotheses;
- tested prompt-injection quarantine;
- deterministic release rules around probabilistic model stages;
- replay and counterfactual certificates; and
- safety-weighted synthetic benchmarking.

This design direction is informed by the ICRC [Handbook on Data Protection in Humanitarian Action](https://www.icrc.org/en/data-protection-humanitarian-action-handbook), which treats personal-data protection as part of protecting dignity, and the [revised OCHA Data Responsibility Guidelines](https://centre.humdata.org/revised-ocha-data-responsibility-guidelines/), which frame data responsibility as safe, ethical, and effective data management in operational response. THREADLINE does not claim compliance with those organizations' policies or validation by either organization.

## Data inventory

The repository and deterministic demo contain fictional identities only.

| Data | Source | Purpose | Current location |
| --- | --- | --- | --- |
| Synthetic record text and metadata | Repository fixtures or local API request | Evidence extraction and comparison | Fixture files and local SQLite |
| Incident settings and workflow options | Local API request | Safety limits and deterministic behavior | Local SQLite with analysis input |
| Extracted fields and exact source spans | Model/mock output plus deterministic validation | Inspectable evidence claims | Workflow response, contracts, local SQLite |
| Normalized representations | Model/mock output plus deterministic helpers | Comparison only | Workflow response and local SQLite |
| Candidate pairs, conflicts, rivals, and review packets | Retrieval, model/mock, and deterministic stages | Authorized review preparation | Workflow response and local SQLite |
| Prompt/template and provider metadata | Runtime configuration | Reproduction and audit | Run traces, manifests, saved artifacts |
| Ground truth | Synthetic benchmark fixture | Evaluation only | Separate fixture and evaluation artifacts; not included in model prompts |
| Audit, replay, and counterfactual artifacts | Deterministic services | Traceability and tested sensitivity | Local SQLite and explicit exports |

The frontend does not intentionally persist case data in cookies, `localStorage`, `sessionStorage`, or IndexedDB. Browser state is in-memory for the current session. A deployed reverse proxy, hosting platform, browser extension, or network intermediary could add logging outside this repository.

## Storage and retention

- The backend default is local SQLite at `backend/data/threadline.db` or `THREADLINE_DATABASE_PATH`.
- Analysis inputs, workflow responses, results, evidence contracts, replay manifests, audit events, reviews, benchmark/trial outputs, and exports can be persisted.
- Export files default to `backend/data/exports` or `THREADLINE_EXPORT_DIRECTORY`.
- Archived live-provider research artifacts under `backend/data/live_runs*` contain fictional benchmark inputs and raw model outputs.
- No automatic expiration, retention schedule, subject-request workflow, or deletion API exists.
- Local deletion requires an operator to remove the relevant database/export files according to an external policy. The repository does not implement secure erasure or backup deletion.

Operational use would require approved retention schedules, deletion procedures, backup handling, legal-basis review, data residency decisions, and accountable ownership. These are future requirements, not existing controls.

## What is sent to a model provider

The default deterministic demo sends nothing to an external provider.

When `LLM_PROVIDER=openai_compatible`, five ordered stages can send data to the configured endpoint:

1. `extract`: quarantined record text wrapped as untrusted evidence, plus the extraction schema and canonical field keys;
2. `normalize`: original name form, source metadata, and deterministic candidate representations;
3. `hypothesis`: structured candidate evidence;
4. `prosecutor`: structured candidate evidence for isolated contradiction analysis; and
5. `adjudicate`: structured support, opposition, rival, and deterministic decision packets.

The privacy gate is node 11, after these model-backed stages. It reduces reviewer-facing disclosure; it is **not** provider-side data minimization. Connected deployment would need provider agreements, regional processing controls, an approved minimum payload, logging policy, and a model-access threat assessment.

## Access boundary

Existing controls:

- credentials remain server-side and are not placed in `NEXT_PUBLIC_*` variables;
- CORS origins are configured;
- provider credentials are omitted from structured exports by key name;
- model text is schema validated; and
- all product outputs remain review packets rather than autonomous determinations.

Not implemented:

- user authentication;
- role-based authorization;
- case-level access control;
- encryption at rest;
- field-level encryption;
- production secret management;
- reviewer identity assurance;
- consent or lawful-basis workflow; and
- multi-tenant isolation.

The local demonstration must therefore be treated as a single-operator synthetic environment.

## Data minimization and redaction

- Request size and candidate count are bounded.
- Candidate retrieval is top-k and evidence fields remain typed.
- Original source text is preserved; normalized representations are additive and cannot overwrite it.
- Reviewer-facing `safe_text` receives deterministic redactions at the privacy gate, and redaction events are audited.
- Ground truth is separated from analysis requests.

The current redactor is pattern based. It does not guarantee discovery of every sensitive value. Because exact evidence spans are a core research feature, source quotations and offsets may remain in review packets and exports.

## Logging, audit, and redaction

The application records structured workflow and audit events, including source IDs, transformation summaries, reason codes, prompt/template identifiers, validation outcomes, and event hashes. Some audit fields and exports can contain record evidence. Hash chaining provides tamper evidence for chained event metadata and payloads; it does not prevent offline database modification or cryptographically seal every current result row.

Credential scrubbing removes dictionary keys named `api_key`, `authorization`, `token`, `secret`, or `password`. It is not a general personal-data scrubber. Operators must inspect any export before sharing it.

## Prompt-injection boundary

Source narratives are treated as untrusted evidence. The quarantine node detects tested instruction patterns, preserves the original text, creates a downstream-safe representation, and prevents record content from entering system messages. Model responses must pass strict structured-output validation.

Residual risk remains:

- pattern detection does not cover every injection strategy;
- an allowed evidence span can still contain manipulative text;
- a connected provider can behave differently over time;
- structured output can be semantically wrong while schema valid; and
- later model nodes receive structured evidence derived from earlier model output.

Deterministic source-span validation, contradiction checks, rival analysis, evidence contracts, and human review reduce but do not eliminate these risks.

## Export and sharing risks

Exports may contain exact fictional source quotations, timestamps, location evidence, candidate IDs, contradictions, and reviewer notes. In an operational system these fields could be highly sensitive. Existing export scrubbing removes credential-shaped keys only. It does not enforce purpose limitation, recipient authorization, disclosure-risk review, watermarking, expiration, or revocation.

Required future controls include export approval, least-privilege recipient selection, field-level policy, disclosure review, access logging, encryption, revocation, and incident response.

## Threat register

| Threat | Existing detection/mitigation | Residual limitation |
| --- | --- | --- |
| Prompt injection in record text | Quarantine, untrusted-evidence wrappers, schema validation | Pattern coverage is incomplete |
| Fabricated citation | Exact half-open quote/offset validation and evidence-contract block | Real evidence can still be missed |
| Model weakens a hard conflict | Deterministic conflicts are restored; adjudication may only preserve or downgrade | An unextracted conflict remains invisible |
| Leading-candidate tunnel vision | Rival-candidate test and explicit abstention | Retrieval can miss the true rival |
| Unsafe release after policy failure | Deterministic evidence contract clears releasable classification | Downstream consumers must honor withheld state |
| Audit-event modification | Hash-chain verification identifies first invalid event | Does not prevent offline modification |
| Provider drift | Prompt/provider/model metadata and deterministic mock replay | Connected-provider exact replay is not implemented |
| Unauthorized access | None beyond local process and configured CORS | Authentication and authorization are absent |
| Excessive retention | None | Retention/deletion policy and automation are absent |
| Unsafe export sharing | Credential-key scrubbing and content hash | Evidence itself is not automatically redacted |

## Operational validation still required

Before any field use, an accountable humanitarian organization would need representative authorized data, privacy and data-protection impact assessment, affected-population consultation, security review, access control, retention and incident-response policy, reviewer training, escalation procedures, subgroup evaluation, language coverage analysis, monitoring, and independent governance.

THREADLINE has completed none of that real-world validation. Its measured results apply only to the versioned synthetic artifacts in this repository.
