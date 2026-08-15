# THREADLINE implementation validation — historical August 3 snapshot

Date: 2026-08-03 (America/Vancouver)

> Superseded release evidence: this file preserves the August 3 implementation snapshot. Its 62-test/91-source static-analysis counts and zero-generation statement are not current release-wide claims. Use `docs/final-validation.md` for August 9 validation and `creative/threadline/manifests/generation-manifest.json` for the current Higgsfield invocation ledger.

## Outcome

THREADLINE now has one deterministic, end-to-end fictional cyclone case that moves from six source records through exact source spans, claim transformations, candidate-scoped evidence, a blocking evidence contract, authorized review, a structured disposition, and an append-only audit history.

The leading candidate is deliberately withheld. The unresolved Narin Quay versus Hillcrest School location contradiction blocks release, all candidate classification fields are cleared, and the only final disposition is linked to an authorized human review record.

## Acceptance coverage

- Six synthetic records from five fictional organizations; English and Arabic originals plus translation artifacts.
- Name spelling variations, birth-date discrepancy, material location contradiction, shared emergency contact, partial family evidence, 34-hour missing interval, leading thread, and credible rival.
- Immutable half-open source offsets, exact quotations, SHA-256 validation hashes, language, validation state, and creation metadata.
- Extracted, normalized, timeline, compatibility, contradiction, and rival claims with parent links, transformations, certainty categories, candidate scope, and consuming rule IDs.
- Candidate-scoped ledger separates support, contradictions, timeline claims, rival comparisons, missing evidence, follow-up evidence, safety notices, and contract results.
- All ten canonical deterministic rules execute with versioned statuses, reason codes, input artifacts, related spans, evaluator version, and evaluation timestamp.
- Closed release-state union prevents review-required and blocked responses from containing an autonomous decision.
- Structured review records rationale, remaining uncertainty, requested evidence, reviewer identity, contract/candidate references, and disposition.
- Backend review persistence appends `review_opened` and `authorized_disposition_recorded` events to the hash chain.
- Audit verification detects deletion, reordering, payload mutation, and broken previous-hash references.
- `/demo` is a real static route using application components, fixtures, and services; it supports reset, manual exploration, a 13-step guided mode, keyboard controls, and no live services.
- Landing page, README, methodology documentation, and demo use the canonical evidence-operating-system positioning and `PROOF BEFORE RELEASE` boundary.

## Rendered production checks

Checks were performed against `next start` using the optimized production build.

- Desktop 1440×810: three-column investigation workspace, blocked contract panel, source navigator, reconstruction, and guided controls rendered without stale routing warnings.
- Signature lineage opened the actual candidate claim, normalized and extracted parents, exact quotations, offsets, hashes, certainty, transformations, and consuming contract rules.
- Authorized review was opened, the exact location conflict rationale was entered, `additional_evidence_required` was saved, and an `authorized disposition recorded` audit item appeared.
- Mobile 390×844: all six source records, five workspace tabs, reset, and guided controls remained available; the global navigation fit without horizontal overflow.
- Interactive graph/source/review controls are native buttons or links and remain keyboard reachable.

## Historical command evidence (August 3 only)

| Command | Result |
|---|---|
| `backend/.venv/Scripts/python.exe -m ruff check app tests` | PASS |
| `backend/.venv/Scripts/python.exe -m ruff format --check app tests` | PASS, 107 files formatted |
| `backend/.venv/Scripts/python.exe -m mypy app` | PASS, 91 source files |
| `backend/.venv/Scripts/python.exe -m pytest tests -q` | PASS, 62/62; one third-party Starlette/httpx deprecation warning |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS, 26/26 |
| `npm run build` | PASS; `/demo` statically prerendered and packet route server-rendered |
| `scripts/integration-smoke.ps1` | PASS: health, analyze/reload, baselines, benchmark, ablation, trials, review/audit, job/result, export, and report |

## Remaining bounded gaps

- The deterministic fixture keeps a session-only review event in the browser for offline demos and explicitly marks its local integrity summary `incomplete`; backend-connected review is the authoritative persisted and hash-verified path.
- Full browser journeys are manually exercised plus structurally tested; a dedicated Playwright CI suite is still a post-95% hardening item.
- The third-party Starlette/httpx deprecation warning remains; it does not affect test results.
- Substantial cinematic production is intentionally deferred until product approval.

## Credit and repository safety (August 3 phase only)

- Higgsfield generation commands executed in this phase: **0**.
- Paid credits spent in this phase: **0**.
- `paid_generation_authorized`: **false**.
- Optional 72-credit plate remains `cost_estimated`, `generation_submitted: false`, and ungenerated.
- Git staged files: **0**; no secrets or authentication files were staged.

## August 9 visual-direction update

The user later explicitly authorized three Higgsfield `gpt_image_2` 2K, 16:9 concept frames: opening, archive/workbench, and safety/abstention. They are stored under `docs/art-direction/` and are not shipped or embedded by the frontend. The landing experience translates their direction into semantic React, CSS, and SVG. Current frontend evidence is 26/26 behavior tests, passing typecheck, passing production build, targeted ESLint over the changed TypeScript/TSX, and browser QA at desktop and 390 px mobile widths. The refreshed full frontend ESLint invocation did not complete in the validation window.
