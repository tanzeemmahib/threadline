# THREADLINE submission benchmark report

## Answer first

On the fixed deterministic 21-case harness, the generic and structured one-call fixtures returned a positive review candidate in all 8 different-identity cases; the full THREADLINE workflow returned none and abstained on the one deliberately ambiguous case. This is a workflow-behavior replay, **not model performance**.

## Deterministic same-case comparison

Evaluation label: **Deterministic mock replay - not model performance.**

| System | Candidate recall | False-link rate | Correct abstention |
| --- | ---: | ---: | ---: |
| Exact/fuzzy matching | 33.333% (4/12) | 25.000% (2/8) | 0.000% (0/1) |
| Generic single-prompt baseline | 100.000% (12/12) | 100.000% (8/8) | 0.000% (0/1) |
| Structured single-call baseline | 100.000% (12/12) | 100.000% (8/8) | 0.000% (0/1) |
| Full THREADLINE workflow | 33.333% (4/12) | 0.000% (0/8) | 100.000% (1/1) |

## Archived live-provider evidence (separate track)

Evaluation label: **Archived measured live-provider extraction run (one run).**

- Synthetic records: 58
- Successful extractions: 57/58
- Extraction TP / FP / FN: 157 / 30 / 25
- Extraction precision / recall / F1: 0.8396 / 0.8626 / 0.8509
- Candidate retrieval: 14/14
- True links / false merges / false non-links: 4 / 0 / 10
- Median / p95 extraction latency: 49714 ms / 82819 ms
- Approximate API cost: Not measured

## Ablation and counterfactual

- `full`: Reference configuration; no nodes disabled.
- `no-prosecutor`: No primary quality/safety metric or case-level change; affected cases: 0. Operational harness delta: model_calls -23.
- `no-rivals`: No primary quality/safety metric or case-level change; affected cases: 0.
- `no-adjudication`: No primary quality/safety metric or case-level change; affected cases: 0. Operational harness delta: model_calls -46.
- `selected-combined`: No primary quality/safety metric or case-level change; affected cases: 0. Operational harness delta: model_calls -69.

Removing `HOSPITAL-052` changed aggregate contract status from `withheld` to `released`. The removed contradiction was age evidence. This changes what the contract permits; it does not prove identity.

Evidence-contract-node removal is **Not measured** because the contract is not an independently disableable benchmark node in the current implementation.

## Limitations

- Deterministic mock outputs are fixtures used to exercise workflow paths; they are not LLM quality measurements.
- The archived Prompt V2 evidence is one live extraction run and has no live same-model single-prompt comparator.
- The 21-case harness is synthetic and small; zero observed false links is not a real-world safety guarantee.
- The selected benchmark ablations produced no primary-metric or case-level change. That no-effect result is retained rather than hidden.
- THREADLINE proposes possible record connections for authorized review and never confirms identity.

## Reproduction

From `backend`:

```powershell
.\.venv\Scripts\python.exe scripts\build_submission_evidence.py
```
