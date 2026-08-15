# Reproducibility

The judge-facing, offline-first procedure is maintained in [`docs/submission/reproduction.md`](submission/reproduction.md). It includes the one-command proof demo, the submission-evidence generator, cold-start rehearsal, and file-integrity checks.

1. Use Python 3.11+ and Node.js 20+.
2. Leave the backend on its default `LLM_PROVIDER=mock` for offline deterministic runs. A copied `backend/.env` is optional and must remain untracked.
3. Start the backend with `scripts/start-backend.ps1` and frontend with `scripts/start-frontend.ps1`.
4. Record the Git commit, application version, provider mode, configured model name, benchmark configuration, seeds, dataset content hashes, run IDs, and result IDs.
5. Run `python -m pytest`, Ruff, Mypy, frontend lint/typecheck/tests/build, and `scripts/integration-smoke.ps1`. Record failures as failures: the last full audit retained known repository-wide Ruff and mypy debt, and the August 9 frontend refresh completed targeted ESLint but the full ESLint invocation did not finish in the validation window.

Dataset mutation and mock model payloads are deterministic. Wall-clock durations are measurements and will vary. Multi-seed statistics therefore reproduce classification/quality aggregates while operational duration remains environment-specific. Generated exports include hashes and provider mode, but never credentials.

## Submission evidence bundle

From `backend/`, regenerate the deterministic comparison, per-case outputs, ablations, counterfactual, CSV, and report with:

```powershell
./.venv/Scripts/python.exe scripts/build_submission_evidence.py
```

The generator writes under `docs/submission/` and records the visible Git commit plus a dirty-working-tree flag. The offline comparison keeps identical case input and the same deterministic mock provider/model across the included one-call baselines and full workflow. It is explicitly labeled **Deterministic mock replay - not model performance**.

Archived live-provider Prompt V2 extraction remains a separate evidence track. It must not be blended with deterministic mock metrics or described as a live same-model baseline comparison.

Real-provider reproduction additionally requires an equivalent OpenAI-compatible endpoint and model configuration. Provider behavior can change outside this repository; reports must retain the provider/model label and distinguish real-provider measurements from mock results. The repository contains one archived full run for Prompt V2 and one for Prompt V3; neither result has a repeated-run confidence interval.

## Provider-dependent live extraction reproduction

Live reproduction is opt-in and can spend provider credits. From `backend/`, configure `LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, and the timeout/retry/concurrency values in a local untracked `.env`. Then run the versioned runner with the repository virtual environment:

```powershell
./.venv/Scripts/python.exe scripts/live_phase11_runner.py --mode full --prompt v2 --runs 1 --out data/live_runs_phase11_reproduction
./.venv/Scripts/python.exe scripts/live_phase11_runner.py --mode full --prompt v3 --runs 1 --out data/live_runs_phase13_reproduction
```

The runner checkpoints `raw-outputs.json` after each record. Re-running the exact command and output directory resumes from completed records. If a checkpoint contains provider errors, add `--retry-errors`; successful entries are reused and only error entries are submitted again. Use a new output root for an independent trial. Do not overwrite the archived primary artifacts. Preserve the runner console metadata, prompt version, provider/model, fixture and identity-assignment hashes, run directory, `raw-outputs.json`, and `live-artifact.json`. Never commit the local `.env` or print the API key.

The archived V2/V3 live artifacts do not record the exact Git commit or dirty-tree patch that produced them. That field is **Not recorded** and must not be retroactively replaced with the repository's current commit. Their source fixture hashes, prompt version, provider/model, temperature, timestamps, raw outputs, and evaluation artifacts remain available.

## Benchmark ground-truth versioning

`backend/fixtures/identity_benchmark.json` is the historical (v1/v2) benchmark and is treated as byte-stable: its SHA-256 is pinned in artifacts and in the v3 companion fixture. `backend/fixtures/identity_benchmark_identity_v3.json` holds canonical v3 `fictional_identity_id` assignments without modifying the historical fixture. Benchmark artifacts serialize `ground_truth_schema`, `identity_schema_version`, `fixture_sha256`, and `identity_assignment_sha256` so metrics can be reproduced and never compared across truth schemas. See `synthetic-benchmark-schema.md` for the canonical latent-identity truth model.
