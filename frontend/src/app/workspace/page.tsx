import type { Metadata } from "next";
import { SiteHeader } from "@/components/site-header";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export const metadata: Metadata = {
  title: "Synthetic incident workspace",
  description: "Inspect source records, candidate evidence, contradictions, rivals, and human review checkpoints.",
};

export default function WorkspacePage() {
  return (
    <>
      <SiteHeader workspace />
      <main id="main-content" className="workspace-page">
        <WorkspaceShell />
      </main>
    </>
  );
}

