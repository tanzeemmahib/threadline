# THREADLINE — three-minute Reverie demo script

Target: `2:35–2:50`  
Primary route: `http://127.0.0.1:3000/demo?demo=guided`  
Technical deep dive: `http://127.0.0.1:3000/prompt-lab`  
Case: `INCIDENT-V1-RIVAL` — fictional synthetic records only

## Before recording

1. From the repository root, run `./scripts/run-v1-demo.ps1` with no model API key.
2. Open a fresh 1440 × 900 browser window at 100% zoom.
3. Confirm the landing page says **Synthetic research demonstration. No identity is autonomously confirmed.**
4. Open **Run the evidence case** and select **Reset** once.
5. Confirm keyboard focus, direct scene selection, **Back**, **Next evidence**, **Reset**, source-span controls, and **Compare the prompts** work.
6. Keep the pointer outside the evidence area until the relevant action.

## Script

### 0:00–0:16 — Position the problem

**Visible action:** Start on `/`. Select **Run the evidence case**.

**Say:**

> Three organizations hold three incomplete records about one possible person — and one dangerously similar rival. THREADLINE asks what the evidence can support without allowing similarity to become identity.

**Judge should see:** three synthetic source fragments; the question is human, not architectural.

### 0:16–0:40 — Scene 1: Human stakes

**Visible action:** Pause on the first guided scene. Keep `FAMILY-018`, `SHELTER-204`, and `HOSPITAL-052` visible.

**Say:**

> The family and shelter summaries both describe Youssef Al Hassan, age fourteen. The hospital summary looks plausible by name, but reports a document-backed age of twenty-four. Nothing here is an identity conclusion.

**Judge should see:** three concise record summaries with distinct source-type and record-ID labels. Exact original text is intentionally deferred to the source-span dialog in Scene 3.

### 0:40–1:03 — Scene 2: one-shot baseline

**Visible action:** Select **Next evidence**. Expand the prompt/configuration once.

**Say:**

> First, a reasonable one-shot baseline receives the exact same record packet. This offline result is a deterministic replay, not live-model performance. It returns a plausible family-to-shelter candidate, but supplies no exact citation, no contradiction, and no rival analysis. An answer can sound careful and still outrun its evidence.

**Judge should see:** `generic_baseline/v1`, deterministic-fixture model, temperature `0`, same input hash, `possible_candidate`, and zero citations.

### 1:03–1:35 — Scene 3: Source-cited extraction

**Visible action:** Select **Next evidence**, then open one evidence span.

**Say:**

> THREADLINE decomposes the work. Prompt V2 extracts typed fields, but every displayed evidence link resolves to an exact quote and offset. Original wording remains intact. Deterministic representations appear beside source values for comparison; they never overwrite evidence and never decide identity.

**Visible action:** Close the source view with `Escape`.

**Judge should see:** the original-source → structured-field → deterministic-representation legend, paired source values, factor interpretation, source-span IDs, and a dialog with the record ID, exact quote, offsets, and substring-validation state. This scene does not display extraction uncertainty or evidence-category labels.

### 1:35–1:58 — Scene 4: Supported thread

**Visible action:** Select **Next evidence**.

**Say:**

> Deterministic comparison reconstructs a possible connection between the family and shelter records. Name similarity is supporting evidence only; age compatibility and distinguishing marks remain individually traceable. Missing evidence is never counted as agreement. This packet is eligible only for authorized human review.

**Judge should see:** `FAMILY-018 ↔ SHELTER-204`, a supported possible connection, and a review-only state — never “confirmed” or “found.”

### 1:58–2:22 — Scene 5: Conflict gate

**Visible action:** Select **Next evidence** and open the age conflict source if one click is available.

**Say:**

> Now the rival. The shared name is initially convincing, but direct source evidence says age fourteen in the family and shelter records and documented age twenty-four from an identity card in the hospital record. The deterministic gate blocks candidate pairs involving the rival under timeline consistency and material-contradiction rules. The model cannot override this state.

**Judge should see:** **BLOCKED — deterministic identity conflict**, policy identifiers, conflicting fields, exact source spans, and an interrupted—not successful—connection.

### 2:22–2:47 — Scene 6: Measured proof

**Visible action:** Select **Next evidence**. Pause on the final statement.

**Say:**

> The valid candidate remains a traceable packet for authorized review, while the rival remains blocked. The final ledger pins both outcomes to the same-input hash, available-evidence hash, and evidence-contract identifiers. In one archived Prompt V2 run, THREADLINE recorded zero false merges across eight evaluated different-identity opportunities and four link-recommended candidate pairs; those synthetic denominators are small, not a field-safety claim.

> One connection recovered. One false merge prevented. Every decision traceable.

**Judge should see:** possible connection for review, blocked rival, input/evidence hashes, contract identifiers, explicit synthetic limitation, and the final thesis. This locked story does not display or claim a replay certificate or export artifact; both are recorded as **Not recorded**. “Connection recovered” means a candidate connection reconstructed from records — not a person identified.

### 2:47–2:58 — Optional ML-track proof

**Visible action:** Select **Compare the prompts** or open `/prompt-lab` in the prepared tab.

**Say:**

> Prompt Lab exposes identical inputs, full prompt versions, raw and validated outputs, exact spans, deterministic decisions, and the V1-to-V3 promotion evidence. It shows why Prompt V3 was not promoted: higher recall came with a major precision regression.

Stop here. Do not tour unrelated administration screens.

## Offline backup

If the connected provider is unavailable, do **not** improvise a live run.

1. Keep the default `LLM_PROVIDER=mock`; no API credential is needed.
2. Run `./scripts/run-v1-demo.ps1`.
3. Use `/demo?demo=guided`; confirm the masthead identifies **Deterministic synthetic replay** and Scene 2 warns **Deterministic mock replay — not model performance**.
4. If the frontend was already built, use the printed production URL. If not, run the script again and wait for its readiness checks.
5. Use `/prompt-lab` for saved prompt artifacts. Never describe a recorded provider artifact as a live call.

## Keyboard-only path

1. `Tab` to **Run the evidence case** and press `Enter`.
2. Use `Tab` / `Shift+Tab` and `Enter` or `Space` for scene controls.
3. Open a source span, then press `Escape` to close it and restore focus.
4. Use **Back**, **Next**, and **Reset** without pointer input.
5. On the final scene, open **Compare the prompts** and return with browser back navigation.

## Reduced-motion path

With `prefers-reduced-motion: reduce`, travel-heavy traces and magnetic interactions are removed. State changes remain immediate and readable through text, shape, line interruption, and focus. The script and timing do not depend on animation.

## Recording gate

- [ ] Opens with human stakes before architecture or metrics
- [ ] Synthetic scope is visible and spoken
- [ ] Baseline and workflow show the same record IDs and input hash
- [ ] Baseline is labelled deterministic replay, not model performance
- [ ] An exact source span opens in one action
- [ ] A supported possible connection reaches authorized review only
- [ ] `HOSPITAL-052` is visibly blocked by deterministic conflict
- [ ] No screen says identity confirmed, person found, or records autonomously merged
- [ ] V2/V3 precision tradeoff is stated with exact values or omitted
- [ ] Final statement holds for at least two seconds
- [ ] Total runtime is under three minutes
