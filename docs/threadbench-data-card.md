# THREADBENCH synthetic data card

## Intended use

THREADBENCH evaluates inspectability, candidate-retrieval behavior, safe abstention, evidence faithfulness, multilingual robustness, and tested prompt-injection handling in THREADLINE. It contains fictional identities only. It is not representative of real-world population frequencies and must not be used to identify a person.

## Generation

`random.Random(seed)` drives record creation. The saved configuration includes identity and record counts, languages, corruption rates, age variance, changed locations, duplicates, contradictory timestamps, rivals, injected instructions, and common-name frequency. A SHA-256 content hash identifies the generated dataset. Ground truth is stored separately from analysis requests.

Default multi-seed evaluation uses `[104, 205, 306, 407, 508]`. Reports include mean, population standard deviation, minimum, maximum, successful/failed runs, case count, provider/model, actual model calls, and measured duration. Fixed-seed bootstrap 95% intervals use bootstrap seed `904221` and 1,000 resamples.

## Metrics and limitations

Metrics include candidate recall at K, false-link rate, correct abstention, evidence faithfulness, tested injection resistance, multilingual robustness, classification accuracy, duration, model calls, failures, and retries. Zero denominators remain explicit. Mock-provider results are labeled “Deterministic mock evaluation — not real model performance.” Connected results are labeled “Measured provider evaluation.”

Synthetic templates cover selected languages and corruptions, not humanitarian reality. They cannot establish fairness, field safety, language coverage, or operational readiness.
