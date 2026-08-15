"use client";

import { useEffect, useRef, useState } from "react";
import { ThreadButton, ThreadLoader } from "@/components/thread-motion";
import type { ReviewOutcome } from "@/types";

const outcomeOptions: Array<{ value: ReviewOutcome; label: string }> = [
  { value: "additional_evidence_required", label: "Additional evidence required" },
  { value: "candidate_thread_not_supported", label: "Candidate thread not supported" },
  { value: "candidate_thread_remains_plausible", label: "Candidate thread remains plausible" },
  { value: "escalate_to_authorized_case_process", label: "Escalate to authorized case process" },
];

export function ReviewDialog({
  candidateId,
  initialOutcome,
  onClose,
  onSave,
}: {
  candidateId: string;
  initialOutcome: ReviewOutcome | null;
  onClose: () => void;
  onSave: (outcome: ReviewOutcome, notes: string, remainingUncertainty: string[], requestedEvidence: string[]) => Promise<void>;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [outcome, setOutcome] = useState<ReviewOutcome>("additional_evidence_required");
  const [notes, setNotes] = useState("");
  const [remainingUncertainty, setRemainingUncertainty] = useState("Material location contradiction remains unresolved.");
  const [requestedEvidence, setRequestedEvidence] = useState("Independently timestamped transport or custody record.");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (initialOutcome && dialog && !dialog.open) {
      setOutcome(initialOutcome);
      setNotes("");
      dialog.showModal();
    }
  }, [initialOutcome]);

  if (!initialOutcome) return null;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    await onSave(outcome, notes.trim(), remainingUncertainty.split("\n").map((item) => item.trim()).filter(Boolean), requestedEvidence.split("\n").map((item) => item.trim()).filter(Boolean));
    setSaving(false);
  }

  return (
    <dialog className="review-dialog" ref={dialogRef} onCancel={onClose} onClose={onClose} aria-labelledby="review-dialog-title">
      <form className="dialog-shell" onSubmit={submit}>
        <header className="dialog-header">
          <div><span className="panel-kicker">{candidateId} / authorized checkpoint</span><h2 id="review-dialog-title">Record authorized disposition</h2></div>
          <button className="dialog-close" type="button" onClick={() => dialogRef.current?.close()} aria-label="Close review dialog">×</button>
        </header>
        <div className="review-warning" role="note">
          <span aria-hidden="true">!</span>
          <p>THREADLINE proposes candidate record connections only. Final identity decisions require authorized human procedures and independent verification.</p>
        </div>
        <label className="dialog-field">
          <span>Selected outcome</span>
          <select value={outcome} onChange={(event) => setOutcome(event.target.value as ReviewOutcome)}>
            {outcomeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
        <label className="dialog-field">
          <span>Rationale</span>
          <textarea required value={notes} onChange={(event) => setNotes(event.target.value)} rows={4} placeholder="Record which exact spans were checked and why this disposition is appropriate." />
        </label>
        <label className="dialog-field">
          <span>Remaining uncertainty · one item per line</span>
          <textarea required value={remainingUncertainty} onChange={(event) => setRemainingUncertainty(event.target.value)} rows={3} />
        </label>
        <label className="dialog-field">
          <span>Additional evidence requested · one item per line</span>
          <textarea value={requestedEvidence} onChange={(event) => setRequestedEvidence(event.target.value)} rows={3} />
        </label>
        <div className="audit-timestamp"><span>Audit timestamp</span><strong>{new Date().toISOString()}</strong></div>
        <footer className="dialog-footer">
          <ThreadButton variant="secondary" type="button" onClick={() => dialogRef.current?.close()}>Cancel</ThreadButton>
          <ThreadButton variant="primary" type="submit" aria-busy={saving} disabled={saving}>
            {saving ? <ThreadLoader label="Saving authorized outcome" compact announce={false} /> : null}
            {saving ? "Saving outcome…" : "Save outcome"}
          </ThreadButton>
        </footer>
      </form>
    </dialog>
  );
}
