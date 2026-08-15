import type { Metadata } from "next";
import { AblationLab } from "@/components/evaluation/ablation-lab";
import { BaselineArena } from "@/components/evaluation/baseline-arena";
import { DatasetLab } from "@/components/evaluation/dataset-lab";
import { ErrorWorkbench } from "@/components/evaluation/error-workbench";
import { EvaluationSession } from "@/components/evaluation/evaluation-session";
import { EvaluationRunConsole } from "@/components/evaluation/evaluation-run-console";
import { BenchmarkChart } from "@/components/benchmark-chart";
import { SiteHeader } from "@/components/site-header";
import { StatusPill } from "@/components/status-pill";
import { ThreadLink } from "@/components/thread-motion";
import { benchmarkMetrics, benchmarkSystems } from "@/data/mock-data";
import { v1HeldOutEvidence } from "@/data/v1-evaluation";

export const metadata: Metadata = {
  title: "Research and evaluation laboratory",
  description: "Configure deterministic synthetic data, compare baselines, inspect ablations, and analyze case-level errors without presenting illustrative values as measurements.",
};

const featuredMetrics = [
  { id: "candidate_recall", summary: "Structured retrieval retains more reference candidates than literal matching in this deterministic interface example." },
  { id: "false_link_rate", summary: "The full workflow returns fewer incorrect review candidates in this illustrative fixture." },
  { id: "evidence_faithfulness", summary: "Source-span requirements keep more structured claims tied to evidence in this example." },
  { id: "injection_resistance", summary: "The quarantine boundary resists more tested embedded-instruction cases in this illustrative fixture; this is not a universal safety claim." },
];

export default function BenchmarkPage() {
  return (
    <>
      <SiteHeader active="evaluation" />
      <main id="main-content" className="evaluation-page">
        <section className="evaluation-hero shell" aria-labelledby="evaluation-title">
          <div><p className="eyebrow">Research laboratory / evaluation / failure analysis</p><h1 className="page-title" id="evaluation-title">Inspect the workflow by changing it.</h1><p className="body-large">Generate deterministic fictional cases, compare four systems, remove workflow stages, and trace every changed error back to its first divergence.</p></div>
          <aside className="evaluation-disclaimer" role="note"><StatusPill tone="amber">Evidence modes separated</StatusPill><strong>Saved results and interactive examples have different status</strong><p>The measured panels cite versioned artifacts. The laboratories and summary charts below remain illustrative until a run is connected.</p></aside>
        </section>

        <nav className="research-index shell" aria-label="Evaluation laboratory sections"><a href="#measured-evidence">Measured evidence</a><a href="#dataset-lab">Dataset lab</a><a href="#baseline-arena">Baseline arena</a><a href="#ablation-lab">Ablation lab</a><a href="#error-workbench">Error analysis</a><a href="#run-console">Run console</a><a href="#metric-overview">Metric overview</a></nav>

        <section className="evaluation-section shell" id="measured-evidence" aria-labelledby="measured-evidence-title">
          <div className="evaluation-section__heading">
            <div><p className="eyebrow">Archived evaluation / held-out synthetic evidence</p><h2 className="section-title" id="measured-evidence-title">A measured safety snapshot, with its boundary visible.</h2></div>
            <p>{v1HeldOutEvidence.label} {v1HeldOutEvidence.limitation}</p>
          </div>
          <div className="metric-catalog panel-subtle">
            <h3><StatusPill tone="amber">Preliminary artifact</StatusPill> {v1HeldOutEvidence.benchmarkId}</h3>
            <dl>
              <div><dt>Held-out cases</dt><dd>{v1HeldOutEvidence.holdoutCases} synthetic cases in the versioned V1 evidence-contract artifact.</dd></div>
              <div><dt>Different-identity cases</dt><dd>{v1HeldOutEvidence.differentIdentityWithheld.numerator} / {v1HeldOutEvidence.differentIdentityWithheld.denominator} were withheld; this is the full false-release opportunity set.</dd></div>
              <div><dt>Released-review precision</dt><dd>{v1HeldOutEvidence.releasedReviewPrecision.numerator} / {v1HeldOutEvidence.releasedReviewPrecision.denominator} released review proposals were supported by the synthetic reference labels.</dd></div>
              <div><dt>Candidate top-1 recall</dt><dd>{v1HeldOutEvidence.candidateTop1Recall.numerator} / {v1HeldOutEvidence.candidateTop1Recall.denominator} same-identity cases. This is deliberately not labelled recall@5.</dd></div>
              <div><dt>Conditional 95% upper bound</dt><dd>{v1HeldOutEvidence.conditionalWilsonUpperPercent}% across {v1HeldOutEvidence.negativeCases} negative opportunities. The {v1HeldOutEvidence.targetPercent.toFixed(1)}% demonstration target was <strong>{v1HeldOutEvidence.targetStatus}</strong>.</dd></div>
            </dl>
          </div>
        </section>

        <EvaluationSession>
          <DatasetLab />
          <BaselineArena />
          <AblationLab />
          <ErrorWorkbench />
          <EvaluationRunConsole />
        </EvaluationSession>

        <section className="evaluation-section shell" id="metric-overview" aria-labelledby="systems-title">
          <div className="evaluation-section__heading"><div><p className="eyebrow">Metric overview</p><h2 className="section-title" id="systems-title">Comparable outputs, visible definitions.</h2></div><p>All axes start at zero. These four summary figures remain illustrative and link to the richer case-level laboratories above.</p></div>
          <div className="benchmark-chart-grid">{featuredMetrics.map(({ id, summary }) => { const metric = benchmarkMetrics.find((item) => item.metric_id === id); return metric ? <BenchmarkChart key={id} metric={metric} systems={benchmarkSystems} summary={summary} /> : null; })}</div>
          <div className="metric-catalog panel-subtle"><h3>Benchmark metric contract</h3><dl>{benchmarkMetrics.map((metric) => <div key={metric.metric_id}><dt>{metric.label}</dt><dd>{metric.description}</dd></div>)}</dl></div>
          <div className="operations-table-wrap panel-subtle"><table className="operations-table"><caption>Illustrative operational placeholders — awaiting measured benchmark output</caption><thead><tr><th scope="col">System</th><th scope="col">Average latency</th><th scope="col">Model calls</th><th scope="col">Source</th></tr></thead><tbody>{benchmarkSystems.map((system) => <tr key={system.system_id}><th scope="row">{system.system_name}</th><td>{system.values.average_latency.toLocaleString()} ms</td><td>{system.values.model_calls}</td><td>Synthetic example output</td></tr>)}</tbody></table></div>
        </section>

        <section className="evaluation-close shell"><div><p className="eyebrow">Methods before claims</p><h2 className="section-title">Inspect the workflow boundary and backend contracts.</h2></div><ThreadLink variant="primary" bridge arrow="forward" href="/methodology">Open methodology</ThreadLink></section>
      </main>
    </>
  );
}
