# THREADLINE — Reverie Hacks judge Q&A

Answers are designed for a live three-minute demo. Every claim below is bounded by the saved synthetic artifacts.

## What does THREADLINE do?

THREADLINE is an experimental safety and review layer for possible connections between fragmented synthetic missing-person records. It converts untrusted narrative records into exact source-cited evidence, compares candidate records deterministically, challenges each hypothesis with contradictions and rivals, and withholds any output that is not safe to place before an authorized human reviewer.

## Why is this prompt engineering rather than ordinary software?

The research variable is how multiple constrained prompt operations change what can be audited and released. Extraction, multilingual normalization, support construction, contradiction challenge, and adjudication each have a narrow purpose, a versioned template, a typed output schema, and a deterministic validation boundary. Prompt V3 is not promoted even though it completed every extraction, because its false-positive fields caused precision and F1 to fall. The software exists to make those prompt choices testable and safe.

## Why not use one strong prompt?

A one-call prompt must extract, normalize, compare, challenge, rank rivals, and decide at once. That makes unsupported claims and omitted opposition hard to isolate. THREADLINE separates these responsibilities, validates exact spans before later use, and prevents any model output from overriding deterministic conflicts. The repository does not claim a live same-model one-shot quality win; the available one-shot comparison is a deterministic workflow replay labelled **not model performance**.

## What prevents hallucinations?

No single mechanism can prevent all hallucinations. THREADLINE reduces their effect by requiring schema-constrained output, canonical field keys, exact quoted spans and offsets, original-text preservation, one bounded repair attempt, and fail-closed handling. Unsupported extracted fields are removed or marked missing before they can support a proposal. The archived V2 run still contained 30 false-positive fields, which is why deterministic validation and human review remain essential.

## Who makes the identity decision?

No model and no THREADLINE policy confirms identity. Deterministic policy decides only whether evidence is safe to prepare as a **possible connection** for authorized review or must be withheld. An authorized human, operating under an organization's governance, would make any real disposition. This prototype does not implement production identity authority.

## What happens when evidence conflicts?

The field comparator emits typed conflicts, the contradiction prompt searches for opposing evidence independently, and deterministic policy restores any material blocker the model omits. In the judge case, age 14 in `FAMILY-018`/`SHELTER-204` conflicts with an identity-card-supported age 24 in rival `HOSPITAL-052`. `TIMELINE_CONSISTENCY` and `MATERIAL_CONTRADICTIONS_RESOLVED` block rival candidate release. The LLM cannot override that result.

## What does “one connection recovered” mean?

It means one cross-record **candidate connection** is reconstructed with traceable support and becomes eligible only for authorized human review. It does not mean a person is identified, confirmed, found, or merged automatically. The closing line is shorthand for the review artifact, not a factual identity determination.

## Why is the data synthetic?

Missing-person data is highly sensitive and operational use requires consent, lawful authority, data minimization, security controls, and organizational governance that a hackathon prototype cannot provide. Synthetic fixtures allow deterministic ground truth, controlled contradictions, prompt-injection cases, exact replay, and public inspection without exposing real people. The tradeoff is that the results do not establish operational accuracy or fairness.

## What do zero false merges actually prove?

Only that no false merge was observed in the stated synthetic denominator. The archived V2 run recorded `0/8` evaluated different-identity opportunities and the deterministic 21-case workflow replay recorded `0/8` false-link cases. These are small synthetic sets, not proof of real-world safety. The UI and documents show the denominator and retain false non-links rather than converting this into a broad “100% safe” claim.

## Why was Prompt V3 rejected?

On the same full 58-record fixture and model configuration as V2, V3 improved extraction success from `57/58` to `58/58` and recall from `0.8626` to `0.8846`. But false-positive fields rose from `30` to `78`, precision fell from `0.8396` to `0.6736`, and F1 fell from `0.8509` to `0.7648`. For evidence work, completing every record is not a win if more unsupported fields enter the system. V2 remains production.

## What changed from Prompt V1 to V2?

On their shared targeted 19-record cohort, V2 improved TP/FP/FN from `56/4/9` to `58/2/7`, precision from `0.9333` to `0.9667`, recall from `0.8615` to `0.8923`, and F1 from `0.8960` to `0.9280`. V2 made completeness, multilingual preservation, OCR tolerance, partial values, and distinguishing marks explicit while retaining exact-source fidelity and canonical keys.

## How are one-shot and workflow inputs kept identical?

The deterministic judge artifact records record IDs, per-record text hashes, an input hash, and a complete available-evidence hash per system. For `INCIDENT-V1-RIVAL`, the generic baseline, structured baseline, and full workflow all use input SHA-256 `bc8084e71ab87554163279a3b61d27d1b71f0c06fb3347c4555de5670ab83576` and available-evidence SHA-256 `68c34760bc4c0f0f6e18f0aeb40d1ddf5243656efcc75b7034dbe0d73223ff20`.

## How would this scale?

The architecture separates inexpensive deterministic steps from bounded model calls: normalize once, retrieve top-k candidates, then reason only over bounded evidence packets. Versioned artifacts and prompt hashes support regression testing before promotion. Actual scale claims are not measured here; production work would need load tests, provider budgets, cache policy, queueing, reviewer-capacity modeling, and incident-specific governance.

## How could an NGO deploy it safely?

Not directly from this repository. A responsible deployment would require threat modeling with the organization, lawful authority and consent, data minimization, regional data handling, access control, encryption, retention/deletion automation, provider agreements, reviewer training, escalation and appeal processes, representative evaluation, subgroup analysis, audit anchoring, and independent security review. THREADLINE demonstrates a workflow pattern, not operational readiness.

## What are the largest remaining limitations?

Synthetic-only data; small negative denominators; one archived live run per full prompt version; no live same-model one-shot versus workflow experiment; no confidence intervals; weak location/distinguishing-mark precision; selected ablations with no measured primary effect; and missing production security, privacy, governance, fairness, and connected-replay controls.

## What is the innovation?

THREADLINE does not claim to invent digital missing-person matching. Its narrower contribution is the combination of exact claim-to-source lineage, separate adversarial challenge, rival retention, prompt-injection quarantine, deterministic release rules around probabilistic stages, replay and source-removal counterfactuals, and a promotion policy that rejects a more complete prompt when precision regresses.

## Why should this score well on the ML Prompt Engineering track?

The product exposes the prompt workflow, each model query's purpose, versioned prompts and hashes, typed outputs, validation boundaries, same-input comparison artifacts, real prompt-iteration results, and failure analysis. The visible story is not “AI found a person.” It is: a prompt workflow made the evidence auditable, reconstructed one reviewable candidate connection, and prevented one plausible false merge from crossing a deterministic safety gate.

