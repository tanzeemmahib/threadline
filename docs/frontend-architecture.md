# THREADLINE frontend architecture

## Stack

- Next.js 16 App Router
- React 19
- strict TypeScript
- Tailwind CSS 4 plus project-owned CSS token and component layers
- native SVG for the evidence thread, workflow, and benchmark charts
- no added runtime dependencies

## Routes

| Route | Responsibility |
| --- | --- |
| `/` | Editorial product explanation, evidence-thread hero, and expandable workflow strip |
| `/workspace` | Synthetic incident browser, synchronized reconstruction, candidate reasoning, review, workflow inspector, and audit ledger |
| `/workspace/packet` | Print-optimized synthetic case-review packet |
| `/benchmark` | Deterministic dataset, baseline, ablation, error-analysis, and metric laboratories |
| `/trials` | Deterministic mutation configuration, before/after diff, system results, first divergence, stored trace, and exports |
| `/methodology` | System boundary, node contracts, prompt strategy, schemas, evaluation design, safety, and limitations |

No authentication, pricing, billing, settings, chat, or unrelated routes are included.

## Component structure

- `src/components/site-header.tsx`, `brand-mark.tsx`, and `status-pill.tsx` provide shared navigation and status language.
- `landing-evidence-thread.tsx` and `workflow-strip.tsx` build the landing explanation.
- `workspace/workspace-shell.tsx` owns demo interaction state only; record filtering, candidate visualization, review comparison, evidence dialog, and review dialog are separate components.
- `workflow-explorer.tsx` renders the twelve workflow nodes, replay state, node contracts, partial-failure copy, and browser-print export.
- `benchmark-chart.tsx` renders accessible, zero-based SVG comparisons with text summaries.
- `trials/trials-lab.tsx` is the responsive client boundary for preview/run/cancel/retry, mutation diff, results, divergence, trace, and exports.
- `evaluation/evaluation-session.tsx` shares actual dataset/benchmark outputs across the four existing laboratory components; `evaluation-run-console.tsx` owns durable multi-seed jobs.

## API boundary and state

`src/lib/api/client.ts` is the only module that calls `fetch`. It exposes health, demo, analysis, baselines, dataset generation, benchmark, ablation, trials, workflow/result reload, reviews/audit, exports, and job methods. Expected request errors remain component state with `aria-live` status, request ID, retry, and cancel actions. No service catch block returns a fixture in place of an API response.

## Types and deterministic data

Strict domain models live in `src/types/index.ts`. They include every required incident, evidence, candidate, workflow, review, audit, benchmark, and ablation type. No domain type uses `any`.

The deterministic synthetic sources are `src/data/mock-data.ts` and `src/data/research-data.ts`. They include fifteen fictional records across five required source classes plus a volunteer note. They cover English, Arabic, French, transliteration, estimated age, changed location, duplicate detection, close rivals, a hard conflict, insufficient evidence, translation loss, and a quarantined embedded instruction. No random value is generated on refresh.

## API adapter

`src/lib/api/client.ts` is the only place that calls `fetch`. With no `NEXT_PUBLIC_API_URL`, the service remains in synthetic demo mode. With the variable set, `analyzeRecords` calls the canonical `POST /api/v1/analyze`. A failed request returns deterministic data with an explicit fallback notice.

The canonical contract and unsupported future operations are documented in `docs/api-contract.md`.

## Environment variables

```text
NEXT_PUBLIC_API_URL=https://example.invalid
```

Leave the variable unset for the reliable no-backend demo. Do not place credentials in a `NEXT_PUBLIC_` variable; Next.js includes public variables in the browser bundle.

## Demo flow

