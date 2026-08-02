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
