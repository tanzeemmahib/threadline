# THREADLINE — Reverie ML Prompt Engineering documentation

Status: synthetic research demonstration  
Workflow version: `threadline-workflow/2.0.0`  
Production extraction prompt: `extraction/v2`  
Decision boundary: possible record connections for authorized human review only

> AI extracts source-cited evidence. Deterministic comparison and conflict policies decide when the system must stop.

## 1. Research claim

THREADLINE tests whether a decomposed, source-cited prompt workflow can make record-reconciliation evidence safer to review than a one-call answer. The system preserves source lineage, asks separate model operations to build and challenge a hypothesis, retains rival candidates, and applies deterministic release rules around every probabilistic output.

It does **not** claim that a prompt proves identity. It does not autonomously merge records, declare someone found, or replace authorized humanitarian review.

The ML prompt-engineering contribution is the workflow boundary:

1. constrain each model operation to one reviewable purpose;
2. require schema-constrained output rather than prose;
3. bind extracted claims to exact source spans;
4. keep supportive and adversarial reasoning separate;
5. prevent a model operation from upgrading a deterministic block; and
6. evaluate prompt iterations on extraction precision, recall, false-positive fields, downstream safety states, and reproducibility—not completion rate alone.

## 2. End-to-end workflow

![Seven-stage THREADLINE ML workflow](reverie-ml-workflow.png)

The editable source is [`reverie-ml-workflow.svg`](reverie-ml-workflow.svg). The implementation contains twelve ordered nodes, grouped into seven judge-readable stages.

| Order | Runtime node | Type | Purpose | Input | Output | Prompt / tool | Deterministic boundary | If missing or invalid | Why it is separate |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `incident` | Human + deterministic | Establish incident scope, fictional-data declaration, limits, and review boundary. | `AnalyzeRequest` | `IncidentConfigurationOutput` | Pydantic validation | Record count, text size, and candidate limits | Reject request | Keeps authorization and scope outside model inference. |
| 2 | `quarantine` | Deterministic | Treat every narrative as untrusted text and isolate tested instruction-like patterns. | `RecordInput[]` | `QuarantinedRecord[]` | Quarantine service | Original text must remain unchanged; safe rendering is separate | Fail before provider call | Prevents record text from becoming workflow instruction. |
| 3 | `extract` | LLM | Convert narrative evidence into typed, cited fields. | `QuarantinedRecord[]` | `ExtractionModelOutput[]` | `extraction/v2` | Schema, canonical-key allowlist, exact quote/offset validation | Unsupported field is withheld; one bounded repair attempt | Separates probabilistic reading from evidentiary admissibility. |
| 4 | `normalize` | LLM + deterministic helpers | Add multilingual and canonical comparison views without replacing originals. | Validated extractions | `NormalizationModelOutput[]` | `normalization/v1` + Unicode/name helpers | Original form and evidence links must survive | Reject representation that loses lineage | Keeps representation distinct from identity conclusion. |
| 5 | `timeline` | Deterministic | Reconstruct order while preserving exact versus estimated status. | Normalized evidence | `TimelineEvent[]` | Timestamp and chronology rules | Approximation cannot become fact | Withhold coherent timeline if it requires invention | Makes time/location contradictions inspectable. |
| 6 | `retrieve` | Retrieval + deterministic | Generate bounded candidates and compare fields. | Normalized records | `CandidateConnection[]` | Blocking, top-k retrieval, pairwise comparison, scoring | Missing ≠ agreement; score ≠ probability; hard conflicts block | `insufficient_evidence` when discriminating evidence is absent | Separates search recall from release policy. |
| 7 | `hypothesis` | LLM | Summarize the strongest admissible support for one candidate. | Candidate evidence | `HypothesisModelOutput` | `hypothesis/v1` | Every factor must cite a valid source span; blocked states cannot upgrade | Remove unsupported support | Prevents the affirmative case from absorbing opposition. |
| 8 | `prosecutor` | LLM | Independently search for contradiction and missing support. | Candidate evidence | `ProsecutorModelOutput` | `prosecutor/v1` | Deterministic blockers are restored if omitted; absence is not conflict | Unresolved material conflict continues to the gate | Makes disconfirming review an explicit prompt operation. |
| 9 | `rivals` | Retrieval | Test whether evidence distinguishes the leader from nearby alternatives. | Candidate set | `RivalComparison[]` | Deterministic rival comparison | Close rivals remain visible; shared contacts are not independent proof | Close rival can force insufficiency/review | A leading candidate is unsafe without alternatives. |
| 10 | `adjudicate` | LLM + deterministic guard | Aggregate structured support, opposition, and rivals. | `AdjudicationPacket` | `AdjudicationModelOutput[]` | `adjudication/v1` | Transition allowlist permits preserve or downgrade only | Retain safer deterministic state | Allows concise review context without surrendering policy control. |
| 11 | `privacy` | Deterministic | Minimize the reviewer-facing packet while retaining audit evidence. | Candidate review packet | `PrivacySafePacket` | Pattern redaction | Restricted configured fields cannot remain in `safe_text` | Fail packet | Makes reviewer minimization explicit and testable. |
| 12 | `review` | Human routing | Prepare an authorized-review packet and permitted actions. | Privacy-safe packet | `HumanReviewRoute` | Deterministic router + human disposition | No autonomous identity-confirmation action | Packet invalid if it bypasses review | Separates software preparation from accountable human action. |

