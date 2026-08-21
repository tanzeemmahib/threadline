# THREADLINE — Reverie Hacks 2026 submission brief

> **Primary 2026 judge path:** use the current [three-minute demo script](reverie-demo-script.md), [Prompt Lab comparison](reverie-prompt-comparison.md), and [ML-track documentation](reverie-ml-track-documentation.md). Older workspace-tour materials are retained only as legacy technical references.

## Project description

THREADLINE is an experimental safety and review layer for proposed record connections. It preserves exact provenance, challenges each hypothesis with contradictions and rival candidates, and deterministically withholds outputs that are not safe for authorized human review.

The central demonstration is:

> Same records. Same deterministic mock model. Different workflow.  
> A single prompt reaches a conclusion. THREADLINE preserves the evidence, exposes the contradiction, and withholds what cannot be proven.

The deterministic mock in Judge Mode is an offline, reproducible workflow-behavior fixture. It is not a claim about live-model performance. Archived live-provider measurements are presented separately, and a frozen same-model live comparison (18/18 runs completed) is presented separately with mixed outcomes and no superiority claim.

THREADLINE is a synthetic research demonstration. It is not a production registry, a public search engine, an identification system, a facial-recognition product, a replacement for humanitarian organizations, or evidence of real-world humanitarian validation. It never confirms identity or autonomously merges people.

## The problem

After a disaster, records about a missing person can be fragmented across family reports, shelter registers, hospitals, and field notes. Names may be transliterated differently, dates may be partial, and contacts may be copied between systems. Similarity can make a proposed connection look persuasive even when a material contradiction remains.

THREADLINE tests a narrow ML-safety question: can a prompt-engineered workflow make probabilistic extraction and reasoning more reviewable by preserving source lineage, actively looking for disconfirming evidence, considering rival candidates, and applying deterministic release rules?

## Judge path

The primary route is `/demo?demo=guided`. Its six scenes are designed to complete in under three minutes with narration:

1. **Human stakes** — three synthetic record summaries establish `FAMILY-018`, `SHELTER-204`, and the plausible `HOSPITAL-052` rival without an identity conclusion.
2. **One-shot baseline** — a reasonable deterministic one-call replay receives the same complete packet and returns a plausible candidate without exact citations or explicit rival contradiction.
3. **Source-cited extraction** — structured factors link to exact quoted spans, offsets, and substring validation while deterministic representations remain separate from original evidence.
4. **Supported thread** — `FAMILY-018 ↔ SHELTER-204` becomes a possible connection eligible only for authorized human review.
5. **Conflict gate** — direct age evidence and deterministic timeline/material-conflict rules block candidate pairs involving `HOSPITAL-052`; the model cannot override the gate.
6. **Measured proof** — the supported and blocked outcomes remain beside input/evidence hashes, contract identifiers, archived Prompt V2 counts, and explicit synthetic limits.

The landing-page actions are **Run the evidence case** and **Compare the prompts**. Judge Mode supports direct scene selection, Next, Back, Reset, exact-source opening, keyboard navigation, touch, and reduced motion. `/prompt-lab` is the technical deep dive. The older persisted workspace tour remains available only as a legacy technical reference.

## Technical workflow

The implementation is summarized as seven readable stages in the current [Reverie workflow diagram](reverie-ml-workflow.svg):

1. Human incident configuration and record intake
2. Untrusted-text quarantine and LLM extraction
3. LLM normalization plus deterministic timeline checks
4. Deterministic candidate retrieval
5. LLM hypothesis construction, contradiction challenge, and rival-candidate analysis
6. LLM adjudication, deterministic review-packet construction, and the evidence contract
7. Withholding or authorized human-review handoff, with audit and replay artifacts

Five stages call an LLM when a connected provider is configured: extraction, normalization, hypothesis construction, contradiction challenge, and adjudication. Retrieval, evidence validation, timeline rules, contract evaluation, audit chaining, and disposition routing are deterministic. The current privacy node is late in the pipeline and protects the reviewer-facing packet; it is not a pre-provider privacy gateway.

Each material claim retains:

- the source record identifier;
- the exact quoted source span and span coordinates;
- the original value;
- a separately stored normalized value;
- its evidence category and independence status;
- extraction uncertainty and validation outcomes.

The evidence contract can release only a **possible connection proposal** for authorized review. It cannot confirm identity. A material unresolved conflict causes a **withheld** disposition and **human review required** state.

## What is novel — and what is not

