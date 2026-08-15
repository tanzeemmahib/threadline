# THREADLINE final validation

Historical validation date: 2026-08-09

Current cinematic pass date: 2026-08-11

## Current validation status

**PASS — the August 11 cinematic pass is validated for the synthetic hackathon demonstration.** The cinematic layer remains optional presentation: the evidence workflow, fail-closed language, API routes, review controls, and deterministic fixture behavior are still the source of product truth. This is not a production-deployment or real-world efficacy verdict.

The August 11 Higgsfield provenance is recorded, but asset generation is not product validation. The new optional atmosphere consists of a 278,404-byte silent VP8 WebM with a 79,134-byte static WebP poster fallback; the 8,609,831-byte source MP4 is not shipped. Mobile, reduced-motion, unsupported-video, and video-failure paths use the poster while the real interface remains HTML/CSS/SVG.

| August 11 asset | Dimensions / duration | SHA-256 |
|---|---|---|
| `docs/art-direction/higgsfield-hero-atmosphere-20260811.png` | 2688 x 1520; 5,526,363 bytes | `826efd60648c673bc0b8f7fdb9fdcaa87a2ecadfcfd72dab4224f0d64fc552c8` |
| Unshipped Seedance source MP4 | 1920 x 1080; 8.041667 s; 8,609,831 bytes | `80865eb8acf4dcb7f3498d8f498b34771a90395c696238478064b0efc9d5f731` |
| `frontend/public/media/threadline/hero-archive-loop.webm` | 1280 x 720; approximately 8 s; 278,404 bytes | `6e54c787086dd3d3b710235acae3383e030cb520398c59daa8b99f141bf9dd77` |
| `frontend/public/media/threadline/hero-archive-poster.webp` | 1920 x 1080; 79,134 bytes | `584085eb1454568a1d29139bec760c7e19053e9ccd8b00711c4104a542864581` |

## August 11 measured checks

| Surface | Result |
|---|---|
| Frontend behavior and cinematic contracts | 28 / 28 passed |
| Frontend TypeScript | passed (`tsc --noEmit`) |
| Frontend ESLint | full invocation passed |
| Frontend production build | passed on Next.js 16.3.0; `/`, `/benchmark`, `/demo`, `/methodology`, `/trials`, and `/workspace` prerendered; `/workspace/packet` server-rendered |
| Production dependency audit | 0 known production vulnerabilities (`npm audit --omit=dev`) |
| Backend suite | 451 tests passed; one upstream Starlette/httpx deprecation warning |
| Live HTTP integration smoke | passed against an isolated mock-provider database: health, demo/analyze/reload, four baselines, benchmark, ablation, eight trial fixtures, mutation preview/run, review/audit, durable job/result, export, and report |
| Browser route smoke | passed on the production build for all seven user routes at 390 px and 1440 px; one H1 per route, no page-level horizontal overflow, no page errors |
| Landing responsive matrix | passed at 375, 430, 768, 1024, 1440, and 1728 px |
| Motion and interaction | CTA pointer-down/release, restrained click pulse, SPA route acknowledgement, evidence disclosure, guided focus/Escape return, tab roving keys, and active-panel scroll passed |
| Media lifecycle | desktop/tablet WebM played and paused offscreen; mobile and reduced-motion skipped video; forced WebM failure retained the poster and complete HTML interface |
| Reduced motion | no video request, no route overlay, no hidden staged content, and no required scroll animation |
| Repository diff check | passed; only Git line-ending conversion warnings were emitted |

Browser screenshots of the final implemented product are retained at `docs/product-screenshots/cinematic-landing-desktop.png`, `docs/product-screenshots/cinematic-landing-mobile.png`, `docs/product-screenshots/cinematic-workbench-transition.png`, and `docs/product-screenshots/cinematic-live-workspace.png`. They are captures of the real website, not Higgsfield concepts.

## August 9 release decision (historical baseline)

The frontend redesign and current runtime suites are ready for a synthetic hackathon demonstration. The repository-wide ship verdict remains contingent on a fresh API integration smoke after the final route/wiring pass. Production extraction remains pinned to Prompt V2. Prompt V3 was tested live but not promoted because its recall gain came with a material precision and F1 regression.

## August 9 measured checks (historical baseline)

