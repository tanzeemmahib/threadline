# THREADLINE

Reconnect fragmented records. Preserve human judgment.

THREADLINE is an uncertainty-aware humanitarian record-reconciliation research prototype. It proposes evidence-linked candidate connections for authorized review and does not autonomously determine identity. Every included identity, incident, benchmark, trial, and screenshot fixture is synthetic.

## Integrated repository

```text
frontend/   Next.js 16 / React 19 workspace, evaluation laboratory, and Trials UI
backend/    FastAPI workflow, SQLite persistence, jobs, trials, and evaluation engine
docs/       API, schemas, data cards, threat model, and reproducibility guidance
shared/     canonical synthetic request/response examples
scripts/    Windows PowerShell start and integration-smoke commands
```

The frontend routes are `/`, `/workspace`, `/workspace/packet`, `/benchmark`, `/trials`, and `/methodology`. The existing visual language, responsive behavior, RTL evidence, keyboard focus, reduced-motion handling, and print packet remain intact.

## Quick start on Windows

Backend (Python 3.11+):

```powershell
Set-Location backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
Copy-Item .env.example .env
Set-Location ..
.\scripts\start-backend.ps1
```

Frontend (Node.js 20+), in another terminal:

```powershell
npm --prefix frontend install
.\scripts\start-frontend.ps1
```

Open `http://localhost:3000`. `NEXT_PUBLIC_API_URL` defaults to the local backend in the start script. Without a URL, the workspace is explicit fixture mode. Failed requests are never silently replaced; the interface shows `Backend unavailable — synthetic fallback active` with retry/cancel state.

## Provider modes

`LLM_PROVIDER=mock` is the network-free default. UI labels are `Deterministic mock provider` and `Deterministic mock evaluation — not real model performance`. Connected OpenAI-compatible mode uses `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, and `LLM_MAX_CONCURRENT_CALLS`; the UI labels it `Connected model provider` / `Measured provider evaluation`. Legacy `THREADLINE_OPENAI_*` variables still work. Keys remain server-side and are removed from exports.

## Durable workflow and research evaluation

SQLite at `backend/data/threadline.db` stores workflow runs, results, reviews, audit events, trials, jobs, reports, and export metadata across restarts. Evaluation jobs default to one concurrent job and expose queued/running/completed/failed/cancelled state, real progress, cancellation, errors, and reloadable result IDs.

The benchmark runs exact/fuzzy, generic single-call, structured single-call, and the 12-stage THREADLINE workflow on identical records. Multi-seed defaults are `[104, 205, 306, 407, 508]`; aggregates include mean/std/min/max and fixed-seed bootstrap 95% intervals. Risk–coverage uses an observable review-priority score, never a probability. The adaptive router chooses deterministic-only, reduced, or full processing from observable complexity and compares actual metrics, calls, and duration.

THREADLINE Trials includes eight fixtures (`TRIAL-001`…`008`) and 15 deterministic mutation types. Mutation records preserve ground truth, which is never included in model prompts. Trial results store all four outputs, a deterministic first-divergence finding, full workflow trace, provider mode, seed, mutations, and exportable result ID.

## Quality and smoke checks

```powershell
Set-Location backend
python -m ruff check app tests
python -m ruff format --check app tests
python -m mypy app
python -m pytest

Set-Location ..\frontend
npm run lint
npm run typecheck
npm test
npm run build

Set-Location ..
.\scripts\integration-smoke.ps1
```

The opt-in connected-provider smoke is `python backend/scripts/real_provider_smoke.py` after setting `LLM_*` variables.

## Safety boundary

- No public people search, facial recognition, biometrics, identity probability, or automatic identity decision.
- Original evidence remains immutable; derived fields cite source spans and provenance.
- Prompt-like record text is quarantined before model-backed reasoning.
- Candidate classifications are limited to strong-for-review, possible, insufficient, and conflicting.
- Review actions record workflow state only; authorized external verification remains required.
- Synthetic benchmark performance does not establish field safety or fairness.

Start with [API contract](docs/api-contract.md), [THREADLINE Trials](docs/threadline-trials.md), [THREADBENCH data card](docs/threadbench-data-card.md), [reproducibility](docs/reproducibility.md), and [threat model](docs/threat-model.md).