Digital missing-person matching predates THREADLINE. The [ICRC Missing Persons Digital Matching project](https://www.icrc.org/sites/default/files/media_file/2024-12/MPDM_tool_A4_1%20pager.pdf) describes work to support comparison of missing-person and unidentified-person data. THREADLINE does not claim to have invented that field.

Its narrower experimental contribution is the combination of:

- exact claim-to-source lineage;
- adversarial contradiction analysis;
- explicit rival hypotheses;
- containment of untrusted record text before prompt construction;
- deterministic release rules around probabilistic model stages;
- replay and source-removal counterfactual evaluation;
- safety-weighted benchmarking centered on false merges rather than a single accuracy score.

The project treats the [ICRC Handbook on Data Protection in Humanitarian Action](https://www.icrc.org/en/data-protection-humanitarian-action-handbook) and [OCHA Data Responsibility Guidelines](https://centre.humdata.org/revised-ocha-data-responsibility-guidelines/) as relevant operational references, not as endorsements or evidence that this prototype is deployment-ready.

## Evaluation evidence

THREADLINE keeps two evidence tracks separate.

### Deterministic same-case workflow replay

The fixed 21-case synthetic harness compares exact/fuzzy matching, a generic single-prompt fixture, a structured single-call fixture, and the full THREADLINE workflow. All systems receive the same record evidence. This track measures deterministic workflow behavior, **not model quality**.

| System | Candidate recall | False-link rate on different-identity cases | Correct abstention |
| --- | ---: | ---: | ---: |
| Exact/fuzzy matching | 4/12 (33.333%) | 2/8 (25.000%) | 0/1 (0.000%) |
| Generic single-prompt fixture | 12/12 (100.000%) | 8/8 (100.000%) | 0/1 (0.000%) |
| Structured single-call fixture | 12/12 (100.000%) | 8/8 (100.000%) | 0/1 (0.000%) |
| Full THREADLINE workflow | 4/12 (33.333%) | 0/8 (0.000%) | 1/1 (100.000%) |

These counts show the behavior encoded by the fixed fixtures and rules. They do not estimate real-world performance, and zero observed false links across eight negative cases is not a safety guarantee.

### Archived live-provider extraction evidence

One archived Prompt V2 run used an OpenAI-compatible provider with `Qwen/Qwen3-30B-A3B-Instruct-2507`, temperature 0, and the synthetic identity benchmark. It is extraction-focused and has no live same-model one-prompt comparator. A separate frozen preregistered same-model comparison (spec `THREADLINE-REVERIE-LIVE-EVAL-V1.1`) did run both systems live on identical inputs; see `docs/reverie-ml-track-documentation.md` and the published artifact under `backend/data/reverie_live_evaluation_v1_1/`.

| Measure | Archived result |
| --- | ---: |
| Successful extractions | 57/58 |
| Extraction TP / FP / FN | 157 / 30 / 25 |
| Extraction precision / recall / F1 | 0.8396 / 0.8626 / 0.8509 |
| Candidate retrieval | 14/14 |
| Released possible connections | 4 |
| Different-identity false merges | 0/8 evaluated opportunities |
| False non-links | 10 |
| Conflict-blocked cases | 6 |
| Median latency, successful calls | 49,714 ms |
| p95 latency, successful calls | 82,819 ms, nearest-rank |
| Successful-call tokens / total attempts | 236,788 / 128 |
| Approximate API cost | Not measured |

The run artifact records fixture and prompt hashes, provider and model identifiers, temperature, timestamps, raw outputs, and evaluation results. It did not record an exact git commit or clean/dirty tree state; the current commit must not be retroactively assigned to that archived run.

## Ablation and counterfactual evidence

The selected deterministic ablations are retained even when they produce no primary-metric or case-level change. This is an honest limitation of the small fixed harness, not evidence that the nodes are unnecessary.

The implemented source-removal counterfactual removes `HOSPITAL-052` from the representative case. Aggregate contract status changes from **withheld** to **released** because the removed age contradiction no longer blocks the contract. That change only shows what the current deterministic rules permit; it does not prove that the remaining records describe the same person.

An independently disableable evidence-contract node has not been measured. Accordingly, “THREADLINE without the deterministic evidence contract” is reported as **Not measured**, not estimated.

Machine-readable counts and raw case outputs are in:

- [results.json](submission/results.json)
- [results.csv](submission/results.csv)
- [raw-outputs.json](submission/raw-outputs.json)
- [ablation-counterfactual.json](submission/ablation-counterfactual.json)
- [benchmark report](submission/benchmark-report.md)

## Safety and data responsibility

Only fictional synthetic identities are included. Exact source text is preserved and normalized values never overwrite it. Prompt instructions explicitly treat record text as untrusted data, and structured outputs are validated before later stages use them.

The connected-provider path may send record text or derived structured evidence to the configured provider in five LLM stages. The local SQLite database and export directories persist data until manually removed. The prototype does not implement authentication, role-based access control, encryption at rest, automated retention/deletion, a provider-side deletion guarantee, or field-level export redaction. These are named production requirements, not implied controls.

See [Data responsibility and threat model](submission/data-responsibility.md) for the exact implemented boundary and residual risks.

## Reproduction and artifacts

- [Reverie submission checklist](reverie-submission-checklist.md)
- [Three-minute Reverie demo script](reverie-demo-script.md)
- [Prompt comparison](reverie-prompt-comparison.md)
- [ML-track workflow and node documentation](reverie-ml-track-documentation.md)
- [Editable Reverie workflow SVG](reverie-ml-workflow.svg)
- [Reverie workflow PNG](reverie-ml-workflow.png)
- [Machine-readable Prompt Lab evidence](submission/reverie-prompt-lab.json)
- [Reproduction instructions](submission/reproduction.md)
- [Legacy technical workspace package](submission/README.md)

The deterministic demo requires no network connection or provider credentials and is explicitly labelled as a synthetic replay. Optional connected-provider runs require credentials and must be reported separately.

## Known limitations

- All records and cases are synthetic; there has been no operational humanitarian validation.
- The 21-case deterministic harness is too small to support broad safety or performance claims.
- The frozen live same-model comparison completed 18/18 runs but is small and mixed: the structured one-shot was outcome-acceptable in 9/9 runs while emitting 45 invalid citations, and THREADLINE emitted 0 invalid citations while abstaining on 6/9 runs. No superiority claim is made from three synthetic cases; approximate monetary cost and confidence intervals remain not measured.
- Selected workflow ablations do not change primary metrics on the current fixed harness.
- The release contract encodes research rules, not a validated humanitarian decision policy.
- The prototype lacks the privacy, security, governance, and organizational controls required for production use.
- Human-review workflow states do not establish that a reviewer has validated a person or a proposed connection.

## Submission thesis

> The baseline produced an answer.  
> THREADLINE produced an auditable boundary around what the evidence can support.

That boundary — exact evidence, visible contradiction, plausible rivals, deterministic withholding, and authorized human review — is the project’s primary result.
