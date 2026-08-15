# THREADLINE evidence contracts

THREADLINE does not release a candidate decision unless its evidence contract passes. The contract is a deterministic, post-routing release gate over the existing workflow output; it does not add an identity decision or a model judgment.

## V1 contract

Each analyzed candidate receives an `EvidenceContract`. `POST /api/v1/analyze` returns the primary `evidence_contract`, all candidate-scoped `evidence_contracts`, and an aggregate `contract_release_status`. `GET /api/v1/contracts/{contract_id}` reloads the durable contract from SQLite.

The claim ledger includes extracted facts, additive normalized representations, deterministic timeline interpretations, compatibility claims, contradictions, and rival comparisons. Cited `source_spans` carry the immutable record ID, quote, exact half-open character offsets, and certainty label. The `certainty_basis` maps every cited span to the certainty used by the claim.

The granular verifier retains the EC diagnostic rules without an LLM:

- `EC-001` checks that each cited quote is identical to the immutable source text at its declared offsets and blocks unsupported claims.
- `EC-006` requires claim certainty to equal the cited span certainty.
- `EC-007` requires every hard-conflict ID from the contradiction stage in both the contract and review-router input.
- `EC-008` requires close-rival analysis before a strong review classification can pass.
- `EC-011` rejects configured prohibited autonomous-outcome language in reviewer-facing output.
- `EC-018` requires the exact candidate-review safety notice.

Any blocking violation sets the contract to `blocked`, clears the contract classification, clears the corresponding candidate classification fields, and changes the candidate label to `Output withheld`. Review-required outputs also omit candidate classifications. The closed `release_state` union can represent only draft, evaluating, blocked, authorized-review-required, review-in-progress, or human-disposition-recorded states. The blocked UI keeps structured authorized-review actions available; it never exposes an autonomous decision.

V1 preserves those IDs and adds deterministic EC-002 through EC-005, EC-009 through EC-010, and EC-012 through EC-017 for source ownership, provenance, lineage, normalization support, workflow completeness, quarantine boundaries, classification/abstention consistency, audit/replay integrity, source diversity, and decision-critical analysis. Every rule emits a typed result, operator explanation, affected claim/span IDs, and remediation. EC-016 and EC-017 are review-required; blocking findings fail closed.

## Canonical ten-rule contract

Operator-facing results aggregate the granular findings into exactly ten versioned rules: `SOURCE_SPAN_INTEGRITY`, `CLAIM_LINEAGE_COMPLETE`, `CERTAINTY_PRESERVED`, `TIMELINE_CONSISTENCY`, `MATERIAL_CONTRADICTIONS_RESOLVED`, `RIVAL_EXPLANATION_COVERAGE`, `REQUIRED_SAFETY_NOTICE_PRESENT`, `HUMAN_REVIEW_ROUTING_VALID`, `AUDIT_EVENT_READY`, and `RELEASE_AUTHORIZATION_VALID`. Each result includes pass/warn/fail/block status, a stable reason code, input artifact IDs, related source-span IDs, evaluation timestamp, and evaluator version.

Each source span carries its document ID, offsets, exact quotation, content hash, language, validation state, and creation metadata. Each derived claim carries parent IDs, transformation history, certainty category, candidate/case scope, and the contract rules that consume it. Candidate-scoped ledgers prevent one candidate's evidence from silently counting for another.

## Standalone demo

Start the backend and frontend using the repository scripts, then open `/demo`. The deterministic Cyclone Ilyra case produces a blocked contract from a real location contradiction, clickable exact spans, a credible rival, a 34-hour missing interval, structured authorized disposition, and append-only audit verification. No external service or paid generation is required.

For the fail-closed smoke test, copy the canonical request, append one configured prohibited token to a synthetic record, and submit it to `POST /api/v1/analyze`. The response returns `contract_release_status: withheld`, a blocked contract with `EC-011`, and `null` candidate classification fields. Reload the certificate with its contract ID, or open `/workspace?run={workflow_run_id}` to render that exact persisted run in the candidate panel. The automated integration test `test_blocked_contract_withholds_classification_in_api` executes this mutation without changing repository fixtures.

`audit_chain_status` now contains the release-time typed integrity snapshot. Actual counterfactual results populate `decision_critical_evidence`; no span is labeled critical without a real derived-workflow replay.

THREADLINE proposes candidate record connections for authorized human review and does not autonomously determine identity.
