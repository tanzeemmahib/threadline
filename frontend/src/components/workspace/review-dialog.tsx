"use client";

import { useEffect, useRef, useState } from "react";
import type { ReviewOutcome } from "@/types";

const outcomeOptions: Array<{ value: ReviewOutcome; label: string }> = [
  { value: "request_more_information", label: "Request more information" },
  { value: "dismiss_candidate", label: "Dismiss candidate" },
  { value: "escalate_authorized_review", label: "Escalate for authorized review" },
  { value: "mark_unrelated", label: "Mark records as unrelated" },
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
  onSave: (outcome: ReviewOutcome, notes: string) => Promise<void>;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [outcome, setOutcome] = useState<ReviewOutcome>("escalate_authorized_review");
  const [notes, setNotes] = useState("");
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
    await onSave(outcome, notes.trim());
    setSaving(false);
  }

  return (
    <dialog className="review-dialog" ref={dialogRef} onCancel={onClose} onClose={onClose} aria-labelledby="review-dialog-title">
      <form className="dialog-shell" onSubmit={submit}>
        <header className="dialog-header">
          <div><span className="panel-kicker">{candidateId} / authorized checkpoint</span><h2 id="review-dialog-title">Record verification outcome</h2></div>
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
          <span>Reviewer notes</span>
          <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={5} placeholder="Record what was checked, what remains unresolved, and the next authorized step." />
        </label>
        <div className="audit-timestamp"><span>Audit timestamp</span><strong>{new Date().toISOString()}</strong></div>
        <footer className="dialog-footer">
          <button className="button-secondary" type="button" onClick={() => dialogRef.current?.close()}>Cancel</button>
          <button className="button-primary" type="submit" disabled={saving}>{saving ? "Saving outcome…" : "Save outcome"}</button>
        </footer>
      </form>
    </dialog>
  );
}
