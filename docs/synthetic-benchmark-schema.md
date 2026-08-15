# Synthetic benchmark schema

The backend generator is deterministic, fixed-seed, and synthetic-only. It uses no LLM and never uses real identities.

## Configuration

```json
{
  "seed": 41027,
  "identities": 12,
  "records_per_identity": 3,
  "languages": ["English", "Arabic", "French"],
  "transliteration_severity": 35,
  "spelling_corruption": 12,
  "missing_field_percentage": 24,
  "estimated_age_variance": 2,
  "changed_location_frequency": 30,
  "duplicate_record_frequency": 8,
  "contradictory_timestamp_frequency": 10,
  "rival_candidate_count": 2,
  "prompt_injection_frequency": 5,
  "common_name_frequency": 18
}
```

Frequency/severity fields are integer percentages from 0 to 100. `seed` is required, at least two identities and two records per identity are required, and the configured maximum is 500 identities.

## Dataset

`POST /api/v1/benchmark/generate` returns configuration, fictional identity truth, fragmented `RecordInput`-compatible records, separate ground-truth cases, a SHA-256 `content_hash`, and `synthetic_only: true`. The same validated configuration serializes to the same identity/record/case order and hash.

Every ground-truth case contains case and record IDs, fictional identity IDs, `same_identity`, `different_identity`, or `genuinely_ambiguous` relation, expected allowed classification, ambiguity status, difficulty/corruption/language tags, and expected evidence fields. Ground truth is never copied into an analysis request or model prompt.

With at least two configured rivals, the generator includes a complete abstention case with a common name, broad estimated age, missing location, no distinctive feature, and equally plausible rivals. The canonical fixtures always contain the required two-rival case. Its expected classification is `insufficient_evidence`.

## Multi-seed result envelope

The default seeds are `104, 205, 306, 407, 508`. Every aggregate includes per-metric mean, population standard deviation, min/max, and a fixed-seed bootstrap 95% interval, plus successful/failed runs, total cases, provider/model, actual calls, and duration. A benchmark-suite result also stores risk–coverage points and the full/adaptive router comparison. See the [THREADBENCH data card](threadbench-data-card.md).

The frontend generator remains an illustrative browser fixture. Backend evaluation results are distinct artifacts and are labelled `Deterministic mock evaluation` or `Real-provider evaluation`.

## Canonical latent identity ground truth (Phase 10S, schema v3)

### Four independent concepts

The benchmark separates four concepts that earlier schemas conflated. They are stored and evaluated independently, and nothing downstream may collapse them:

1. **Latent identity truth** — whether two fictional records depict the same fictional person. Grounded *exclusively* in per-record canonical `fictional_identity_id` equality. Allowed values under v3: `same_identity`, `different_identity`, or `canonical_identity_under_specified` (the fixture does not authorially establish the identity — this is a stop-condition state, never a guess).
2. **Evidence disposition** — what the observable record evidence justifies: `supports_same_identity`, `supports_different_identity`, `genuinely_ambiguous`, `insufficient_evidence`. This is *not* identity truth: a pair can legitimately be `latent_identity_truth = different_identity` with `evidence_disposition = genuinely_ambiguous`.
3. **Expected candidate** — whether retrieval/blocking should surface the pair. It never influences identity truth.
4. **Workflow expectation** — the safe resolver action (`link_recommended`, `human_review_required`, `blocked_by_conflict`, `insufficient_evidence`, …). Kept distinct from identity truth.

### v3 identity fixture

The canonical identity assignments live in `backend/fixtures/identity_benchmark_identity_v3.json` (schema version `1.0`), a *companion* fixture that leaves the historical `identity_benchmark.json` bytes untouched so v1/v2 reproduction is byte-stable. Each of the 58 benchmark records has exactly one of:

```json
{"record_id": "MISS-A1", "fictional_identity_id": "mina_darzi_001", "rationale": "..."}
{"record_id": "COMMON-A1", "canonical_identity_under_specified": true, "rationale": "..."}
```

`canonical_identity_under_specified` records carry no ID. Any v3 universe pair touching such a record is itself `canonical_identity_under_specified`; no identity is fabricated and no evidence similarity is used as hidden truth.

### v3 truth derivation rule

```python
same_identity    = a.fictional_identity_id == b.fictional_identity_id
under_specified  = a.id is None or b.id is None
otherwise        = different_identity
```

v3 latent truth never consults: incident `ground_truth.relation`, `expected_pair`, extracted fields, normalization output, retrieval/scoring/classification, or the Phase 10R `GROUND_TRUTH_CORRECTIONS_V2` table. Tests mutate each of those inputs and assert v3 truth is unchanged; mutating an identity ID is the only operation that changes v3 truth.

### v3 universe distribution

Of the 36 within-incident universe pairs: 14 `same_identity`, 10 `different_identity`, 12 `canonical_identity_under_specified`. The five Phase 10R corrected labels emerge naturally from identity IDs (the MISS decoys are different identities; the PATH Mohammed-side records are under-specified rather than evidence-inferred).

### Metrics versioning

- `wss_v1` is pinned at `+5` and `wss_v2` at `+25` as historical Phase 10R constants; they are never recomputed.
- `wss_v3` is computed under v3 canonical-truth semantics. An auto-link on an under-specified pair is penalized like a false merge because it is an unsafe conclusion from unknown truth.
- Artifacts serialize `ground_truth_schema`, `identity_schema_version`, `fixture_sha256`, `identity_assignment_sha256` (digest of the sorted `record_id → fictional_identity_id` map), `metric_versions`, and `candidate_metrics_version`. Artifact schema cannot disagree with the metric schema used to generate it.
