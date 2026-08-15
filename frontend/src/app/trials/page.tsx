import type { Metadata } from "next";
import { SiteHeader } from "@/components/site-header";
import { TrialsLab } from "@/components/trials/trials-lab";

export const metadata: Metadata = {
  title: "THREADLINE Trials",
  description: "Run deterministic record mutations, compare systems, and inspect first-divergence evidence without exposing evaluation truth to model prompts.",
};

export default function TrialsPage() {
  return (
    <>
      <SiteHeader active="trials" />
      <main id="main-content" className="trials-page">
        <TrialsLab />
      </main>
    </>
  );
}