After node 12, an 18-rule deterministic **evidence contract** evaluates source integrity, lineage, certainty preservation, hard-conflict inclusion, rival coverage, safety language, audit integrity, and release authorization. Any blocking outcome clears the externally releasable classification and marks the packet **Withheld**.

## 3. The five model operations

The runtime selects provider and model using `LLM_PROVIDER` and `LLM_MODEL`; that identity is recorded in run metadata. Offline Judge Mode uses a deterministic mock provider and is labelled **not model performance**. The archived live Prompt V2 artifact evaluates extraction with an OpenAI-compatible provider and `Qwen/Qwen3-30B-A3B-Instruct-2507` at temperature `0`; it does not prove that all five nodes ran live under that model.

| # | Model operation | Prompt and SHA-256 | Query purpose | Expected structured output | Validation boundary | Evaluation signal |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | Structured extraction | `extraction/v2` · `92302c609100a882463cb950dd315f0185541082d030e7db622e570ce04b2624` | Extract every explicitly supported identity-relevant field while preserving raw script, partial precision, and exact spans. | `ExtractionModelOutput[]` | Pydantic, canonical keys, quote equality, half-open offsets, certainty enum | TP/FP/FN, micro precision/recall/F1, extraction success, per-field error analysis |
| 2 | Multilingual normalization | `normalization/v1` · `7b4ad0c542bb02470161ef262e7661f248b33a19881b50f9adca20a540a91c4e` | Propose comparison forms while keeping source-language values authoritative. | `NormalizationModelOutput[]` | Original form and evidence links preserved; deterministic canonicalizers retained | Cross-script retrieval and candidate behavior; lineage validity |
| 3 | Evidence hypothesis | `hypothesis/v1` · `25c04d5abd5cc97680a239d00d29c159c3ec49bed4edd0787b96313eb5df234b` | State only the strongest source-backed support for a candidate pair. | `HypothesisModelOutput` | Every factor cites an admissible span; unsupported support removed | Exact-citation validity; unsupported factor count; downstream state cannot upgrade |
| 4 | Contradiction challenge | `prosecutor/v1` · `a9091ce340e13e7028a150c682e60dd45e4ae6d67d3ba1d0e2dc32e5bcf5b2f7` | Search separately for conflicting fields, timeline impossibility, and insufficient independence. | `ProsecutorModelOutput` | Deterministic blockers restored; hard/soft conflict types retained | Blocking-conflict recall; contradiction recall; unsupported opposition |
| 5 | Independent adjudication | `adjudication/v1` · `a88a3e2ae0b6b1bcaf81e58176d42b26995a1d625a34d39dfee3ee95b888048c` | Produce concise review context from isolated support, opposition, and rival packets. | `AdjudicationModelOutput[]` | Explicit transition allowlist: preserve or downgrade, never upgrade blocked/insufficient | Invalid transition count; disposition consistency; contract invalid-release rate |

These outputs are structured decision rationales, not private chain-of-thought.

## 4. Prompt iteration and promotion policy

Prompt versions are promoted by measured evidence, not recency.

