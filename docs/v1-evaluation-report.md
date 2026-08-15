# THREADLINE V1 held-out synthetic evaluation

## Answer first

The selected deterministic policy withheld all `4 / 4` different-identity cases in the 40-case synthetic holdout. Because only four cases offered a false-release opportunity, the conditional 95% Wilson upper bound is `48.989%`; the predeclared `10.0%` demonstration target was **not met**. The smaller `8.762%` all-case bound is retained in the artifact for audit, but it is not a conditional false-release bound and must not be used as the safety headline.

## Split and leakage control

The artifact was generated from `backend` with `python scripts/build_v1_evaluation.py` and benchmark seed `20260802`. Four synthetic identities produced 8 calibration cases. Thirty-six disjoint identities produced 40 holdout cases. Identity overlap is zero; cross-split cases were excluded. Demo fixtures are not copied into the benchmark.

## Holdout results

| Metric | Result |
| --- | ---: |
| Candidate top-1 recall | 11.111% (4/36 same-identity cases) |
| Top-1 precision among released review proposals | 100% (3/3) |
| Different-identity cases not released positively | 100% (4/4) |
| Same-identity contract-withheld rate | 19.444% (7/36) |
| Human-review routing | 100% (40/40) |
| Contract rule coverage | 55.556% (10/18) |
| Exact deterministic replay | 100% (40/40) |
| Audit verification | 100% (40/40) |
| Whole-record-removal decision change | 100% (40/40) |

The low top-1 recall and small precision denominator are material limitations: this policy is conservative and incomplete, not deployment-ready. The removal test deletes an entire first record in the top pair; it does not establish that every source span is decision-critical. Rule coverage is 10 of 18 rules on this fixture family, not complete contract coverage.

The versioned machine-readable source is `shared/evaluation/threadline-v1.json`, including definitions, numerators, denominators, assumptions, content hash, and calibration results.
