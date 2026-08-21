import type { Metadata } from "next";
import { ReverieJudgeMode } from "@/components/reverie-judge-mode";
import { SiteHeader } from "@/components/site-header";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";
import { cycloneCaseData, cycloneReconstructionData, cycloneWorkflowTraces } from "@/data/cyclone-case";
import { loadReverieEvidence, loadSubmissionResults } from "@/lib/reverie-evidence";

export const metadata: Metadata = {
  title: "Run the evidence case",
  description: "Follow one supported possible connection and one deterministically blocked rival through the same fictional three-record evidence packet.",
};

export default async function DemoPage({
  searchParams,
}: {
  searchParams: Promise<{ workspace?: string; present?: string }>;
}) {
  const query = await searchParams;
  const technicalWorkspace = query.workspace === "1";
  const presentation = query.present === "1";

  if (technicalWorkspace) {
    return (
      <>
        <SiteHeader workspace demo />
        <main id="main-content" className="workspace-page demo-recording-frame">
          <WorkspaceShell initialCaseData={cycloneCaseData} initialReconstruction={cycloneReconstructionData} initialTraces={cycloneWorkflowTraces} fixtureOnly />
        </main>
      </>
    );
  }

  const [evidence, results] = await Promise.all([loadReverieEvidence(), loadSubmissionResults()]);
  return (
    <>
      {presentation ? null : <SiteHeader demo />}
      <main id="main-content" className={`reverie-demo-page${presentation ? " reverie-demo-page--present" : ""}`}>
        <ReverieJudgeMode
          story={evidence.winning_story}
          comparison={results.judge_case_comparison}
          live={results.archived_live_prompt_v2}
          crossScriptCase={evidence.cases[0]}
          presentation={presentation}
        />
      </main>
    </>
  );
}
