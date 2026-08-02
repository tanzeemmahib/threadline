# THREADLINE Trials

THREADLINE Trials is a deterministic, synthetic-only mutation harness for discovering where record-reconciliation systems first diverge from an accepted evaluation label set. It never changes protected ground truth, never includes ground truth in model-visible prompts, and never turns an evaluation result into an identity decision.

## Catalogue

The stable catalogue contains `TRIAL-001` through `TRIAL-008`: transliteration, distinctive-feature conflict, equally plausible rivals, impossible timeline, prompt injection, translation loss, common-name collision, and clean-but-incomplete evidence. Expected outcomes emphasize possible/conflicting/insufficient evidence and safe abstention.

The mutation engine supports exactly 15 mutation types: transliteration and spelling corruption; missing surname/location; estimated-age shift; changed location; impossible timeline; conflicting distinctive feature; translation detail loss; common-name collision; duplicate submission; equally plausible rivals; prompt injection; source-reliability noise; and contradictory relative information.

Each mutation record stores a deterministic ID, seed, affected records and fields, before/after values, challenge, protected relation, `ground_truth_changed: false`, difficulty, and safety note. Added duplicates and rivals receive unique record IDs so input validation remains intact.

## Execution and divergence

Preview applies mutations without running a system. Run sends the same mutated `AnalyzeRequest` to exact/fuzzy, generic single-call, structured single-call, and the full THREADLINE workflow. Ground truth remains in the evaluation process only.

First-divergence categories are deterministic: candidate retrieval, classification, evidence support, contradiction handling, rival handling, injection quarantine, privacy gate, abstention, or none. The result stores the first divergent system/node, expected set, observed value, and explanation. Every run and export has a stable reloadable ID.
