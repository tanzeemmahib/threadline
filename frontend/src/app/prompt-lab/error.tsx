"use client";

import { ReverieArtifactErrorState } from "@/components/reverie-artifact-error";

export default function PromptLabError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ReverieArtifactErrorState error={error} reset={reset} surface="Prompt Lab" />;
}