1. Open `/` and select **Open live incident**.
2. In `/workspace`, inspect `PHONE-066` to see the quarantined embedded instruction.
3. Select `MATCH-001`, compare `FAMILY-018` with `SHELTER-204`, and open a cited source span.
4. Inspect the hypothesis, contradiction prosecutor, nearby rivals, and next verification question.
5. Select an authorized review action, add a note, and save it to the local audit trail.
6. Switch to **Workflow trace**, replay it, and open a node contract.
7. Open `/benchmark` for the clearly illustrative baseline and ablation interface.
8. Open `/methodology` for the node-by-node documentation.

The header **Restart demo** action reloads the deterministic workspace state.

## Accessibility choices

- semantic header, navigation, main, aside, section, figure, table, details, form, and dialog elements
- skip link and unique route titles
- visible focus indicators and minimum touch-sized primary controls
- native buttons for records, evidence links, tabs, and node selection
- mobile tab semantics with `aria-selected` and linked tab panels
- native modal dialogs with Escape handling and focus management
- status text and icons in addition to color
- chart titles, descriptions, legends, zero-based axes, and text summaries
- SVG relationship view paired with an equivalent list view
- original Arabic text uses language and direction attributes
- all animation is removed under `prefers-reduced-motion`
- print layout hides interaction chrome and preserves workflow-node content

## Responsive behavior

- Desktop uses a record / thread / review three-column workspace.
- Laptop and tablet collapse the review panel into an alternate central panel.
- Under 768px, Records, Reconstruction, Review, Workflow, and Audit become explicit tabs; SVG relationship and route views retain equivalent text/list alternatives.
- Comparison rows stack on mobile and wide data tables remain locally scrollable rather than causing page overflow.

## Known limitations

- No production backend, authentication, authorization, privacy enforcement, or external audit persistence exists in this repository.
- Review outcomes persist in React state for the current page session only.
- Benchmark and ablation values are illustrative interface data, not measured results.
- The prompt-injection display covers one tested synthetic case and is not a universal protection claim.
- Automated browser end-to-end tooling was not present in the repository; structural tests, server-render checks, production build, and manual browser interaction checks are used instead.

## Research-grade v2 extensions

The workspace now coordinates one `ReconstructionSelection` across the record browser, relationship factors, fictional district map, and incident timeline. A record resolves its nearest known event and location; an event or location resolves a relevant source record. `WorkspaceShell` owns that shared state, so the three layers do not maintain competing selections.

Desktop retains the existing record / center / review shell. The center can switch among reconstruction, evidence reasoning, workflow, and audit. Mobile uses five tabs: Records, Reconstruction, Review, Workflow, and Audit. The fictional map uses keyboard-operable external controls and a persistent text alternative; relationship and route visuals have list fallbacks.

The workflow explorer now joins the existing `WorkflowNode` contract to `WorkflowNodeTrace`. Its inspector tabs are Overview, Input, Prompt, Output, Validation, Evidence, and Diff. Duration, tokens, and estimated cost are nullable and display `Synthetic trace` unless measured backend metadata exists.

The benchmark route contains four connected laboratories:

- Dataset lab: deterministic, fixed-seed local generation and JSON export.
- Baseline arena: case-aligned inspection across four systems and an expected-behaviour matrix.
- Ablation lab: node toggles, complete-workflow comparison, metric definitions, and case drill-down.
- Error workbench: five-dimensional filtering and first-divergence inspection.

The print-only `/workspace/packet` route derives from the same records, candidate, reconstruction, and audit fixtures. It uses CSS print rules without a PDF dependency.

## V2 source boundaries

- Synthetic fixtures live in `src/data/mock-data.ts` and `src/data/research-data.ts`.
- Fixed-seed generation is pure and browser-local in `src/lib/benchmark/generator.ts`; it never calls an LLM.
- Network access remains centralized in `src/lib/api/client.ts`.
- `Synthetic example output`, `Synthetic trace`, and `Illustrative values — awaiting backend evaluation` are explicit UI states.
- `Actual backend output` is reserved for a configured backend response.
- Original evidence remains immutable. Translation and normalization add attributed representations without replacing source text.
