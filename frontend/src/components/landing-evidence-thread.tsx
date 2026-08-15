import type { CSSProperties } from "react";

type EvidenceFragment = {
  id: string;
  label: string;
  detail: string;
  position: string;
  language?: "ar";
};

const fragments: readonly EvidenceFragment[] = [
  { id: "FAMILY-042", label: "Amira Saleh", detail: "Family tracing report", position: "family" },
  { id: "SHELTER-118", label: "Ameera Salih", detail: "Shelter intake · 18:40", position: "shelter" },
  { id: "CLINIC-077", label: "A. Salih", detail: "Field clinic register", position: "clinic" },
  { id: "EVAC-031", label: "Narin Quay", detail: "Manifest · 13:20", position: "evac" },
  { id: "WITNESS-064", label: "إفادة شاهد", detail: "Translated witness fragment", position: "witness", language: "ar" },
  { id: "CONTACT", label: "+999 555 •••• 0142", detail: "Observed across systems", position: "contact" },
] as const;

export function LandingEvidenceThread() {
  return (
    <div className="hero-fragments" role="group" aria-label="Fragmented fields from five fictional records in the Cyclone Ilyra demonstration">
      <p className="sr-only">
        Five fictional records preserve different spellings, sources, times, and a shared contact. No identity conclusion has been made.
      </p>
      <div className="hero-fragments__visual" aria-hidden="true">
        {fragments.map((fragment, index) => (
          <span
            className={`hero-fragment hero-fragment--${fragment.position}`}
            key={fragment.id}
            style={{ "--fragment-order": index } as CSSProperties}
          >
            <small>{fragment.id}</small>
            <strong lang={fragment.language} dir={fragment.language === "ar" ? "rtl" : undefined}>{fragment.label}</strong>
            <i>{fragment.detail}</i>
          </span>
        ))}
      </div>
    </div>
  );
}
