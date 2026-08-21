# THREADLINE — Reverie Hacks 2026 submission checklist

Last documentation pass: 2026-08-20  
Track: ML Prompt Engineering  
Scope: fictional synthetic research demonstration

This file separates **artifact-complete** items from **release-owner runtime gates**. An unchecked box is not a hidden pass.

## 1. Judge comprehension and winning story

- [x] Landing position is defined: **Connect the records. Never guess the person.**
- [x] Guided narrative begins with three organizations, fragmented records, and a plausible rival.
- [x] Same-record one-shot comparison is included and labelled deterministic replay — not model performance.
- [x] Valid `FAMILY-018 ↔ SHELTER-204` outcome is described only as a supported possible connection for authorized human review.
- [x] `HOSPITAL-052` is the dangerous rival; exact age/timeline evidence triggers deterministic blocking rules.
- [x] Closing line is qualified: “connection recovered” means candidate record connection, not person identified.
- [ ] Fresh judge confirms the purpose and model/policy boundary within 30 seconds.
- [ ] Guided walkthrough is timed at 75–100 seconds without narration and under three minutes with narration.

## 2. ML Prompt Engineering track evidence

- [x] Editable workflow diagram exists: [`reverie-ml-workflow.svg`](reverie-ml-workflow.svg).
- [x] Submission PNG exists and was visually inspected at `2000 × 1200`: [`reverie-ml-workflow.png`](reverie-ml-workflow.png).
- [x] Diagram identifies human inputs, quarantine, five LLM operations, prompts, expected outputs, deterministic validation, retrieval, rival analysis, evidence contract, human review, withholding, audit, and replay.
- [x] Node-by-node rationale, failure behavior, validation boundary, and evaluation signal are documented: [`reverie-ml-track-documentation.md`](reverie-ml-track-documentation.md).
- [x] Same-input sample comparison exists: [`reverie-prompt-comparison.md`](reverie-prompt-comparison.md).
- [x] Machine-readable Prompt Lab artifact exists: [`submission/reverie-prompt-lab.json`](submission/reverie-prompt-lab.json).
- [x] Prompt V1/V2 comparison uses only the shared 19-record targeted cohort.
- [x] Prompt V2/V3 comparison uses only the shared 58-record full cohort.
- [x] Prompt V3 is marked **NOT PROMOTED / PRECISION REGRESSION** using archived counts.
- [x] Full 58-record V1 is explicitly **not available**; no three-way same-cohort ranking is claimed.
- [x] `/prompt-lab` browser surface loads the artifact and exposes inputs, prompt/config, raw and validated outputs, spans, comparisons, decision, and failure reason.

## 3. Scientific integrity

- [x] All records are visibly described as fictional and synthetic.
- [x] Deterministic mock workflow replay and archived live-provider extraction are kept as separate evidence tracks.
- [x] One-shot prompt is reasonable and not intentionally weakened.
- [x] The live same-model comparison is measured (18/18 runs, spec `THREADLINE-REVERIE-LIVE-EVAL-V1.1`) and reported with mixed outcomes and no superiority claim: one-shot outcome-acceptable 9/9 with 45 invalid citations; THREADLINE 0 invalid citations with abstention on 6/9 runs.
- [x] Zero false merges is shown with denominator `0/8`, not as “100% safe.”
- [x] False non-links remain visible (`10` in the archived V2 run).
- [x] Approximate API cost and confidence intervals are **Not measured** with reasons; per-repetition live results are reported individually.
- [x] Selected no-effect ablations remain reported.
- [x] Counterfactual changes contract permission only; it is not described as identity proof.
- [x] ICRC MPDM prior work is acknowledged; ICRC/OCHA references are not represented as endorsements.
- [x] Prompt Lab generator was rerun against the locked sources; artifact SHA-256 is `9d6aab126a610927b6aa24bb7c95ed8af03b52b85669a5adf79787e184fbcc83`.

## 4. Required files

- [x] `README.md`
- [x] `docs/reverie-ml-workflow.svg`
- [x] `docs/reverie-ml-workflow.png`
- [x] `docs/reverie-prompt-comparison.md`
- [x] `docs/reverie-ml-track-documentation.md`
- [x] `docs/reverie-demo-script.md`
- [x] `docs/reverie-judge-qa.md`
- [x] `docs/reverie-submission-checklist.md`
- [x] `docs/submission/reverie-prompt-lab.json`
- [x] Final desktop and mobile product screenshots copied to `docs/product-screenshots/reverie/`.
- [ ] Final demo video recorded with the three-minute script and offline backup checked.

## 5. Demo rehearsal

- [x] Timestamped script fits within three minutes on paper: [`reverie-demo-script.md`](reverie-demo-script.md).
- [x] Offline backup uses deterministic mock mode and never presents replay as a live call.
- [x] Judge Q&A covers prompt-engineering fit, one-shot rationale, hallucinations, identity authority, synthetic data, denominators, V3 rejection, scale, deployment, and limitations.
- [x] Cold start with no real `LLM_API_KEY` succeeds using the explicit local mock placeholder.
- [x] Primary landing CTA opens `/demo?demo=guided`.
- [x] Secondary CTA opens `/prompt-lab`.
- [x] Exact source span opens in one action and closes with `Escape`, restoring focus.
- [x] Valid candidate and blocked rival are both visible in the golden path.
- [x] Browser back, guided **Back**, **Next**, and **Reset** all work.
- [x] No API credential or external network access is needed for the deterministic path.
- [x] No placeholder, stale eight-scene copy, or contradictory metric appears in the judge path.

