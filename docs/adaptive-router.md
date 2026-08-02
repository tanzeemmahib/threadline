# Adaptive router

The adaptive router reduces work based only on observable input complexity. It does not estimate identity probability and never confirms identity.

Profiles are deterministic:

- `deterministic_only` uses literal/fuzzy processing for two low-complexity records with no warning signals.
- `reduced` runs the workflow with rival testing and independent adjudication disabled when a single non-adversarial complexity signal is present.
- `full` preserves every workflow stage for multilingual, instruction-like, missing-field, timeline/conflict, or multi-rival inputs.

Observable signals are stored with each decision. The benchmark compares full and adaptive outputs using the same ground truth and reports actual metrics, model calls, and duration for both. Savings are not accepted as evidence of safety: candidate output remains a proposal for authorized review.