| Surface | Result |
|---|---|
| Backend suite | 445 tests passed |
| Identity-resolution suite | 372 tests passed |
| Phase 11 extraction contract | 28 tests passed |
| Phase 10S deterministic validator | PASS, 10 / 10 gates |
| Frontend behavior suite | 26 / 26 passed |
| Frontend TypeScript | passed |
| Frontend ESLint | targeted changed TypeScript/TSX passed; refreshed full invocation did not complete in the validation window |
| Frontend production build | passed on Next.js 16.3.0 |
| Production dependency audit | previously reported 0 known vulnerabilities; not refreshed during the August 9 visual pass |
| API integration smoke | previously passed across health, analysis, baselines, benchmark, ablation, trials, review, jobs, result, export, and report paths; a fresh result must be recorded after any API wiring changes |
| Browser smoke | six-step guide completed; desktop and 390 px views had no page-level horizontal overflow; no console warnings or errors |
| Secret scan | previously reported no credential-shaped tracked values; rerun before external submission |

The full legacy Ruff and mypy baselines are not green: repository-wide Ruff reports 184 historical style errors, and mypy reports 172 errors across 22 files. Ruff passes on the production backend files changed for this release. Current backend runtime/contract/deterministic/safety checks and frontend behavior/type/build checks are green; the table distinguishes checks that were not refreshed during the August 9 pass.

The frontend visual pass also used three explicitly authorized Higgsfield 2K concept frames as art-direction references. Those PNGs live only under `docs/art-direction/`; the site does not ship or embed them. Composition, typography, archival texture, thread motion, and safety scenes were implemented natively in React, CSS, and SVG and visually checked at 1440 px and 390 px widths.

Implemented-product captures are retained separately at `docs/product-screenshots/implemented-landing-desktop.png`, `docs/product-screenshots/implemented-workbench-transition.png`, and `docs/product-screenshots/implemented-landing-mobile.png`. These are browser screenshots of the real interactive frontend, not generated concepts.

## Integrity pins

- Fixture SHA-256: `eed1032519f78ebfd18a49da55c920c1b280ade1b7e32ebda514157ff1ead850`
- Canonical identity-assignment SHA-256: `5baf5a35a0641eeb7496abd5c133540526bfa7e0ac031e086de397c86c36e569`
- Deterministic mock-v3 artifact SHA-256: `1428d677737582d23036118de9015fd721ee17ebdd90cb7ca078a26806d0eadd`
- Full live Prompt V2 artifact SHA-256: `c8b43f4f90549b2f32abec3449c7fcb791723d90cab242aef95fc9da06fbb117`
- Full live Prompt V2 raw-output SHA-256: `bd2b1170916257b872994b3fbe38110408d5010cc8abd9d7663ff911b9093bf5`
- Full live Prompt V3 artifact SHA-256: `d1c6f17fe48598754290bc07a24b2d159d707483b92b4eca9c33cb3ca4673a02`
- Full live Prompt V3 raw-output SHA-256: `400e7efaa677809850c1f562020cb636623ee7b5a1943f1f4effcf24e454fc24`

## Live prompt decision

| Metric | Prompt V2 archived production artifact | Prompt V3 full trial |
|---|---:|---:|
| Extraction success | 57 / 58 | 58 / 58 |
| Micro recall | 0.8626 | 0.8846 |
| Micro precision | 0.8396 | 0.6736 |
| Micro F1 | 0.8509 | 0.7648 |
| True links | 4 | 4 |
| False non-links | 10 | 10 |
| False merges | 0 | 0 |
| Unsafe links | 0 | 0 |
| Blocking-conflict recall | 1.000 | 1.000 |
| Weighted safety score | -5 | -5 |

Prompt V3 improved completion and recall, but introduced 78 false-positive extracted fields and lost substantial precision. It remains an experimental artifact. V2 is the safer balanced production prompt until V3 field attachment and hallucination behavior are corrected and repeated live trials are available.

## Remaining limitations

- All evaluation data is synthetic; results do not establish real-world accuracy, demographic fairness, or deployment readiness.
- The primary V2 and experimental V3 live results are single runs, so provider repeatability confidence intervals are not available.
- Full-repository static-analysis debt remains, even though the changed production files and all runtime validation paths pass.
- A public deployment and recorded demo require external hosting and recording authorization.
