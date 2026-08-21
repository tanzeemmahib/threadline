import type { Metadata } from "next";
import { ReverieLanding, type LandingEvidence } from "@/components/reverie-landing";
import { SiteHeader } from "@/components/site-header";
import { loadSubmissionResults } from "@/lib/reverie-evidence";

export const metadata: Metadata = {
  title: "Connect the records. Never guess the person.",
  description:
    "THREADLINE extracts source-cited evidence from fragmented synthetic records while deterministic safety rules decide when the system must stop.",
};

export default async function Home() {
  const artifact = await loadSubmissionResults();
  const baseline = artifact.deterministic_benchmark.systems.find((system) => system.system_id === "generic");
  const workflow = artifact.deterministic_benchmark.systems.find((system) => system.system_id === "threadline");
  const baselineFalseLink = baseline?.metrics.find((metric) => metric.metric_id === "false_link_rate");
  const workflowFalseLink = workflow?.metrics.find((metric) => metric.metric_id === "false_link_rate");
  const exactSpans = workflow?.metrics.find((metric) => metric.metric_id === "evidence_faithfulness");
  const live = artifact.archived_live_prompt_v2;
  const evidence: LandingEvidence = {
    artifactId: artifact.artifact_id,
    evaluationLabel: artifact.deterministic_benchmark.evaluation_label,
    baselineFalseProposals: formatCount(baselineFalseLink?.numerator, baselineFalseLink?.denominator),
    workflowFalseProposals: formatCount(workflowFalseLink?.numerator, workflowFalseLink?.denominator),
    exactSpans: formatCount(exactSpans?.numerator, exactSpans?.denominator),
    liveExtraction: formatCount(live.extraction_quality.records_ok, live.extraction_quality.records_total),
    liveFalseMerges: formatCount(live.decision_metrics.false_merge_count, live.decision_metrics.different_identity_pairs),
    conflictRecall: live.decision_metrics.blocked_conflict_recall.toFixed(3),
  };

  return (
    <>
      <SiteHeader landing />
      <main id="main-content" className="landing-main">
        <p className="sr-only">
          Run a synthetic evidence case with exact source spans, a supported possible connection, and a blocked rival.
        </p>
        <ReverieLanding evidence={evidence} />
      </main>
      <footer className="documentary-footer">
        <span>THREADLINE / SYNTHETIC DEMONSTRATION</span>
        <p>Fictional identities. No autonomous identity decision.</p>
      </footer>
    </>
  );
}

function formatCount(numerator: number | undefined, denominator: number | undefined): string {
  if (numerator === undefined || denominator === undefined) return "Not measured";
  return `${numerator} / ${denominator}`;
}
