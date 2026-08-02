# Risk–coverage analysis

THREADLINE risk–coverage uses a review-priority score, not a calibrated probability. The score is computed from observable output features: insufficient/conflicting classifications, conflict count, rival count, abstention reasons, and cited-evidence count.

Three fixed policies are reported:

| Policy | Review threshold | Interpretation |
|---|---:|---|
| Exploratory | 0.75 | Higher automated coverage for research inspection. |
| Balanced | 0.50 | Intermediate coverage and review workload. |
| Conservative | 0.25 | More cases retained for human review. |

Coverage is the share below the review threshold. Selective risk is the observed classification error rate among that covered subset. Reviewed cases are the complement. Curves are derived from actual benchmark outputs and the separately stored synthetic ground truth. They do not justify deployment thresholds or autonomous action.
