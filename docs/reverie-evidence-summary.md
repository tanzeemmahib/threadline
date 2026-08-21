# THREADLINE — Reverie evidence summary

> **One connection recovered. One false merge prevented. Every decision traceable.** “Connection recovered” means a candidate record connection reconstructed for authorized review — not a person identified.

THREADLINE is a synthetic research demonstration of a source-cited prompt workflow surrounded by deterministic comparison and release policy. It has not been validated for operational humanitarian use.

## The evidence case

| Candidate records | Evidence state | Release boundary |
| --- | --- | --- |
| `FAMILY-018 ↔ SHELTER-204` | Supported possible connection | Eligible only for authorized human review; never identity confirmation |
| `FAMILY-018 ↔ HOSPITAL-052` | Document-backed age/timeline contradiction | **BLOCKED** by deterministic material-conflict rules; the model cannot override |

All three systems in the guided comparison receive the same complete three-record packet. Exact quotes and offsets remain available from the original synthetic source text.

## Prompt promotion evidence

| Shared cohort | Schema-valid | TP / FP / FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Targeted 19 · Prompt V1 | 19/19 | 56 / 4 / 9 | 0.9333 | 0.8615 | 0.8960 |
| Targeted 19 · Prompt V2 | 19/19 | 58 / 2 / 7 | 0.9667 | 0.8923 | 0.9280 |
| Full 58 · Prompt V2 · **PRODUCTION** | 57/58 | 157 / 30 / 25 | 0.8396 | 0.8626 | 0.8509 |
| Full 58 · Prompt V3 · **NOT PROMOTED** | 58/58 | 161 / 78 / 21 | 0.6736 | 0.8846 | 0.7648 |

Prompt V3 was not promoted (`PRECISION_REGRESSION`): recall increased from `0.8626` to `0.8846`, but precision fell from `0.8396` to `0.6736` and false-positive fields rose from `30` to `78` on the same 58 records. No full 58-record V1 artifact exists, so no three-way same-cohort ranking is claimed.

## Measured safety boundary

- Archived full Prompt V2: `4` link-recommended candidate pairs; `0/8` observed false merges; `10` false non-links across `14` same-identity opportunities.
- Blocking-conflict recall: `1.000`.
- Approximate API cost: **Not measured**.
- These are small synthetic denominators, not a real-world safety, fairness, or effectiveness claim.

## Measured live same-model comparison

A frozen preregistered comparison (spec `THREADLINE-REVERIE-LIVE-EVAL-V1.1`, SHA-256 `458279a9595b79e3785af7004cf68a93223fde21e0934b4c432525bebdc786a1`) ran before any provider output was observed: 3 synthetic cases × 3 repetitions × 2 systems = 18 top-level runs; both systems receive identical records, incident context, provider (`openai_compatible`), model (`Qwen/Qwen3-30B-A3B-Instruct-2507`), and temperature `0`. All 18 runs completed with 0 final failures; every request, response, retry, and error is recorded in a sanitized checkpoint under `backend/data/reverie_live_evaluation_v1_1/`.

| System (9 runs each) | Schema-valid | Outcome-acceptable | Supported fields | Unsupported fields | Invalid citations | Exact-citation validity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| THREADLINE workflow | 9 / 9 | 3 / 9 | 3 | 0 | 0 | n/a (0 exact citations claimed) |
| Structured one-shot | 9 / 9 | 9 / 9 | 9 | 45 | 45 | n/a |

The one-shot returned an acceptable classification in all 9 runs, but 45 of its 54 emitted claim spans were inexact (7 invalid citations in every cross-script run). THREADLINE never emitted an unsupported or inexact field across all 9 runs, but abstained (`insufficient_evidence`) in 6 of 9 runs and under-detected the blocking DOB conflict that the deterministic harness blocks. Results are mixed; no superiority claim is made from three synthetic cases. This is measured live-provider evidence, distinct from the deterministic mock replay and the archived Prompt V2/V3 extraction runs.

- Live-evaluation results SHA-256: `00ead5b5f303a57805a8f997e5bb682d504114772733686efc3ddf5ffcaffa5d`

## Audit path

- Guided case: `/demo?demo=guided`
- Prompt Lab: `/prompt-lab`
- Offline release command: `.\scripts\reverie-release.ps1` or `bash scripts/reverie-release.sh`
- Prompt Lab SHA-256: `9d6aab126a610927b6aa24bb7c95ed8af03b52b85669a5adf79787e184fbcc83`
- Case: `THREADLINE-WINNING-STORY-V1`; fictional synthetic records only
