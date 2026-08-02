import type { Metadata } from "next";
import { CasePacket } from "@/components/workspace/case-packet";
import { PrintButton } from "@/components/workspace/print-button";

export const metadata: Metadata = { title: "Case review packet", description: "Print-optimized synthetic case review packet." };

export default async function CasePacketPage({ searchParams }: { searchParams: Promise<{ candidate?: string }> }) {
  const params = await searchParams;
  return (
    <main id="main-content" className="case-packet-page">
      <div className="case-packet-actions no-print"><p>Print or save this synthetic case packet using the browser dialog.</p><PrintButton /></div>
      <CasePacket candidateId={params.candidate ?? "MATCH-001"} />
    </main>
  );
}
