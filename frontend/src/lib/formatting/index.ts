import type { CompatibilityStatus, EvidenceCertainty, SourceType } from "@/types";

export const sourceTypeLabels: Record<SourceType, string> = {
  family_report: "Family report",
  shelter_record: "Shelter record",
  hospital_intake: "Hospital intake",
  evacuation_log: "Evacuation log",
  transport_manifest: "Transport manifest",
  missing_person_registry: "Missing-person registry",
  field_team_note: "Field-team note",
  translated_witness_statement: "Translated witness statement",
  scanned_document_metadata: "Scanned-document metadata",
  translated_phone_submission: "Translated phone submission",
  volunteer_note: "Volunteer note",
  family_tracing_report: "Family tracing report",
  shelter_intake: "Shelter intake",
  field_clinic_register: "Field clinic register",
  evacuation_manifest: "Evacuation manifest",
  aid_registration: "Aid registration",
  translated_witness_note: "Translated witness note",
};

export const statusLabels: Record<CompatibilityStatus, string> = {
  compatible: "Compatible",
  soft_conflict: "Soft conflict",
  hard_conflict: "Hard conflict",
  missing: "Missing",
  uncertain: "Uncertain",
};

export const certaintyLabels: Record<EvidenceCertainty, string> = {
  exact: "Exact",
  estimated: "Estimated",
  translated: "Translated",
  inferred: "Inferred",
  missing: "Missing",
};

export function formatTimestamp(timestamp: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
    timeZoneName: "short",
  }).format(new Date(timestamp));
}

export function humanizeId(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
