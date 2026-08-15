# THREADLINE premium product implementation plan

## Outcome

Upgrade the existing Next.js/FastAPI prototype in place. Preserve the evidence model, API adapter, deterministic fixtures, release gate, routes, and testable architecture. Add a premium, keyboard-operable investigation experience whose central interaction travels from a reviewer-facing candidate claim back to the exact immutable source span.

## Product boundary

THREADLINE reconnects fragmented fictional humanitarian records for authorized review. It never confirms identity. Every visible decision state must preserve uncertainty, rival explanations, contradictions, and source provenance. The governing principle is **PROOF BEFORE RELEASE**.

Approved terms: Candidate thread, Supporting evidence, Contradiction, Unresolved gap, Source span, Evidence contract, Authorized review, Timeline compatibility, Rival explanation, Audit event, Release gate.

Forbidden terms: AI Match Confirmed, Identity Confirmed, Person Found, Guaranteed Match, Autonomous Verification.

## Workstreams

### 1. Global product shell

- Adopt exact THREADLINE colors and Manrope/IBM Plex Mono-compatible local font stacks without remote font fetching.
- Refine the header into a restrained operational masthead with synthetic-data and proof-before-release context.
- Establish consistent button, field, focus, hover, pressed, loading, disabled, success, warning, and failure states.
- Preserve print mode, skip navigation, reduced motion, and 320px minimum support.

### 2. Landing experience

- Replace the current headline and copy with the approved hero content.
- Build a deterministic evidence field: selected synthetic nodes, one authored cyan route, focus/hover previews, pointer parallax bounded to a few pixels, and a mobile/reduced-motion static composition.
- Make the primary action enter the guided synthetic case and the secondary action deep-link to the evidence contract.
- Add compact sections explaining exact-span traceability, rival explanations, release-gate states, and authorized review.

### 3. Case navigator and workspace shell

- Add a synthetic case navigator for passing, blocked-contradiction, and review-required states while preserving backend-run loading by URL.
- Retain the three-column desktop layout and explicit mobile panels.
- Add a visible guided-demo controller with step count, next/back, escape, and screen-reader announcements.

### 4. Evidence graph and comparison

- Convert the record/factor graph into real keyboard buttons linked by semantic SVG edges.
- Map cyan to support, amber to unresolved contradiction, coral to blocked/invalid, and muted to weak/incomplete.
- Selecting an edge opens its exact source evidence; selecting a claim highlights connected records; selecting a contradiction opens paired sources.
- Keep a text/list equivalent adjacent to the graph.

### 5. Signature evidence lineage

- Implement four real selectable layers: Candidate claim → normalized claim → extracted evidence → exact original source span.
- Use existing `EvidenceClaim`, parent claim IDs, source-span citations, extracted fields, normalized values, and immutable record offsets.
- Announce layer changes, expose forward/back controls, preserve current claim selection, and open the exact highlighted original text at the final layer.

### 6. Timeline, contradictions, and rivals

- Keep synchronized record/map/timeline selection and improve hierarchy/legend legibility.
- Add a contradiction workspace with two source panels, quotes, offsets, certainty, and reviewer notes.
- Make rival explanations persist as named alternatives rather than collapse into a single score.

### 7. Evidence contract and release gate

- Add a deterministic UI state machine for `Run Evidence Contract`, `Validating Evidence…`, `Resolve Contract Violations`, and `Send to Authorized Review`.
- Never manufacture a backend result; the fixture-mode interaction replays existing contract findings and labels itself as a synthetic demonstration.
- Gate decision actions on contract state. Blocking violations expose remediation and exact source spans; review-required results retain uncertainty.

### 8. Authorized review, audit, and decision state

- Preserve the native review dialog and backend persistence.
- Rename the primary completion action to `Record Authorized Decision`.
- Add an explicit final state showing released-for-review, withheld, or additional-evidence-required; never an identity confirmation.
- Keep replay, counterfactual, export, and audit-chain controls connected to the existing API client.

### 9. Verification

- Extend structural tests for approved/forbidden language, lineage layers, interactive graph semantics, contract button states, guided demo, and mobile/reduced-motion CSS.
- Run lint, strict typecheck, frontend tests/build, Ruff, format check, mypy, pytest, and integration smoke.
- Perform local rendered desktop/mobile inspection and keyboard smoke testing without deploying.

## Completion gates

1. No forbidden product language in reviewer-facing source or fixture output.
2. Every important control performs a real state change, navigation, dialog, API operation, or documented synthetic replay.
3. Every graph interaction has keyboard access and a text alternative.
4. Exact source text is derived with declared offsets; no decorative fake excerpt.
5. Reduced motion removes parallax, path drawing, pulsing, and guided auto-advance.
6. Mobile has a purposeful static hero and full workspace parity through tabs.
7. No paid generation, upload, deployment, or publish operation occurs without authorization.
