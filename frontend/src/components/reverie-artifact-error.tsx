"use client";

import { useEffect } from "react";
import { ConnectionState, ThreadButton, ThreadLink } from "@/components/thread-motion";

export function ReverieArtifactErrorState({
  error,
  reset,
  surface,
}: {
  error: Error & { digest?: string };
  reset: () => void;
  surface: "evidence case" | "Prompt Lab";
}) {
  useEffect(() => {
    console.error(`THREADLINE ${surface} artifact boundary`, error);
  }, [error, surface]);

  return (
    <main className="reverie-artifact-error" id="main-content">
      <div className="reverie-artifact-error__signal"><ConnectionState state="interrupted" label="Required evidence artifact did not pass validation" announce /></div>
      <p className="eyebrow">{surface} / fail-closed evidence boundary</p>
      <h1>Verified evidence is unavailable.</h1>
      <p>THREADLINE stopped this route because a required locked artifact could not be read or validated. It will not replace missing evidence with fallback metrics, duplicated examples, or an implied decision.</p>
      {error.digest ? <p className="reverie-artifact-error__digest">Reference / {error.digest}</p> : null}
      <div>
        <ThreadButton variant="primary" motion="signature" arrow="forward" type="button" onClick={reset}>Retry artifact validation</ThreadButton>
        <ThreadLink variant="text" motion="quiet" href="/">Return to THREADLINE</ThreadLink>
      </div>
    </main>
  );
}
