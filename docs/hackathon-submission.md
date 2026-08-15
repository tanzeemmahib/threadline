# THREADLINE — Reverie Hacks 2026 submission brief

## Project description

THREADLINE is an experimental safety and review layer for proposed record connections. It preserves exact provenance, challenges each hypothesis with contradictions and rival candidates, and deterministically withholds outputs that are not safe for authorized human review.

The central demonstration is:

> Same records. Same deterministic mock model. Different workflow.  
> A single prompt reaches a conclusion. THREADLINE preserves the evidence, exposes the contradiction, and withholds what cannot be proven.

The deterministic mock in Judge Mode is an offline, reproducible workflow-behavior fixture. It is not a claim about live-model performance. Archived live-provider measurements are presented separately, and a live same-model single-prompt comparison has not been measured.

THREADLINE is a synthetic research demonstration. It is not a production registry, a public search engine, an identification system, a facial-recognition product, a replacement for humanitarian organizations, or evidence of real-world humanitarian validation. It never confirms identity or autonomously merges people.

## The problem

After a disaster, records about a missing person can be fragmented across family reports, shelter registers, hospitals, and field notes. Names may be transliterated differently, dates may be partial, and contacts may be copied between systems. Similarity can make a proposed connection look persuasive even when a material contradiction remains.

THREADLINE tests a narrow ML-safety question: can a prompt-engineered workflow make probabilistic extraction and reasoning more reviewable by preserving source lineage, actively looking for disconfirming evidence, considering rival candidates, and applying deterministic release rules?

## Judge path

The primary route is `/demo`. Its eight scenes are designed to complete in under four minutes:

1. **Fragmented records** — a family report and an intake record show compatible fragments without an identity conclusion.
2. **Single-prompt baseline** — a reasonable one-call fixture returns a plausible candidate for review from the same evidence.
3. **Evidence extraction** — each claim exposes its exact source span, original value, normalized value, category, independence status, and uncertainty.
4. **Contradiction challenge** — a soft date conflict and a material location/timeline conflict interrupt the proposed connection.
5. **Rival candidate** — an alternative candidate remains plausible.
6. **Evidence contract** — deterministic rules withhold release because material location evidence remains unresolved.
7. **Human review** — the case is handed to an authorized reviewer without a success treatment.
8. **Measured comparison** — the deterministic replay and archived live-provider evidence are clearly separated.

Landing-page actions use the exact labels **Run the evidence challenge** and **Explore the technical workspace**. Judge Mode supports Start, Next, Back, Reset, source opening, technical-evidence access, keyboard navigation, touch, and reduced motion.

## Technical workflow

The implementation contains twelve workflow nodes grouped into seven readable stages in the [submission workflow diagram](submission/threadline-workflow.svg):

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

One archived Prompt V2 run used an OpenAI-compatible provider with `Qwen/Qwen3-30B-A3B-Instruct-2507`, temperature 0, and the synthetic identity benchmark. It is extraction-focused and has no live same-model one-prompt comparator.

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

- [Submission package index](submission/README.md)
- [Four-minute demo script](submission/demo-script.md)
- [Workflow and node documentation](submission/workflow-node-documentation.md)
- [Reproduction instructions](submission/reproduction.md)
- [Editable workflow SVG](submission/threadline-workflow.svg)
- [Submission workflow PNG](submission/threadline-workflow.png)
- [Workflow/node documentation PDF](submission/workflow-node-documentation.pdf)
- [Comparison and samples PDF](submission/comparison-samples.pdf)

The deterministic demo requires no network connection or provider credentials and is explicitly labelled as a synthetic replay. Optional connected-provider runs require credentials and must be reported separately.

## Known limitations

- All records and cases are synthetic; there has been no operational humanitarian validation.
- The 21-case deterministic harness is too small to support broad safety or performance claims.
- The one archived live-provider run does not include a live same-model single-prompt comparator or approximate monetary cost.
- Selected workflow ablations do not change primary metrics on the current fixed harness.
- The release contract encodes research rules, not a validated humanitarian decision policy.
- The prototype lacks the privacy, security, governance, and organizational controls required for production use.
- Human-review workflow states do not establish that a reviewer has validated a person or a proposed connection.

## Submission thesis

> The baseline produced an answer.  
> THREADLINE produced an auditable boundary around what the evidence can support.

That boundary — exact evidence, visible contradiction, plausible rivals, deterministic withholding, and authorized human review — is the project’s primary result.
