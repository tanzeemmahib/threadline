# THREADLINE repository baseline

Baseline date: 2026-08-03  
Working tree: pre-existing modified and untracked files were present before this build; they were preserved.

## Architecture

- **Frontend:** Next.js 16.2.12 App Router, React 19.2.4, strict TypeScript 5, Tailwind CSS 4 plus project-owned CSS files. npm scripts are the documented execution surface; `package-lock.json` is present, while the current `node_modules` layout contains pnpm links.
- **Backend:** FastAPI/Pydantic v2 on Python 3.11+, SQLite persistence, deterministic mock and optional OpenAI-compatible providers, a 12-stage workflow, durable evaluation jobs, evidence contracts, canonical audit hashes, replay, and counterfactual certificates.
- **Application entry points:** `frontend/src/app/layout.tsx`, route `page.tsx` files, `backend/app/main.py`, and `backend/app/api/routes/__init__.py`.
- **Frontend routes:** `/`, `/workspace`, `/workspace/packet`, `/benchmark`, `/trials`, `/methodology`; Next also emits `/_not-found`.
- **Backend routes:** health, demo, analysis, baselines, benchmark, ablation, evidence contracts, ingestion, integrity, replay, counterfactuals, jobs, durable results/exports/reports, reviews/audit, and trials under `/api/v1`.
- **Component structure:** shared header/brand/status components; landing evidence thread and workflow; workspace shell with record browser, synchronized reconstruction, evidence reasoning, exact-span dialog, review, workflow explorer, and audit ledger; separate benchmark/trials laboratories.
- **Evidence model:** immutable original source text and half-open character spans; extracted fields and additive normalized values; compatibility factors; contradictions; close rivals; 18-rule evidence contracts; claim ancestry/hashes; release status; audit-chain events; replay and counterfactual certificates.
- **Styling:** global CSS tokens plus route-oriented CSS (`landing.css`, `workspace.css`, `research.css`, evaluation/methodology/trials/print layers). Native SVG is used for relationships, maps, and charts. No additional runtime UI dependency exists.
- **Assets:** favicon and five stock Next.js starter SVGs. No production photography or generated THREADLINE cinematic media exists. The creative manifest began with zero assets.

## Current behavior

The current landing page is an editorial product explanation with a static animated SVG evidence thread. The workspace is already functional: records and candidate threads are selectable; record/factor/event/location state is synchronized; exact source spans open in a native dialog; rivals, contradictions, contracts, replay, counterfactuals, review outcomes, and audit events are exposed.

The current visual system is credible but not yet the requested premium product. It uses near-target dark colors, Georgia display typography, small dense controls, mostly static landing composition, a relationship visualization whose internal SVG paths are not themselves selectable, and no guided cinematic demo controller. The candidate-to-normalized-to-extracted-to-source lineage exists in contract content and the evidence dialog, but it is not yet one continuous signature interaction.

## Responsive and accessibility baseline

Present controls include semantic landmarks, a skip link, route titles, `:focus-visible`, native buttons/details/dialogs, live regions, tab semantics, SVG descriptions, text/list alternatives, Arabic `lang`/`dir`, print styles, and a global reduced-motion rule. Desktop uses a three-column workspace; tablet collapses panels; under 768px the workspace becomes explicit tabs and tables scroll locally.

Gaps at baseline:

- no browser end-to-end or automated accessibility test dependency;
- no roving-arrow keyboard behavior for graph-style node groups;
- evidence graph edges are visual paths rather than interactive controls;
- several dense interface labels are below the preferred 12px caption floor;
- the landing evidence nodes do not expose focused micro-previews or restrained pointer parallax;
- action controls do not model all requested loading/success/warning/failure states;
- no guided demo mode or step announcements.

## Exact command results

### Frontend

| Command | Result |
|---|---|
| `node --version` | Exit 0 — `v24.16.0` |
| `npm --version` | Exit 0 — `11.13.0` |
| `npm ls --depth=0` | Exit 0, but reports a large set of **extraneous** packages. Declared direct packages resolve through `.pnpm`; this is a package-manager/layout hygiene warning, not a build failure. |
| `npm run lint` | Exit 0 — ESLint produced no findings. |
| `npm run typecheck` | Exit 0 — `tsc --noEmit` produced no findings. |
| `npm test` | Exit 0 — 24 tests passed; 0 failed, skipped, or cancelled; duration 529.2735 ms. |
| `npm run build` | Exit 0 — Next.js 16.2.12 compiled successfully in 6.5 s, TypeScript completed in 19.5 s, and 9 static pages were generated in 737 ms. `/workspace/packet` is dynamic; other application routes are static. |

### Backend

The `python` and `python3` commands initially resolved to the Windows Store aliases and failed with exit code 9009. The installed interpreter is available as `py -3.13` (`Python 3.13.2`). Its global environment had none of Ruff, mypy, or pytest, so a repository-local `backend/.venv` was created from the checked-in `requirements.txt` and `requirements-dev.txt`. The first install command exceeded the 120-second shell observation timeout but continued as its child process; a concurrent retry encountered transient `WinError 32` on a mypy file. The original process completed, after which `pip check` and all quality commands ran successfully.

| Command | Result |
|---|---|
| `.venv\Scripts\python.exe -m pip check` | Exit 0 — `No broken requirements found.` |
| `.venv\Scripts\python.exe -m ruff check app tests` | Exit 0 — `All checks passed!` |
| `.venv\Scripts\python.exe -m ruff format --check app tests` | Exit 0 — `106 files already formatted`. |
| `.venv\Scripts\python.exe -m mypy app` | Exit 0 — `Success: no issues found in 91 source files`. |
| `.venv\Scripts\python.exe -m pytest` | Exit 0 — 59 passed in 34.17 s. One third-party `StarletteDeprecationWarning` says Starlette's use of `httpx` test client is deprecated in favor of `httpx2`. |

### Integration

The audited `scripts/integration-smoke.ps1` was run against a temporary local backend on `127.0.0.1:8011`, using deterministic mock mode and a repository-local database at `creative/threadline/exports/baseline-integration.db`. The backend process was stopped immediately after the check.

Result: pass — health, demo/analyze/reload, four baselines, benchmark, ablation, eight trial fixtures, mutation preview/run, review/audit, durable job/result, export, and report all completed.

## Pre-existing failures and warnings

1. The unqualified `python` command is unusable in this environment; repository scripts that call `Get-Command python` without preferring `backend/.venv` may fail unless `THREADLINE_PYTHON` is set. `scripts/start-backend.ps1` already prefers the local venv, while `scripts/run-v1-demo.ps1` does not.
2. The existing frontend dependency directory mixes npm metadata with a pnpm-style installation and produces extensive extraneous-package warnings under `npm ls`.
3. Backend tests emit one dependency deprecation warning from FastAPI/Starlette test client integration.
4. No existing browser E2E suite verifies rendering, keyboard travel, focus restoration, or responsive layout.

No baseline source failure was found in lint, type checking, unit tests, production build, Python static analysis, Python unit/integration tests, or the integration smoke path.
