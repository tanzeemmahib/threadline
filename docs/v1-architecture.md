# THREADLINE V1 architecture

THREADLINE V1 is a proof-carrying decision-support pipeline. It proposes candidate record connections for authorized human review and does not autonomously determine identity.

## Decision lifecycle

```text
Synthetic case package
  -> 12 protected workflow nodes
  -> exact evidence spans + structured candidates
  -> claim ledger and transformation lineage
  -> 18 deterministic evidence-contract rules
  -> tamper-evident audit verification
  -> released candidate packet OR classification-withheld packet
  -> replay and counterfactual certificates
```

The node order and scoring formulas are unchanged. Integrity services are additive and execute after human-review routing. The API persists the original request, response, contracts, replay manifest, legacy audit rows, and authoritative hash-chain rows in one SQLite transaction.

## Evidence-contract lifecycle

Each candidate receives a ledger of extracted, normalized, timeline, compatibility, contradiction, and rival claims. Claims carry exact source spans, parent claim IDs, transformation and prompt/model versions when applicable, creation metadata, and a canonical claim hash. The 18-rule registry returns a typed result for every rule. Blocking findings withhold the classification. Review-required findings preserve an allowed classification but prevent a clean-pass presentation.

## Canonical JSON and audit envelope

Canonical JSON uses UTF-8, recursively sorted object keys, stable input array order, compact separators, explicit nulls, lowercase booleans, timezone-required UTC datetimes rendered with six fractional digits and `Z`, finite JSON floats with negative zero normalized, and exact `Decimal` values rendered as normalized strings. NaN and infinity are rejected.

`payload_hash = SHA-256(canonical_json(payload))`.

`event_hash = SHA-256(canonical_json(envelope))`, where the envelope contains exactly:

```json
{
  "event_id": "CHAIN-...",
  "workflow_run_id": "...",
  "contract_id": null,
  "candidate_id": null,
  "case_id": "CASE-...",
  "referenced_artifact_ids": [],
  "workflow_version": "threadline-workflow/2.0.0",
  "sequence_number": 1,
  "event_type": "workflow_run_created",
  "actor_type": "system",
  "actor_id": null,
  "created_at": "2026-04-18T22:00:20.000000Z",
  "payload_hash": "...",
  "previous_event_hash": "...",
  "schema_version": "threadline-audit-event/1.1.0",
  "hash_algorithm": "sha256"
}
```

The event ID is deterministically derived from the envelope without its `event_id` field; the final event hash then covers the derived ID and every field shown above. The first event references `SHA-256("THREADLINE_AUDIT_GENESIS_V1")`. Sequence numbers are unique and continuous per run. SQLite serialization plus a unique `(workflow_run_id, sequence_number)` constraint prevents application-level forks. The verifier reports broken, incomplete, unsupported-schema, and verifier-error states with the first invalid sequence and expected/observed hashes. This provides tamper evidence for the chained event metadata and payloads, not tamper prevention or a cryptographic seal over the current contract/result rows.

## Replay lifecycle

The manifest hashes the original request, normalized records, configuration, ordered nodes, each node input/output, candidates, ranking, contracts, response, and release-time audit terminal. Mock-provider replay reruns the real workflow and compares checkpoints in order. Connected-provider replay fails closed as unsupported because frozen structured-output injection is not yet implemented; it does not silently call a newer model.

## Counterfactual lifecycle

Counterfactuals derive an immutable request, remove or weaken selected evidence, rerun the real workflow, and compare candidate identity, classification, rank, score, contract rules, routing, and release state. Supported mutations cover one span, one source, compatibility/conflict/rival claims, certainty reduction, and source unavailability. Certificates state the first responsible node and apply only to the tested configuration.

## SQLite additions

- Existing `artifacts` and legacy `audit_events` remain readable.
- `audit_chain_events` is additive, append-only through the repository API, and unique by run sequence.
- Original inputs, manifests, replay certificates, counterfactual certificates, evidence contracts, workflow runs, and results use versioned artifact collections.
- No destructive migration or field rename is required.

## API routes

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/api/v1/analyze` | Run and atomically persist a release-gated analysis |
| GET | `/api/v1/runs/{run}/audit` | Typed authoritative chain plus integrity result |
| GET | `/api/v1/runs/{run}/audit/verify` | Reverify persisted chain |
| POST | `/api/v1/runs/{run}/replay` | Create deterministic replay certificate |
| GET | `/api/v1/replays/{id}` | Reload replay certificate |
| POST | `/api/v1/runs/{run}/counterfactuals` | Run evidence ablation |
| GET | `/api/v1/counterfactuals/{id}` | Reload counterfactual certificate |
| GET | `/api/v1/contracts/{id}` | Reload evidence contract |
| POST | `/api/v1/runs/{run}/contracts/{id}/export` | Export JSON and append audit event |
| POST | `/api/v1/case-packages/ingest` | Canonicalize a synthetic package and ingestion hashes |
| GET | `/api/v1/demo/v1/{scenario}` | Load a real-pipeline V1 scenario |

## Limitations

Authentication, authorization, encryption at rest, retention, multi-host coordination, signed external timestamps, and field validation remain deployment work. SQLite protects transactional ordering inside one application instance; an administrator can still modify the database offline, which verification is designed to detect. Exact replay is currently limited to deterministic mock runs. The benchmark is synthetic and preliminary.
