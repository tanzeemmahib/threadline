import type { Metadata } from "next";
import { PromptLab } from "@/components/prompt-lab/prompt-lab";
import { SiteHeader } from "@/components/site-header";
import { loadReverieEvidence, loadReverieLiveEvaluation } from "@/lib/reverie-evidence";

export const metadata: Metadata = {
  title: "Prompt Lab — same input, visible safety boundary",
  description: "Compare a reasonable single-call baseline with THREADLINE's source-cited workflow on the same locked synthetic evidence.",
};

export default async function PromptLabPage() {
  const [artifact, liveEvaluation] = await Promise.all([loadReverieEvidence(), loadReverieLiveEvaluation()]);

  return (
    <>
      <SiteHeader active="prompt-lab" />
      <main className="prompt-lab-page" id="main-content">
        <PromptLab artifact={artifact} liveEvaluation={liveEvaluation} />
      </main>
    </>
  );
}