- **V1** established exact-span extraction and canonical keys.
- **V2 / PRODUCTION** expanded completeness, multilingual preservation, OCR tolerance, distinguishing-mark handling, partial-value preservation, and a final extraction checklist.
- **V3 / NOT PROMOTED** added stricter subject-attachment and field-specific precision instructions. On the full 58-record archive it completed 58/58 extractions and improved recall, but emitted substantially more false-positive fields, reducing precision and F1. Completion alone was not accepted as progress.

The apples-to-apples comparisons are intentionally separated:

| Shared cohort | Prompt | Success | TP / FP / FN | Precision | Recall | F1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Targeted 19 records | V1 | 19/19 | 56 / 4 / 9 | 0.9333 | 0.8615 | 0.8960 |
| Targeted 19 records | V2 | 19/19 | 58 / 2 / 7 | 0.9667 | 0.8923 | 0.9280 |
| Full 58 records | V2 | 57/58 | 157 / 30 / 25 | 0.8396 | 0.8626 | 0.8509 |
| Full 58 records | V3 | 58/58 | 161 / 78 / 21 | 0.6736 | 0.8846 | 0.7648 |

On the full cohort, V3 added 4 true-positive fields and recovered 4 previously missed fields, but also added 48 false-positive fields relative to V2. Production remains V2 because the precision regression is unsafe for an evidence workflow.

## 5. Evaluation design

THREADLINE keeps two evidence tracks separate.

### Track A — deterministic same-input workflow replay

- 21 fixed synthetic cases: 12 same-identity, 8 different-identity, 1 deliberately ambiguous;
- fixed seed `41027`;
- exact/fuzzy, generic one-prompt, structured one-call, and full workflow systems;
- identical record packets per compared system; and
- deterministic mock outputs labelled **not model performance**.

This track demonstrates workflow behavior and reproducibility. It does not measure live LLM quality.

### Track B — archived live-provider extraction

- 58 synthetic records;
- OpenAI-compatible provider;
- model `Qwen/Qwen3-30B-A3B-Instruct-2507`;
- temperature `0`;
- fixture SHA-256 `eed1032519f78ebfd18a49da55c920c1b280ade1b7e32ebda514157ff1ead850`;
- versioned prompt and raw-output artifacts; and
- deterministic downstream retrieval and policy evaluation.

This is one archived run per full prompt version, not a repeated-trial confidence study and not a same-model one-shot versus workflow experiment.

### Track C — measured live same-model one-shot versus workflow comparison (frozen v1.1, completed)

A same-model comparison was preregistered before any provider output was observed as spec `THREADLINE-REVERIE-LIVE-EVAL-V1.1` (SHA-256 `458279a9595b79e3785af7004cf68a93223fde21e0934b4c432525bebdc786a1`). The draft v1 spec (`dccfb171…1c99`) is preserved as superseded-before-observation. Design: 3 synthetic cases × 3 repetitions × 2 systems = 18 top-level runs; both systems receive identical records, incident context, provider (`openai_compatible`), model (`Qwen/Qwen3-30B-A3B-Instruct-2507`), and temperature `0`. Every provider request, response, retry, and error is recorded in a sanitized, resume-safe checkpoint. The run completed **18 / 18** top-level runs with **0** final failures; three recorded schema-validation failures were retried to success under the symmetric policy and remain visible in the recorder.

| System | Schema-valid | Outcomes within accepted set | Invalid citations | Supported / unsupported fields | Provider calls | Transport attempts | Tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Structured one-shot | 9 / 9 | 9 / 9 | 45 | 9 / 45 | 9 | 18 | 20,108 |
| Full THREADLINE workflow | 9 / 9 | 3 / 9 | 0 | 3 / 0 | 82 | 142 | 150,875 |

Measured behavior is mixed and is reported without spin:

- The one-shot returned an acceptable classification in all 9 runs, but 45 of its 54 emitted claim spans were inexact (exact-citation validity 9/54), including 7 invalid citations in every cross-script run.
- THREADLINE emitted zero invalid citations and zero unsupported fields, but returned `insufficient_evidence` in all 9 runs — including all 3 cross-script runs where the frozen ground truth accepts only positive or human-review outcomes, and all 3 blocking-conflict runs where the expected state is `blocked_by_conflict`. On these live runs it under-detected the DOB conflict rather than surfacing it.
- This is a small synthetic experiment (3 cases × 3 repetitions). It establishes no statistical significance, no system superiority, and no operational validity.

