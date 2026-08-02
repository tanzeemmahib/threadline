# Evaluation interface

The implemented backend runs four systems on identical cases: deterministic exact/fuzzy matching, a realistic generic single-prompt LLM, a schema/evidence-constrained single-call LLM, and the full staged THREADLINE workflow. Default tests and mock evaluation make no external calls.

## Result semantics

Every system result stores the actual candidate IDs, allowed classification, cited spans, structured output, measured duration, actual model-call count, failures, and retries. The frontend labels mock results `Deterministic mock evaluation — not real model performance` and connected results `Measured provider evaluation`.

Metrics are calculated from case outputs and separate ground truth, not copied from frontend illustrative values. Each metric includes value, numerator, denominator, and formula. Required metrics are candidate recall at K, false-link rate, correct abstention rate, evidence faithfulness, prompt-injection resistance, multilingual robustness, and classification accuracy. Operational metrics track measured duration, model calls, failures, and retries.

## Error analysis

Case errors use snake-case categories: `missed_true_candidate`, `incorrect_candidate_link`, `failed_abstention`, `unsupported_evidence`, `timeline_reasoning_failure`, `transliteration_failure`, `rival_candidate_confusion`, `prompt_injection_failure`, `privacy_exposure`, and `extraction_error`.

Every error includes case/record IDs, expected and actual result, system, workflow configuration, first divergent node, evidence, severity, and suggested investigation. These correspond directly to the existing frontend error-analysis concepts.

## Ablations

Supported removals are evidence quarantine, multilingual normalization, timeline reconstruction, contradiction prosecutor, rival-candidate test, independent adjudication, and privacy gate. The runner first computes a complete-workflow reference, then reruns the identical generated dataset and seed for each selected removal (and a combined selection when several are requested). It returns enabled/disabled nodes, computed metrics, deltas from full, newly introduced/resolved errors, and affected case IDs.

The implementation never substitutes manually invented percentage changes. A safety regression may appear as a case-level error even when a general quality metric is unchanged.

## Interpretation

- Candidate classifications propose review, never identity.
- A retrieval score is a ranking signal and never a probability.
- Evidence faithfulness is based on exact quote/offset validity.
- Plausible chronology does not prove identity.
- Abstention is a valid and required result for non-distinctive rival cases.
- Frontend dashboard values remain illustrative unless replaced with backend result artifacts.

## Persistent console

The evaluation console queues multi-seed benchmark jobs, polls persisted progress, cancels active work, reloads results across restarts, and exports credential-free manifests. It renders fixed-seed bootstrap intervals, the three risk–coverage policies, and full-versus-adaptive routing measurements from stored outputs. The Dataset, Baseline, Ablation, and Error components retain explicit fixture labels until a backend artifact replaces them.
