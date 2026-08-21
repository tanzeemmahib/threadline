# THREADLINE four-minute judge demo

> **Superseded recording script:** use [`../reverie-demo-script.md`](../reverie-demo-script.md) for the current six-beat, under-three-minute Reverie narrative. This document is retained only as a detailed reference for the earlier eight-scene flow.

Target duration: `3:45-3:55`  
Legacy route: `http://127.0.0.1:3000/demo?workspace=1&demo=guided`
Case: `CASE-CYCLONE-ILYRA-001` - fictional identities and locations

## Before recording

1. Start the deterministic local demo. No API key or network is required.
2. Open the legacy route above directly in a fresh browser window at 1440 x 900 or larger. The primary landing page now opens the current six-scene Reverie case instead.
3. Confirm the page labels the run **Deterministic mock replay - not model performance**.
4. Confirm the controls are visible: **Open source**, **View technical evidence**, **Back**, **Next**, **Reset**, and **Exit guided case**.
5. Press **Reset**, then **Start evidence challenge**.
6. Keep zoom at 100%, system audio off, and the pointer away from evidence text until needed.

## Spoken script and actions

### 0:00-0:15 - Landing and scope

**Action:** Open the legacy workspace-tour route above directly and select **Start evidence challenge**. The current landing CTA does not open this historical flow.

**Say:**

> THREADLINE is an experimental safety and review layer for proposed record connections. It preserves exact provenance, challenges each hypothesis with contradictions and rivals, and withholds what the evidence cannot safely support. Every identity and location in this demonstration is fictional.

### 0:15-0:40 - 01 Fragmented records

**Action:** Select **Start evidence challenge** if the guided case is not already active. Keep the family report and shelter intake visible.

**Say:**

> These records have compatible name forms and an emergency contact, but both are incomplete. The question is deliberately simple: do they refer to the same person? THREADLINE does not answer from resemblance alone.

**Judge should see:** `FAMILY-042`, `SHELTER-118`, compatible fragments, and the question **Do these records refer to the same person?**

### 0:40-1:10 - 02 Single-prompt baseline

**Action:** Select **Next**.

**Say:**

> First, a reasonable single-prompt baseline sees the same case evidence. The offline judge path is a deterministic replay, not a claim about live model performance. It returns a plausible possible-candidate answer, but no exact citations, no contradiction, and no rival comparison. That is the failure mode: a reasonable answer can still outrun its evidence.

**Judge should see:** prompt ID `generic_baseline/1`, provider mode `mock`, possible-candidate output, zero citations, and the replay limitation.

### 1:10-1:40 - 03 Evidence extraction

**Action:** Select **Next**, then select **Open source** on the name claim.

**Say:**

> THREADLINE separates extraction from decision policy. Each claim keeps the original source, exact quotation and offsets, normalized value, evidence category, source-independence status, and extraction uncertainty. Normalization adds a comparison form; it never overwrites the source.

**Action:** Close the source view with its close control or `Escape`. Select **View technical evidence** briefly, then return.

**Judge should see:** `Amira Saleh`, `Ameera Salih`, their original spans, and `Independent source status: Not established`.

### 1:40-2:15 - 04 Contradiction challenge

**Action:** Select **Next**. Keep both conflict rows visible.

**Say:**

> The independent challenge separates a soft birth-date conflict from a material timeline conflict. A family relay places the leading thread at Narin Quay at 18:20; direct shelter intake places it at Hillcrest School at 18:40. No validated transport or custody record resolves that movement. The interruption shape, label, and text carry the state - not color alone.

**Action:** Open one location source span if time permits, then close it.

### 2:15-2:40 - 05 Rival candidate

**Action:** Select **Next**.

**Say:**

> A second candidate remains plausible. `AID-209` shares a birth date, contact, and compatible name form, but the contact was copied and its own location evidence conflicts. Testing only the leading candidate would manufacture certainty. THREADLINE keeps the rival visible and separately scoped.

### 2:40-3:10 - 06 Evidence contract

**Action:** Select **Next**. Pause on the decisive contract line.

**Say:**

> The release boundary is deterministic. Source-span integrity, lineage, certainty, and rival coverage pass. The timeline gap warns. Material contradictions fail. The result is not a weak match score. It is an explicit boundary: release withheld because the location conflict remains unresolved.

**Judge should see:** **Release withheld: material location conflict remains unresolved.**

### 3:10-3:28 - 07 Human review

**Action:** Select **Next**.

**Say:**

> THREADLINE now hands an evidence packet to authorized human review. The reviewer receives the exact unresolved question and permitted next steps. The system does not confirm identity, declare someone found, or merge records.

### 3:28-3:52 - 08 Measured comparison

**Action:** Select **Next**.

**Say:**

> On this judge case, the replayed baseline returned an answer without a cited contradiction or rival; THREADLINE preserved both and withheld release. Separate saved evidence reports four of four different-identity V1 holdout cases withheld, and zero false merges among eight evaluated different-identity pairs in one archived live-provider V2 extraction run. Those denominators are small, every result is synthetic, and neither result establishes field safety.

> The baseline produced an answer. THREADLINE produced an auditable boundary around what the evidence can support.

**Action:** Select **Finish evidence challenge**.

## Operator controls

- **Back** revisits the prior scene without losing case state.
- **Next** advances one scene only.
- **Reset** returns to the inactive launcher and clears guided focus state.
- **Open source** reveals the exact original quotation and offsets.
- **View technical evidence** opens the deeper evidence view.
- **Exit guided case** returns to the normal workspace.
- `Escape` closes an open evidence disclosure and restores focus.

The route must remain fully usable with keyboard navigation. The evidence state cannot depend on hover.

## Reduced-motion recording

With `prefers-reduced-motion: reduce`, long traces, magnetic behavior, and travel-heavy transitions are removed. State changes remain visible through text, shape, and immediate focus movement. Record a five-second appendix showing scene navigation in reduced-motion mode if the submission format permits.

## Recording checklist

- [ ] Synthetic scope statement visible in the first 15 seconds
- [ ] Guided case completes in under four minutes
- [ ] Same record IDs visible in baseline and THREADLINE scenes
- [ ] Baseline replay limitation spoken and visible
- [ ] Exact source span opened
- [ ] Soft and hard conflicts distinguished without color alone
- [ ] Rival `AID-209` visible
- [ ] Decisive withheld sentence readable at normal video size
- [ ] Human-review handoff shown without a success celebration
- [ ] Measured counts include denominators and synthetic limitations
- [ ] No API credential or network dependency
- [ ] No console, loading, or route error captured
- [ ] Final frame holds for at least two seconds
