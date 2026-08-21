# THREADLINE submission evidence

Release status: **dirty-worktree draft verified; clean-commit CI pending** — see [`../reverie-release.md`](../reverie-release.md) and the generated [`reverie-release-manifest.json`](reverie-release-manifest.json)
Scope: fictional identities; synthetic research demonstration only

> Same records. Same deterministic mock model. Different workflow. A single prompt reaches a conclusion. THREADLINE preserves the evidence, exposes the contradiction, and withholds what cannot be proven.

THREADLINE is an experimental safety and review layer for proposed record connections. It preserves exact provenance, challenges each hypothesis with contradictions and rival candidates, and deterministically withholds outputs that are not safe for authorized human review.

It is not a production registry, a public people-search system, facial recognition, a replacement for humanitarian organizations, or real-world humanitarian validation.

## Start here

1. Run the offline proof: `../../scripts/run-v1-demo.ps1`.
2. Open `http://127.0.0.1:3000/demo?demo=guided`.
3. Follow [the Reverie three-minute demo script](../reverie-demo-script.md).
4. Open `http://127.0.0.1:3000/prompt-lab` and inspect the [machine-readable Prompt Lab artifact](reverie-prompt-lab.json).
5. Read the [Reverie prompt comparison](../reverie-prompt-comparison.md) and [ML-track node documentation](../reverie-ml-track-documentation.md).
6. Inspect the [Reverie workflow PNG](../reverie-ml-workflow.png) and [editable SVG](../reverie-ml-workflow.svg).

The original four-minute script and compact implementation diagram remain below as technical reference; the Reverie path above is the primary submission narrative.

No model credential or network connection is required for this path. The interface labels it **Deterministic mock replay - not model performance**.

## Evidence package

### Measured and machine-readable

- [Reverie Prompt Lab artifact](reverie-prompt-lab.json) - three identical-input case comparisons plus locked V1/V2/V3 prompt evidence.
- [Benchmark report](benchmark-report.md) - answer-first comparison, ablations, counterfactual, caveats, and reproduction.
- [Results JSON](results.json) - compact deterministic comparison and separately labeled archived live-provider evidence.
- [Results CSV](results.csv) - metric rows with formulas, numerators, and denominators.
- [Raw outputs JSON](raw-outputs.json) - per-case deterministic outputs and exact judge-case inputs.
- [Ablation and counterfactual JSON](ablation-counterfactual.json) - no-effect benchmark ablations retained honestly and one source-removal counterfactual.

### Workflow and safety

- [Workflow node documentation](workflow-node-documentation.md) - purpose, input, output, model/tool, prompt, validation, failure behavior, separation rationale, and limitations for all twelve nodes.
- [Data responsibility and threat boundary](data-responsibility.md) - data flow, local storage, connected-provider payloads, access gaps, retention, redaction, prompt injection, and export risk.
- [Workflow diagram PNG](threadline-workflow.png) - seven readable submission stages.
- [Workflow diagram SVG](threadline-workflow.svg) - editable vector source.

### Demo and reproduction

- [Legacy four-minute workspace-tour script](demo-script.md) - retained only as a technical reference for the earlier eight-scene flow.
- [Reproduction guide](reproduction.md) - dependency setup, offline proof, evidence generation, checks, and cold start.

### Final browser captures

- [Desktop landing](../product-screenshots/reverie/desktop-landing.png)
- [Supported review-only thread](../product-screenshots/reverie/desktop-supported-thread.png)
- [Deterministically blocked rival](../product-screenshots/reverie/desktop-blocked-rival.png)
- [Measured proof](../product-screenshots/reverie/desktop-measured-proof.png)
- [Prompt Lab](../product-screenshots/reverie/desktop-prompt-lab.png)
- [Technical workspace](../product-screenshots/reverie/desktop-workspace.png)
- [390 px landing](../product-screenshots/reverie/mobile-landing-390.png)
- [390 px evidence case](../product-screenshots/reverie/mobile-evidence-case-390.png)

### Print-ready files

