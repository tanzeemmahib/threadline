# Integration testing

## Automated matrix

Backend checks cover strict schemas, all 12 workflow nodes, provider retries/timeouts, deterministic generation, metrics/ablations, all 15 trial mutations, eight trial fixtures, restart persistence, reviews/audit, jobs/cancellation, multi-seed bootstrap results, risk–coverage, adaptive routing, exports, and reports.

Frontend checks cover route/contract structure, centralized fetch ownership, explicit fixture labels, workspace synchronization, accessible trial tabs, all mutation controls, review safety language, and output-source labels. The production build is the final Next.js/CSS integration check.

## Live smoke sequence

Run `scripts/integration-smoke.ps1` against a running backend. It checks health, the eight-case catalogue, deterministic preview, trial execution, and result reload. The broader manual sequence should also analyze `/api/v1/demo`, save/reload a review, create and poll a benchmark job, cancel a queued/running job, reload the result after restart, and export JSON/CSV/Markdown manifests.

The real-provider smoke script is opt-in: set the `LLM_*` variables and run `python backend/scripts/real_provider_smoke.py` from the backend import context. It prints only safe run metadata.
