# THREADLINE submission reproduction

This guide reproduces the offline judge path and the saved synthetic evidence package without a network connection or API credential. Commands assume Windows PowerShell from the repository root.

## 1. Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer
- npm
- PowerShell 7 recommended

Install backend dependencies:

```powershell
cd backend
py -3.11 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
cd ..
```

Install the pinned frontend dependency tree:

```powershell
cd frontend
npm ci
cd ..
```

Do not create a live-provider `.env` for the offline path. The default is `LLM_PROVIDER=mock`.

## 2. One-command deterministic proof demo

```powershell
./scripts/run-v1-demo.ps1
```

If the local execution policy blocks the script:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./scripts/run-v1-demo.ps1
```

The launcher builds and starts the frontend when needed, starts an isolated mock-provider backend, writes its SQLite database under the system temporary directory, and exercises:

- a release-eligible authorized-review packet;
- a hard-conflict withheld packet;
- an insufficient-evidence packet;
- audit-chain verification and copied-database tamper detection;
- exact deterministic replay; and
- a curated source-removal counterfactual.

The script prints exact workspace URLs and process IDs. It does not modify source fixtures or require a provider key.

For the eight-scene judge experience, open:

```text
http://127.0.0.1:3000/demo?demo=guided
```

Select **Start evidence challenge**. Complete the sequence in `demo-script.md`.

## 3. Generate the locked submission evidence

From `backend`:

```powershell
./.venv/Scripts/python.exe scripts/build_submission_evidence.py
```

The generator writes these versioned judge artifacts under `docs/submission/`:

- `results.json` - compact deterministic and archived-live summaries;
- `results.csv` - metric rows with numerators and denominators;
- `raw-outputs.json` - per-case deterministic outputs and exact judge-case inputs;
- `ablation-counterfactual.json` - measured ablations plus a source-removal counterfactual; and
- `benchmark-report.md` - human-readable results, caveats, and reproduction command.

The deterministic comparison uses the same generated case input for each included system and records the input SHA-256 by system. It is labeled **Deterministic mock replay - not model performance**. The archived Prompt V2 live-provider extraction result remains a separate evidence track and is never blended into mock metrics.

The generator records the Git commit visible at generation time and whether the working tree is dirty. A dirty-tree flag means the commit alone is not a complete code identity.

## 4. Rebuild the held-out V1 evaluation

From `backend`:

```powershell
./.venv/Scripts/python.exe scripts/build_v1_evaluation.py
```

The authoritative machine-readable output is `shared/evaluation/threadline-v1.json`. The split is grouped by fictional identity, and the artifact reports its dataset content hash and identity-overlap count. The current locked V1 artifact records:

- candidate top-1 recall: `4/36` (`11.111%`);
- released-review precision: `3/3`;
- different-identity cases withheld: `4/4`;
- same-identity cases withheld by the evidence contract: `7/36`;
- rule coverage: `10/18`;
- conditional false-merge Wilson upper bound: `48.989%`, with the denominator and condition shown in the artifact;
- target status: not met; and
- whole-record-removal counterfactual coverage: `40/40`.

These V1 measures use their saved definitions and must not be relabeled as standard retrieval recall or broad real-world safety estimates. The archived live Prompt V2 artifact reports a separate `14/14` candidate-retrieval result.

## 5. Verify file integrity

```powershell
$paths = @(
  'backend/fixtures/identity_benchmark.json',
  'backend/data/live_runs_phase11/full-prompt-v2-run-1/live-artifact.json',
  'backend/data/live_runs_phase11/full-prompt-v2-run-1/raw-outputs.json',
  'shared/evaluation/threadline-v1.json',
  'docs/submission/results.json',
  'docs/submission/raw-outputs.json',
  'docs/submission/ablation-counterfactual.json',
  'docs/threadline-workflow.svg',
  'docs/threadline-workflow.png'
)
$paths | ForEach-Object { Get-FileHash -Algorithm SHA256 $_ }
```

The archived Prompt V2 pins expected source hashes in its result package. Submission-package files are regenerated artifacts, so compare their printed hashes with the current `docs/submission/README.md` handoff or final release report rather than assuming a timeless value.

## 6. Run verification checks

Backend runtime and proof checks:

```powershell
cd backend
./.venv/Scripts/python.exe -m pytest
./.venv/Scripts/python.exe _phase10s_validate.py
./.venv/Scripts/python.exe -m pytest tests/test_phase11_extraction_contract.py
cd ..
```

Frontend checks:

```powershell
cd frontend
npm test
npm run typecheck
npm run lint
npm run build
cd ..
```

With the backend running:

```powershell
./scripts/integration-smoke.ps1
```

Repository-wide Ruff and mypy are also part of the complete audit, but the repository may retain known pre-existing debt. Record their exact result; do not convert a failure into a pass:

```powershell
cd backend
./.venv/Scripts/python.exe -m ruff check app tests scripts
./.venv/Scripts/python.exe -m mypy app
cd ..
```

## 7. Cold-start rehearsal

1. Use a fresh terminal with no `LLM_API_KEY`.
2. Run `./scripts/run-v1-demo.ps1`.
3. Open `/` and select **Run the evidence challenge**.
4. Complete all eight scenes.
5. In **Evidence extraction**, open an exact source span and close it with `Escape`.
6. Confirm the material location contradiction produces **Withheld**.
7. Confirm the rival remains visible.
8. Open **View technical evidence**.
9. Select **Reset** and start again.
10. Open a printed workspace URL and inspect its evidence contract and audit state.
11. Confirm no network request to a model provider and no credential prompt occurred.

## 8. Optional connected-provider reproduction

Connected reproduction can spend provider credits and can expose submitted record content to the configured endpoint. Use fictional data only.

From `backend`, copy `.env.example` to an untracked `.env` and configure `LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, timeout, retry, and concurrency values. Then run:

```powershell
./.venv/Scripts/python.exe scripts/live_phase11_runner.py --mode full --prompt v2 --runs 1 --out data/live_runs_phase11_reproduction
```

Use a new output directory for an independent trial. Do not overwrite the archived primary result. Preserve the prompt version, provider/model label, temperature, run timestamp, fixture hash, canonical identity-assignment hash, raw outputs, retries, and errors.

The repository does not contain a repeated live same-model single-prompt versus full-workflow comparison. Mark that comparison **Not measured** unless a real, locked artifact is added.

## 9. Interpretation boundary

All generated cases are synthetic. A correctly withheld case is not a model failure, a proposed connection is not identity confirmation, and a counterfactual that relaxes a rule does not prove that records describe the same person. Reproduction demonstrates code-path behavior and saved measurements only.
