import type { Metadata } from "next";
import { SiteHeader } from "@/components/site-header";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";
import { cycloneCaseData, cycloneReconstructionData, cycloneWorkflowTraces } from "@/data/cyclone-case";

export const metadata: Metadata = {
  title: "Run the evidence challenge",
  description: "Compare a single-prompt baseline with THREADLINE on the same fictional Cyclone Ilyra records, then inspect the evidence boundary and authorized-review handoff.",
};

export default function DemoPage() {
  return (
    <>
      <SiteHeader workspace demo />
      <main id="main-content" className="workspace-page demo-recording-frame">
        <WorkspaceShell initialCaseData={cycloneCaseData} initialReconstruction={cycloneReconstructionData} initialTraces={cycloneWorkflowTraces} fixtureOnly />
      </main>
    </>
  );
}
