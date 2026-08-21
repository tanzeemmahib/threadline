"use client";

import { ReverieArtifactErrorState } from "@/components/reverie-artifact-error";

export default function DemoError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ReverieArtifactErrorState error={error} reset={reset} surface="evidence case" />;
}