## 6. Accessibility and responsive QA

- [ ] Full keyboard-only golden path passes.
- [ ] Visible focus is retained on all controls.
- [x] Source and decision states do not depend on hover or colour alone.
- [x] Semantic headings and landmarks are correct on the landing, judge, Prompt Lab, and workspace routes.
- [ ] Screen-reader names distinguish **Supported**, **Contradicted**, **Missing**, **Inferred**, **Withheld**, and **Human review required**.
- [ ] `prefers-reduced-motion: reduce` removes travel-heavy motion without hiding state.
- [x] No page-level overflow at 390 px, 768 px, and desktop widths.
- [ ] No text required for comprehension is below 11–12 px.

## 7. Automated release gates

Record exact counts in the final release report; do not convert known debt into a pass.

```powershell
cd backend
$env:PYTHONPATH='.'
./.venv/Scripts/python.exe scripts/build_reverie_prompt_lab.py
./.venv/Scripts/python.exe -m pytest tests/test_reverie_prompt_lab.py
./.venv/Scripts/python.exe -m pytest
./.venv/Scripts/python.exe _phase10s_validate.py
./.venv/Scripts/python.exe -m pytest tests/test_phase11_extraction_contract.py
./.venv/Scripts/python.exe -m ruff check app tests scripts
./.venv/Scripts/python.exe -m mypy app
cd ../frontend
npm test
npm run typecheck
npm run lint
npm run build
cd ..
./scripts/integration-smoke.ps1
```

- [x] Prompt Lab artifact generator passed: `cases=3`.
- [x] Focused Prompt Lab tests passed: `10/10`, with one FastAPI/httpx deprecation warning.
- [x] Full backend tests pass: `464 passed`.
- [x] Deterministic validator passes all `10 / 10` gates.
- [x] Phase 11 extraction-contract tests pass: `28 passed`.
- [x] Frontend tests pass: `43 / 43`.
- [x] Frontend typecheck passes.
- [x] Frontend lint passes with zero errors and warnings.
- [x] Frontend production build passes; all 11 pages generate.
- [x] Both the full integration smoke and proof-layer demo smoke pass.
- [x] Ruff result recorded exactly: `185` findings across 17 files; named static-analysis debt.
- [x] mypy result recorded exactly: `139` errors across 16 files; named static-analysis debt.

## 8. Browser release gates

- [x] Fresh landing at desktop width: no console error, one dominant story, CTAs visible.
- [x] Fresh landing at 390 px: no overflow, readable hero, CTA above fold.
- [x] `/demo?demo=guided`: complete golden path, source opening, reset, and keyboard controls pass; reduced motion is covered by the CSS/contract gate below rather than browser emulation.
- [ ] `/prompt-lab`: all three cases, progressive disclosures, V1/V2/V3 experiment, malformed/backend-unavailable state.
- [ ] `/workspace`: evidence, review state, audit, retry/loading/empty/error states remain credible.
- [x] Route navigation and browser back do not double-fire or leave stuck interaction state.
- [x] No browser console errors or warnings on the golden path.
- [x] Screenshots captured for desktop landing, mobile landing, valid connection, blocked rival, Prompt Lab, and workspace.

## 9. Upload and integrity gate

- [x] Record SHA-256 for `docs/submission/reverie-prompt-lab.json`: `9d6aab126a610927b6aa24bb7c95ed8af03b52b85669a5adf79787e184fbcc83`.
- [x] Record workflow hashes: SVG `c6c03ebebbde6987f94defea2510c3eafcf600485b436bf40bc13f40133c034b`; PNG `c9a7f1e7bddd943637cdd3a988aef8be95aa3b9da7582fe0b22abc74717aff2a`.
- [x] Markdown-link and missing-asset check passed on 2026-08-20: `31` Markdown files, `79` local links checked, `0` missing targets.
- [x] Confirm `.env`, real credentials, real identities, and private data are absent from the submission scope; the only tracked key-shaped assignment is the literal `threadline-local-mock-placeholder` used by the offline runner.
- [x] Confirm required files open at normal document size; the workflow PNG was inspected at 2000 × 1200 and product screenshots were inspected at their target viewports.
- [x] Record final `git status --short` in the release response; unrelated `.gitignore`, `tmp/`, and inaccessible pre-existing `backend/.tmp/pytest-*` work remains preserved.
- [x] Name every failing or unexecuted gate in the final verdict.

## 10. Final verdict rule

- Use **SUBMISSION READY** only when every runtime, browser, accessibility, and upload gate above is checked.
- Use **READY WITH NAMED LIMITATIONS** when judge-visible requirements pass but documented research or repository-wide static-analysis debt remains.
- Use **NOT READY** if the golden path, artifact integrity, prompt comparison, workflow PNG, mobile layout, production build, or offline replay fails.
