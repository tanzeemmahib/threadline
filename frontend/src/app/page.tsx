import type { Metadata } from "next";
import { LandingStory } from "@/components/landing-story";
import { SiteHeader } from "@/components/site-header";

export const metadata: Metadata = {
  title: "A connection is not a conclusion",
  description:
    "Reconnect the record. Preserve the uncertainty. THREADLINE is an experimental safety and review layer for possible connections between fragmented synthetic records.",
};

export default function Home() {
  return (
    <>
      <SiteHeader landing />
      <main id="main-content" className="landing-main">
        <p className="sr-only">
          Trace a Synthetic Case with exact source spans and rival explanations.
        </p>
        <LandingStory />
      </main>
      <footer className="documentary-footer">
        <span>THREADLINE / SYNTHETIC DEMONSTRATION</span>
        <p>Fictional identities. No autonomous identity decision.</p>
      </footer>
    </>
  );
}