- [One-page evidence summary](../../output/pdf/threadline-reverie-evidence-summary.pdf) - compact case, prompt-promotion, safety-boundary, and reproduction proof.
- [Reverie workflow PDF](../../output/pdf/threadline-reverie-workflow.pdf) - full-page seven-stage workflow.
- [Prompt comparison PDF](../../output/pdf/threadline-reverie-prompt-comparison.pdf) - printable same-input comparison and prompt iteration report.
- [ML-track documentation PDF](../../output/pdf/threadline-reverie-ml-track-documentation.pdf) - printable node and safety-boundary reference.

The older `comparison-samples.pdf` and `workflow-node-documentation.pdf` predate the current Reverie six-scene package. They remain legacy technical derivatives and are not primary upload artifacts.

PDFs are derived presentation artifacts. The Markdown, JSON, CSV, raw outputs, and editable SVG remain the auditable sources.

## Evidence tracks must remain separate

### Track A - deterministic workflow comparison

- fixed synthetic cases;
- identical input manifest per compared system;
- deterministic mock provider;
- reasonable generic and structured one-call prompts;
- full THREADLINE workflow; and
- exact per-case outputs.

This track demonstrates workflow behavior and reproducibility. It is not a measurement of live model quality.

### Track B - archived live-provider Prompt V2 extraction

- 58 synthetic records;
- OpenAI-compatible provider;
- `Qwen/Qwen3-30B-A3B-Instruct-2507`;
- temperature `0`;
- production extraction prompt `v2`;
- one archived run; and
- downstream deterministic retrieval and policy metrics.

This track measures one live extraction run. It is not a same-model single-prompt versus full-workflow experiment, has no repeated-run confidence interval, and does not establish field safety.

The package never blends Track A and Track B into one score.

## Terminology

| Use | Do not imply |
| --- | --- |
| Possible connection | Identity match |
| Supported | Confirmed |
| Contradicted | Incorrect person |
| Insufficient evidence | Low-confidence match |
| Withheld | Failed |
| Human review required | AI decision |
| Candidate record | Identified person |

## Prior work and narrower contribution

The ICRC [Missing Persons Digital Matching tool](https://www.icrc.org/sites/default/files/media_file/2024-12/MPDM_tool_A4_1%20pager.pdf) already applies digital search and matching to missing-person work. THREADLINE does not claim to originate that field. Its narrower research focus is claim-to-source lineage, contradiction and rival analysis, prompt-injection containment, deterministic release rules, replay, counterfactual evaluation, and safety-weighted synthetic benchmarking.

The submission also cites the ICRC [Handbook on Data Protection in Humanitarian Action](https://www.icrc.org/en/data-protection-humanitarian-action-handbook) and [revised OCHA Data Responsibility Guidelines](https://centre.humdata.org/revised-ocha-data-responsibility-guidelines/). THREADLINE is not endorsed by, validated by, or operationally compliant with either organization.

## Named limitations

- All records and identities are fictional and synthetic.
- The deterministic comparison is not model-performance evidence.
- The archived live result is one extraction run, not a repeated evaluation or live same-model baseline comparison.
- Small negative-case denominators make zero observed false merges preliminary only.
- The selected benchmark node ablations may show no primary-metric change; that result is retained rather than hidden.
- Authentication, authorization, encryption at rest, retention/deletion automation, data residency, and production reviewer governance are not implemented.
- Connected-provider exact replay is not implemented.
- No operational humanitarian organization has validated THREADLINE.

## Final release gate

Use the single [Reverie release procedure](../reverie-release.md). The generated manifest is content-addressed and the CI workflow starts from a clean checkout. A dirty-worktree manifest is a draft and must not be represented as a commit-complete release.

Before upload, the release owner must record exact results for backend tests, deterministic validators, frontend tests, typecheck, lint, production build, integration smoke, cold start, desktop/mobile browser inspection, reduced motion, PDF page inspection, and broken-link checks. Any failure remains a named limitation; it must not be hidden or converted into a pass.
