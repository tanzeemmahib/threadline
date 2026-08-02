# THREADLINE backend

FastAPI/Pydantic v2 implements the fixed 12-stage THREADLINE decision-support workflow, deterministic and OpenAI-compatible providers, SQLite persistence, bounded async evaluation jobs, synthetic trials, baselines, benchmarks, ablations, multi-seed statistics, risk–coverage, adaptive routing, reports, and exports.

THREADLINE proposes candidate record connections for authorized human review and does not autonomously determine identity.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Mock mode is credential-free and network-free. Connected mode uses the `LLM_*` settings documented in `.env.example`, with bounded timeout, retries, and a shared async call semaphore. `GET /health` reports mode/configuration/model but never returns keys.

## Storage and jobs

The default SQLite database is `data/threadline.db`; exports are written to `data/exports/`. Both are ignored. JSON artifacts retain stable IDs and metadata, reviews append human audit events, and workflow/results/trials reload after process restart. SQLite is appropriate for the local single-process prototype; distributed deployments need an external database/job queue.

Job endpoints queue benchmark, ablation, or trial work. Default `MAX_CONCURRENT_EVALUATION_JOBS=1`. States are queued, running, completed, failed, and cancelled with progress, completed/total cases, stage, timestamps, result ID, safe error, and retryability.

## Endpoint groups

- Health/demo/analysis: `/health`, `/api/v1/demo`, `/api/v1/analyze`
- Baselines/evaluation: `/api/v1/baselines/run`, `/benchmark/generate`, `/benchmark/run`, `/ablation/run`
- Persistence/review: `/workflow-runs/{id}`, `/results`, `/results/{id}`, `/reviews`, `/cases/{id}/audit`
- Trials: `/trials/cases`, `/trials/preview`, `/trials/run`, `/trials/{id}`, `/trials/{id}/rerun`
- Jobs: `/jobs/benchmark`, `/jobs/ablation`, `/jobs/trial`, `/jobs/{id}`, `/jobs/{id}/cancel`
- Artifacts: `/results/{id}/export`, `/results/{id}/report`

Interactive OpenAPI documentation is at `http://127.0.0.1:8000/docs`.

## Evaluation semantics

Benchmark ground truth stays outside model prompts. Multi-seed defaults are 104/205/306/407/508. Fixed-seed bootstrap intervals use 1,000 resamples. Risk–coverage scores observable review complexity rather than identity likelihood. Adaptive routing uses deterministic-only/reduced/full profiles and never changes the human-review boundary. Export JSON/CSV/Markdown content is scrubbed of credential-shaped keys and includes a SHA-256 manifest.

## Quality

```powershell
python -m ruff check app tests
python -m ruff format --check app tests
python -m mypy app
python -m pytest
```

The connected-provider smoke is explicitly opt-in: set `LLM_API_KEY` and run `python scripts/real_provider_smoke.py` from this directory.
