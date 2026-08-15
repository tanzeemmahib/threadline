# THREADLINE — FINAL RELEASE REPORT

Release date: 2026-08-15
Scope: synthetic identities only. THREADLINE is an experimental safety and review layer for proposed record connections; it never autonomously confirms identity.

## 1. Release verdict

**SHIP READY WITH DOCUMENTED LIMITATIONS**

The release passes the full runtime verification matrix (backend tests, deterministic validator, frontend behavior/typecheck/lint/build, end-to-end demo, benchmark-integrity audit, and an eight-scene Judge Mode cold-start rehearsal). It ships with named limitations: known static-analysis debt, synthetic-only evaluation, single-run archived live-provider evidence, and small negative-case denominators. No safety control was weakened to reach this verdict.

## 2. Verification table

| Suite | Command (working directory) | Result | Count |
| --- | --- | --- | --- |
| Backend unit/contract/safety/integration | `./.venv/Scripts/python.exe -m pytest` (`backend`) | PASS | 454 passed, 0 failed, 1 warning |
| Deterministic 10-gate validator | `./.venv/Scripts/python.exe _phase10s_validate.py` (`backend`) | PASS | 10 / 10 gates |
| Phase 11 extraction contract | `pytest tests/test_phase11_extraction_contract.py` (`backend`) | PASS | 28 passed |
| Submission evidence contract | `pytest tests/test_submission_evidence.py` (`backend`) | PASS | 3 passed (includes `risk_bound.target_status == "not_met"`) |
| Ruff (static analysis) | `./.venv/Scripts/python.exe -m ruff check app tests scripts` (`backend`) | KNOWN DEBT | 184 errors (149 auto-fixable) |
| mypy (static analysis) | `./.venv/Scripts/python.exe -m mypy app` (`backend`) | KNOWN DEBT | 139 errors / 16 files |
| Frontend behavior tests | `npm test` (`frontend`) | PASS | 35 passed, 0 failed |
| Frontend typecheck | `npm run typecheck` (`frontend`) | PASS | — |
| Frontend ESLint (full) | `npm run lint` (`frontend`) | PASS | 0 errors |
| Frontend production build | `npm run build` (`frontend`) | PASS | Next.js 16.3.0; `/`, `/benchmark`, `/demo`, `/methodology`, `/trials`, `/workspace` prerendered; `/workspace/packet` server-rendered |
| End-to-end demo + integration smoke | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./scripts/run-v1-demo.ps1` (repo root) | PASS | passing `released`, blocked `withheld`, review `insufficient_evidence`, replay `exact_match`, counterfactual `changed=True`, audit chain `verified`, tamper smoke detected the injected break |

The Ruff and mypy results are reported as the project already describes them: known repository-wide debt, not green, and not represented as passing. The two static-analysis commands are intentionally excluded from the green set.

## 3. Judge Mode cold-start path (verified)

A fresh, cold local state was exercised end-to-end: `run-v1-demo.ps1` built the production frontend, started the mock backend and frontend, created three persisted cases, and verified their contract states, audit integrity, deterministic replay, and source-removal counterfactual. The guided case at `/demo?demo=guided` was then stepped through all eight scenes in the in-app browser:

1. **Fragmented records** — six records, two candidate threads, one awaiting review, no identity conclusion.
2. **Single-prompt baseline** — shows a possible-candidate answer with `0` citations and `0` contradictions, labelled "Deterministic mock replay — not model performance", with an "exact prompt and shared six-record input manifest" disclosure.
3. **Evidence extraction** — reverse provenance travels candidate claim → normalized claim → extracted evidence → exact source span.
4. **Contradiction challenge** — soft birth-date conflict vs. material location contradiction, with per-span offsets and certainty.
5. **Rival candidate** — leading thread vs. credible rival (AID-209) retained with supporting and conflicting evidence.
6. **Evidence contract** — 10 versioned rules; `MATERIAL_CONTRADICTIONS_RESOLVED` BLOCK, `TIMELINE_CONSISTENCY` WARN, rest PASS; output withheld.
7. **Human review** — authorized handoff, release state withheld, autonomous merge not permitted.
8. **Measured comparison** — deterministic 21-case replay vs. the single-prompt fixture, the V1 holdout raw count, and the archived live run kept in separate, labelled evidence tracks.

No console errors were observed. The persisted API-backed workspace (`/workspace?run=…`) also loaded with a relationship graph, map, timeline, and source-span buttons.

Viewport note: the desktop and 390 px+ layouts verified previously show no page-level horizontal overflow; at a 318 px preview pane (below the 320 px design floor) a ~9 px overflow was observed. This is recorded as a minor presentation limitation, not a judge-path blocker.

## 4. Benchmark claims (every headline number, denominator, and artifact)

### Track A — deterministic mock replay (NOT model performance)

| Claim | Value | Denominator | Artifact |
| --- | ---: | --- | --- |
| THREADLINE positive-case candidate recall | 4 / 12 (33.333%) | 12 same-identity cases | `docs/submission/results.json` → `deterministic_benchmark.systems[threadline].metrics.candidate_recall_at_k` |
| THREADLINE false-link rate | 0 / 8 | 8 different-identity cases | same, `false_link_rate` |
| THREADLINE correct abstention | 1 / 1 | 1 ambiguous case | same, `correct_abstention_rate` |
| Generic single-prompt recall / false-link / abstain | 12/12, 8/8, 0/1 | same denominators | same, `systems[generic]` |
| Structured single-call recall / false-link / abstain | 12/12, 8/8, 0/1 | same denominators | same, `systems[structured]` |
| Exact/fuzzy recall / false-link / abstain | 4/12, 2/8, 0/1 | same denominators | same, `systems[fuzzy]` |
| Valid cited quote/offset spans (THREADLINE) | 179 / 179 | all cited evidence spans | `docs/submission/raw-outputs.json` |

Verified independently this pass: the 21 stored `input_sha256` values re-hash correctly under the canonical serialization (21/21), the 43 record-level `text_sha256_by_record` values match (43/43), and `judge_case_comparison.same_input_verification.exact_input_shared` is `true` with identical `input_sha256`, `available_evidence_sha256`, and `record_ids` across the generic/structured/threadline systems. The benchmark-report table matches `results.json` exactly.

### Track B — archived live-provider extraction (one run, separate track)

| Claim | Value | Denominator | Artifact |
| --- | ---: | --- | --- |
| Extraction success | 57 / 58 | 58 synthetic records | `docs/submission/results.json` → `archived_live_prompt_v2` |
| Micro extraction precision / recall / F1 | 0.8396 / 0.8626 / 0.8509 | 157 TP / 30 FP / 25 FN | same |
| Candidate retrieval | 14 / 14 | 14 same-identity universe pairs | same |
| True links | 4 | — | same |
| False merges | 0 | 8 evaluated different-identity pairs | same |
| False non-links | 10 | 14 same-identity universe pairs | same |
| Unsafe under-specified links | 0 | — | same |
| Blocking-conflict recall | 1.000 | — | same |
| Weighted safety score | -5 | — | same |

The live track records provider `openai_compatible`, model `Qwen/Qwen3-30B-A3B-Instruct-2507`, temperature `0`, prompt version `v2`, and `execution_mode: live_provider` with fixture and identity-assignment hashes. It is never combined with Track A.

### Failed predeclared target (kept visibly failed)

The V1 holdout safety bound does **not** meet its predeclared `10.0%` demonstration target: all 4 different-identity cases were withheld, but the conditional 95% Wilson upper bound is `48.989%`. This is asserted by `test_submission_evidence.py` (`risk_bound.target_status == "not_met"`) and surfaced in the Judge Mode "held-out synthetic risk artifact". It was not hidden or converted into a pass.

## 5. Live-provider evidence (separate from deterministic evaluation)

Deterministic mock replay (Track A) and the archived live run (Track B) are described separately in every artifact and in the UI. No deterministic/mock result is labelled as live-model performance, and no aggregate blends the two tracks. Repeated live-provider trials (three-run repeatability, confidence intervals) were not performed in this pass; the archived V2 result remains a single run.

## 6. Known limitations

- All identities, incidents, and benchmarks are synthetic; no real-world accuracy, demographic fairness, or deployment evidence exists.
- The archived live result is a single run with no repeated-run confidence interval and no live same-model single-prompt comparator.
- Small negative-case denominators (8 different-identity pairs in the 21-case replay; 8 in the live decision metric) make "zero false merges" preliminary only.
- Repository-wide Ruff (184 findings) and mypy (139 findings across 16 files) remain unresolved debt; they are reported, not hidden.
- Transliteration covers selected scripts and common variants, not every language or naming convention.
- Audit hashes detect chained metadata/payload mutation but do not cryptographically seal persisted rows; production would need access controls and external signing/anchoring.
- A ~9 px horizontal overflow was observed at a 318 px viewport (below the 320 px design floor); 390 px+ and desktop widths verified clean.
- THREADLINE has not been validated by any operational humanitarian organization.

## 7. Files changed (this pass)

- `README.md` — corrected stale validation counts to freshly measured results (backend 445→454 tests; frontend 26→35 tests; full ESLint now passes rather than "did not complete"; mypy 172/22 files → 139/16 files).
- `FINAL_RELEASE_REPORT.md` — this report (new).
- `docs/submission/README.md` — updated the release-status line from "pending" to "verified", pointing to this report.

Prior release-pass changes (already on disk and uncommitted) include the benchmark fairness fix, Judge Mode hardening, submission evidence artifacts, workflow documentation, and the V1 safety-bound correction. None of this pass's changes touched thresholds, scoring weights, candidate generation, conflict policy, fixtures, or identity assignments.

## 8. Submission checklist

- [x] Backend deterministic/unit/contract/safety suite: 454 passed
- [x] Deterministic 10-gate validator: PASS
- [x] Frontend behavior tests, typecheck, full lint, production build: all PASS
- [x] End-to-end demo (guided Judge Mode + workspace + conflicts + rivals + review): PASS
- [x] Benchmark integrity (input hashes, denominators, raw outputs, track separation): verified
- [x] Submission PDFs valid and derived from retained Markdown/JSON/CSV sources
- [x] Secret scan of submission artifacts and live-run data: 0 credential-shaped matches
- [x] Failed predeclared target remains visibly failed
- [ ] Repeated live-provider trials / confidence intervals — not performed (documented limitation)
- [ ] External operational validation — not performed (documented limitation)