Authoritative artifacts: `backend/data/reverie_live_evaluation_v1_1/results.json`, the sanitized recorder `raw-provider-calls.json`, the byte-identical submission copy `docs/submission/reverie-live-evaluation-results.json`, and the publication manifest `docs/submission/reverie-live-evaluation-manifest.json`.

## 6. Representative safety case

The judge case uses the exact same three-record packet for each deterministic comparison system:

- `FAMILY-018` — family report, age 14;
- `SHELTER-204` — shelter intake, age 14; and
- `HOSPITAL-052` — plausible rival, documented age 24 from an identity card.

Input SHA-256: `bc8084e71ab87554163279a3b61d27d1b71f0c06fb3347c4555de5670ab83576`  
Complete available-evidence SHA-256: `68c34760bc4c0f0f6e18f0aeb40d1ddf5243656efcc75b7034dbe0d73223ff20`

The generic one-prompt replay returns `FAMILY-018 ↔ SHELTER-204` as a possible candidate with no citations, contradiction, or rival comparison. THREADLINE preserves that pair as a possible connection for authorized review while blocking candidate pairs involving `HOSPITAL-052` under `TIMELINE_CONSISTENCY` and `MATERIAL_CONTRADICTIONS_RESOLVED`, with exact age spans attached. This is not an identity confirmation.

## 7. Audit and reproducibility

Run artifacts preserve, where available:

- case and record IDs;
- exact source text and source-span coordinates;
- prompt/template ID, version, and content hash;
- provider, model, temperature, run timestamp, and run ID;
- fixture and identity-assignment hashes;
- raw model outputs, validation failures, retries, and repair attempts;
- deterministic comparison and evidence-contract outcomes; and
- audit, replay, and counterfactual records.

Authoritative sources:

- [`submission/results.json`](submission/results.json)
- [`submission/results.csv`](submission/results.csv)
- [`submission/raw-outputs.json`](submission/raw-outputs.json)
- [`submission/ablation-counterfactual.json`](submission/ablation-counterfactual.json)
- [`../backend/data/live_runs_phase11/full-prompt-v2-run-1/live-artifact.json`](../backend/data/live_runs_phase11/full-prompt-v2-run-1/live-artifact.json)
- [`../backend/data/live_runs_phase13/full-prompt-v3-run-1/live-artifact.json`](../backend/data/live_runs_phase13/full-prompt-v3-run-1/live-artifact.json)

## 8. Prior work and scope

THREADLINE does not claim to have invented digital missing-person matching. The ICRC [Missing Persons Digital Matching project](https://www.icrc.org/sites/default/files/media_file/2024-12/MPDM_tool_A4_1%20pager.pdf) already describes multilingual comparison and human analysis of candidate results. THREADLINE's narrower experimental contribution is exact claim-to-source lineage, adversarial contradiction analysis, retained rivals, prompt-injection containment, deterministic release rules around probabilistic stages, replay/counterfactual evaluation, and safety-weighted synthetic benchmarking.

The design is informed by the ICRC [Handbook on Data Protection in Humanitarian Action](https://www.icrc.org/en/data-protection-humanitarian-action-handbook) and the [revised OCHA Data Responsibility Guidelines](https://centre.humdata.org/revised-ocha-data-responsibility-guidelines/). THREADLINE is not endorsed by either organization and has not been validated for operational humanitarian use.

## 9. Known limitations

- All records and identities are fictional and synthetic.
- The deterministic baseline comparison is not live-model evidence.
- The live archives contain one full run per V2/V3 version and no repeated-run confidence intervals.
- The frozen live same-model comparison (3 cases × 3 repetitions) completed 18/18, but its outcomes are mixed: the one-shot was outcome-acceptable in 9/9 runs with 45 invalid citations, while THREADLINE was citation-exact (0 invalid) but abstained in all 9 runs and under-detected the blocking DOB conflict. No superiority claim is made from this small synthetic experiment.
- Zero observed false merges uses only eight evaluated different-identity opportunities in the archived V2 run; it is not a field-safety guarantee.
- Selected workflow-node ablations produced no primary-metric or case-level change on the small fixed harness; that no-effect result is retained.
- Authentication, role enforcement, encryption at rest, automated retention/deletion, connected-provider exact replay, field validation, fairness evaluation, and external security review remain production requirements.

