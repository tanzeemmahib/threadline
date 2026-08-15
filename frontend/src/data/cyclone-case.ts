import { workflowNodes } from "@/data/mock-data";
import type {
  AuditEvent,
  CandidateConnection,
  CaseData,
  EvidenceClaim,
  EvidenceContract,
  EvidenceCertainty,
  OriginalEvidenceSpan,
  ReconstructionData,
  SourceRecord,
  WorkflowNodeTrace,
} from "@/types";

const CASE_ID = "CASE-CYCLONE-ILYRA-001";
const RUN_ID = "RUN-DEMO-CYCLONE-ILYRA-001";
const CREATED_AT = "2026-06-15T09:00:00Z";
const safetyNotice = "THREADLINE turns fragmented records into reviewable evidence threads—not automated identity verdicts. Authorized human review remains required.";

function span(recordId: string, text: string, id: string, field: string, quote: string, certainty: EvidenceCertainty = "exact"): OriginalEvidenceSpan {
  const start = text.indexOf(quote);
  if (start < 0) throw new Error(`Fixture span ${id} does not resolve.`);
  return {
    span_id: id,
    record_id: recordId,
    source_document_id: recordId,
    quote,
    text: quote,
    start,
    end: start + quote.length,
    field,
    certainty,
    extraction_method: "deterministic_pattern",
    extraction_status: "extracted",
    valid: true,
    validation_status: "valid",
    content_hash: `sha256:${id.toLowerCase()}-immutable`,
    language: recordId === "FAMILY-042" || recordId === "WITNESS-064" ? "Arabic" : "English",
    created_at: CREATED_AT,
    created_by: "threadline_extract",
    validated_at: CREATED_AT,
  };
}

function record(input: Omit<SourceRecord, "fields" | "evidence_spans" | "quarantined" | "status" | "reliability_note"> & { spans: Array<[string, string, string, EvidenceCertainty?]>; reliability: string }): SourceRecord {
  const evidence_spans = input.spans.map(([id, field, quote, certainty]) => span(input.record_id, input.text, id, field, quote, certainty));
  return {
    ...input,
    status: "candidate",
    quarantined: false,
    reliability_note: input.reliability,
    evidence_spans,
    fields: evidence_spans.map((item) => ({
      field_id: `FIELD-${item.span_id}`,
      key: item.field.toLowerCase().replaceAll(" ", "_"),
      label: item.field,
      value: item.quote,
      certainty: item.certainty,
      source_span_id: item.span_id,
      normalized_value: item.field === "Name" ? item.quote.toLowerCase().replaceAll("ee", "i").replaceAll("ih", "eh") : item.quote,
    })),
  };
}

export const cycloneRecords: SourceRecord[] = [
  record({
    record_id: "FAMILY-042", source_type: "family_tracing_report", source_organization: "Maruva Family Reconnection Desk", language: "Arabic", timestamp: "2026-06-14T18:24:00Z", display_name: "Amira Saleh",
    text: "بلاغ أسري / translated intake fields: Amira Saleh, age 15. DOB 2010-02-14. Arabic and limited English. Emergency contact Khaled Saleh +999 555 0142. Mother Laila Saleh. Observed at Narin Quay at 18:20 wearing a navy raincoat.",
    translated_text: "Family report: Amira Saleh, age 15, observed at Narin Quay at 18:20. Emergency contact Khaled Saleh; mother Laila Saleh.", translation_provenance: "TRANS-AR-042 · human translation artifact", translation_warning: "The location was relayed by telephone and is not independently corroborated.",
    created_at: "2026-06-14T18:24:00Z", event_time: "2026-06-14T18:20:00Z", reliability: "Translated family tracing update; telephone relay remains uncorroborated.",
    spans: [["SPAN-F42-NAME", "Name", "Amira Saleh", "translated"], ["SPAN-F42-DOB", "Birth date", "DOB 2010-02-14", "translated"], ["SPAN-F42-CONTACT", "Emergency contact", "Emergency contact Khaled Saleh +999 555 0142", "translated"], ["SPAN-F42-FAMILY", "Family relationship", "Mother Laila Saleh", "translated"], ["SPAN-F42-LOC", "Location", "Narin Quay", "translated"], ["SPAN-F42-TIME", "Timeline", "18:20", "translated"], ["SPAN-F42-CLOTH", "Clothing", "navy raincoat", "translated"]],
  }),
  record({
    record_id: "SHELTER-118", source_type: "shelter_intake", source_organization: "Harbor Relief Shelter Network", language: "English", timestamp: "2026-06-14T18:43:00Z", display_name: "Ameera Salih",
    text: "Shelter intake: Ameera Salih, age 15. Birth date 2010-04-12. Arabic and limited English. Emergency contact Khaled Saleh +999 555 0142. Mother: Layla. Direct intake at Hillcrest School at 18:40, reportedly from Pine Ridge Transit, wearing a navy raincoat.",
    created_at: "2026-06-14T18:43:00Z", event_time: "2026-06-14T18:40:00Z", reliability: "Direct intake; birth date copied from an unverified handwritten card.",
    spans: [["SPAN-S118-NAME", "Name", "Ameera Salih"], ["SPAN-S118-DOB", "Birth date", "Birth date 2010-04-12"], ["SPAN-S118-CONTACT", "Emergency contact", "Emergency contact Khaled Saleh +999 555 0142"], ["SPAN-S118-FAMILY", "Family relationship", "Mother: Layla"], ["SPAN-S118-LOC", "Location", "Hillcrest School"], ["SPAN-S118-TIME", "Timeline", "18:40"], ["SPAN-S118-ORIGIN", "Location", "Pine Ridge Transit"], ["SPAN-S118-CLOTH", "Clothing", "navy raincoat"]],
  }),
  record({
    record_id: "CLINIC-077", source_type: "field_clinic_register", source_organization: "Kestrel Field Hospital", language: "English", timestamp: "2026-06-13T08:19:00Z", display_name: "A. Salih",
    text: "Clinic register: A. Salih, estimated age 14-16. Treated at East Levee Clinic at 08:15. Aunt: Mariam Salih. Arabic speaker. Wrist abrasion; onward destination not recorded.",
    created_at: "2026-06-13T08:19:00Z", event_time: "2026-06-13T08:15:00Z", reliability: "Point-of-care register; abbreviated name and estimated age.",
    spans: [["SPAN-C77-NAME", "Name", "A. Salih"], ["SPAN-C77-LOC", "Location", "East Levee Clinic"], ["SPAN-C77-TIME", "Timeline", "08:15"], ["SPAN-C77-FAMILY", "Family relationship", "Aunt: Mariam Salih"]],
  }),
  record({
    record_id: "EVAC-031", source_type: "evacuation_manifest", source_organization: "Bluewater Evacuation Service", language: "English", timestamp: "2026-06-12T13:25:00Z", display_name: "A. Salih",
    text: "Evacuation manifest: A. Salih, estimated age 14-16, boarded at Narin Quay at 13:20 for Riverbend Depot wearing a dark blue raincoat. Emergency contact was not recorded.",
    created_at: "2026-06-12T13:25:00Z", event_time: "2026-06-12T13:20:00Z", reliability: "Water-damaged primary manifest; destination remained legible.",
    spans: [["SPAN-E31-NAME", "Name", "A. Salih"], ["SPAN-E31-LOC", "Location", "Narin Quay"], ["SPAN-E31-TIME", "Timeline", "13:20"], ["SPAN-E31-DEST", "Location", "Riverbend Depot"], ["SPAN-E31-CLOTH", "Clothing", "dark blue raincoat"]],
  }),
  record({
    record_id: "AID-209", source_type: "aid_registration", source_organization: "Tideland Aid Registry", language: "English", timestamp: "2026-06-14T17:59:00Z", display_name: "Amira Salah",
    text: "Aid registration: Amira Salah, age 15. Date of birth 2010-02-14. Emergency contact Khaled Saleh +999 555 0142 copied from a wrist card. Registered at Riverbend Depot at 17:55 after travel from South Canal Camp. White shirt; family relationship unverified.",
    created_at: "2026-06-14T17:59:00Z", event_time: "2026-06-14T17:55:00Z", reliability: "Direct registration; contact copied from a wrist card and is not an independent discriminator.",
    spans: [["SPAN-A209-NAME", "Name", "Amira Salah"], ["SPAN-A209-DOB", "Birth date", "Date of birth 2010-02-14"], ["SPAN-A209-CONTACT", "Emergency contact", "Emergency contact Khaled Saleh +999 555 0142"], ["SPAN-A209-LOC", "Location", "Riverbend Depot"], ["SPAN-A209-TIME", "Timeline", "17:55"], ["SPAN-A209-ORIGIN", "Location", "South Canal Camp"]],
  }),
  record({
    record_id: "WITNESS-064", source_type: "translated_witness_note", source_organization: "Maruva Community Translation Unit", language: "Arabic", timestamp: "2026-06-14T20:10:00Z", display_name: "Ameera Salih",
    text: "إفادة شاهد / translated fields: Ameera Salih, estimated age 14-16, seen at South Canal Camp at 17:00 with an adult woman described as an aunt. Red bag. Destination unknown.",
    translated_text: "Witness note: Ameera Salih, estimated age 14-16, seen at South Canal Camp at 17:00 with an adult woman possibly an aunt.", translation_provenance: "TRANS-AR-064 · reviewed translation artifact", translation_warning: "The relationship description is uncertain and the witness report was delayed.",
    created_at: "2026-06-14T20:10:00Z", event_time: "2026-06-14T17:00:00Z", reliability: "Translated witness recollection recorded three hours after the claimed observation.",
    spans: [["SPAN-W64-NAME", "Name", "Ameera Salih", "translated"], ["SPAN-W64-LOC", "Location", "South Canal Camp", "translated"], ["SPAN-W64-TIME", "Timeline", "17:00", "translated"], ["SPAN-W64-FAMILY", "Family relationship", "described as an aunt", "inferred"]],
  }),
];

const leading: CandidateConnection = {
  candidate_id: "THREAD-LEADING-01", record_a_id: "FAMILY-042", record_b_id: "SHELTER-118", label: "Output withheld", classification: null, classification_code: null, review_status: "review_required",
  compatibility_factors: [
    { factor_id: "CF-LEAD-NAME", field: "Name", record_a_value: "Amira Saleh", record_b_value: "Ameera Salih", status: "compatible", interpretation: "Two spelling variations normalize to a comparable form; the originals remain authoritative.", certainty_a: "translated", certainty_b: "exact", evidence_span_ids: ["SPAN-F42-NAME", "SPAN-S118-NAME"] },
    { factor_id: "CF-LEAD-CONTACT", field: "Emergency contact", record_a_value: "Khaled Saleh +999 555 0142", record_b_value: "Khaled Saleh +999 555 0142", status: "compatible", interpretation: "The shared contact supports this thread and the rival, so it is not independently distinguishing.", certainty_a: "translated", certainty_b: "exact", evidence_span_ids: ["SPAN-F42-CONTACT", "SPAN-S118-CONTACT"] },
    { factor_id: "CF-LEAD-DOB", field: "Birth date", record_a_value: "2010-02-14", record_b_value: "2010-04-12", status: "soft_conflict", interpretation: "Day and month differ; the shelter value came from an unverified handwritten card.", certainty_a: "translated", certainty_b: "exact", evidence_span_ids: ["SPAN-F42-DOB", "SPAN-S118-DOB"] },
    { factor_id: "CF-LEAD-FAMILY", field: "Family relationship", record_a_value: "Mother Laila Saleh", record_b_value: "Mother: Layla", status: "uncertain", interpretation: "The relationship and spelling are partially compatible but incomplete.", certainty_a: "translated", certainty_b: "exact", evidence_span_ids: ["SPAN-F42-FAMILY", "SPAN-S118-FAMILY"] },
    { factor_id: "CF-LEAD-LOCATION", field: "Location", record_a_value: "Narin Quay · 18:20", record_b_value: "Hillcrest School · 18:40", status: "hard_conflict", interpretation: "The two observations are 20 minutes apart at sites outside the validated transfer window.", certainty_a: "translated", certainty_b: "exact", evidence_span_ids: ["SPAN-F42-LOC", "SPAN-F42-TIME", "SPAN-S118-LOC", "SPAN-S118-TIME"] },
  ],
  conflicts: [{ conflict_id: "CONFLICT-LOCATION-001", field: "Location", severity: "hard", explanation: "Narin Quay at 18:20 and Hillcrest School at 18:40 cannot be reconciled with the available transport evidence.", evidence_span_ids: ["SPAN-F42-LOC", "SPAN-F42-TIME", "SPAN-S118-LOC", "SPAN-S118-TIME"] }],
  rivals: [{ record_id: "AID-209", display_name: "Amira Salah", age: "15", comparison: { name: "stronger", age: "stronger", language: "unresolved", location: "conflicting", timeline: "conflicting", clothing: "weaker", distinctive_features: "unresolved", hard_conflicts: "conflicting" }, summary: "A credible rival shares the birth date and contact, but the contact was copied and its movement path also conflicts." }],
  supporting_summary: "Name variation, shared contact, partial family evidence, and clothing support a candidate thread.", opposing_summary: "A material 20-minute location contradiction remains unresolved; the 34-hour interval from clinic to aid registration is also incomplete.", verification_question: "Can an independently timestamped transport or custody record resolve the Narin Quay–Hillcrest conflict?", verification_explanation: "Only an authorized reviewer may record the disposition after comparing the exact source spans.", additional_questions: ["Was the emergency contact copied between systems?", "Can the missing 34-hour interval be reconstructed?"], abstention_reasons: ["Material location contradiction remains unresolved."],
};

const rival: CandidateConnection = {
  ...leading,
  candidate_id: "THREAD-RIVAL-02", record_b_id: "AID-209",
  compatibility_factors: [
    { factor_id: "CF-RIVAL-NAME", field: "Name", record_a_value: "Amira Saleh", record_b_value: "Amira Salah", status: "compatible", interpretation: "A close spelling variation supports the rival thread.", certainty_a: "translated", certainty_b: "exact", evidence_span_ids: ["SPAN-F42-NAME", "SPAN-A209-NAME"] },
    { factor_id: "CF-RIVAL-CONTACT", field: "Emergency contact", record_a_value: "Khaled Saleh +999 555 0142", record_b_value: "copied from wrist card", status: "uncertain", interpretation: "Compatible with either candidate because this value was copied.", certainty_a: "translated", certainty_b: "exact", evidence_span_ids: ["SPAN-F42-CONTACT", "SPAN-A209-CONTACT"] },
    { factor_id: "CF-RIVAL-LOCATION", field: "Location", record_a_value: "Narin Quay · 18:20", record_b_value: "Riverbend Depot · 17:55", status: "hard_conflict", interpretation: "The observed locations are incompatible within 25 minutes.", certainty_a: "translated", certainty_b: "exact", evidence_span_ids: ["SPAN-F42-LOC", "SPAN-F42-TIME", "SPAN-A209-LOC", "SPAN-A209-TIME"] },
  ],
  conflicts: [{ conflict_id: "CONFLICT-RIVAL-LOCATION-002", field: "Location", severity: "hard", explanation: "Riverbend Depot at 17:55 conflicts with Narin Quay at 18:20.", evidence_span_ids: ["SPAN-A209-LOC", "SPAN-A209-TIME", "SPAN-F42-LOC", "SPAN-F42-TIME"] }],
  rivals: [{ record_id: "SHELTER-118", display_name: "Ameera Salih", age: "15", comparison: { name: "unresolved", age: "conflicting", language: "stronger", location: "conflicting", timeline: "conflicting", clothing: "stronger", distinctive_features: "unresolved", hard_conflicts: "conflicting" }, summary: "The leading shelter thread remains plausible but has a birth-date discrepancy and material location conflict." }],
  supporting_summary: "The rival has a close name form, same stated birth date, and the shared emergency contact.", opposing_summary: "The contact was copied and the Riverbend–Narin observations conflict.",
};

function findSpan(id: string): OriginalEvidenceSpan {
  const found = cycloneRecords.flatMap((item) => item.evidence_spans).find((item) => item.span_id === id);
  if (!found) throw new Error(`Unknown fixture span ${id}`);
  return found;
}

function claim(id: string, type: EvidenceClaim["claim_type"], text: string, spanIds: string[], parents: string[], node: string, certainty: EvidenceCertainty): EvidenceClaim {
  const spans = spanIds.map(findSpan);
  return {
    claim_id: id, candidate_id: leading.candidate_id, case_id: CASE_ID, claim_type: type, claim_text: text, raw_value: spans.map((item) => item.quote).join(" | "), normalized_value: text, certainty_category: certainty,
    source_record_ids: [...new Set(spans.map((item) => item.record_id))], source_spans: spans, source_span_ids: spanIds, certainty_basis: Object.fromEntries(spans.map((item) => [item.span_id, item.certainty])), generated_by_node: node, created_by: `threadline_${node}`, created_at: CREATED_AT, supported: true, support_reason: "Exact quotations resolve to immutable source offsets; uncertainty remains explicit.", violations: id === "CLAIM-CONTRADICTION-LOCATION" ? ["VIOLATION-MATERIAL-LOCATION"] : [], parent_claim_ids: parents, transformation_type: type === "extracted_fact" ? "direct_extraction" : "deterministic_transformation", transformation_version: "1.0.0", transformation_history: type === "extracted_fact" ? [] : [{ transformation_id: `TRANSFORM-${id}`, transformation_type: "deterministic_transformation", transformation_version: "1.0.0", input_claim_ids: parents, input_artifact_ids: spanIds, output_certainty: certainty, created_by_step: node, created_at: CREATED_AT }], consumed_by_rule_ids: type === "contradiction_claim" ? ["TIMELINE_CONSISTENCY", "MATERIAL_CONTRADICTIONS_RESOLVED"] : ["SOURCE_SPAN_INTEGRITY", "CLAIM_LINEAGE_COMPLETE", "CERTAINTY_PRESERVED"], claim_hash: `sha256:${id.toLowerCase()}-validated`,
  };
}

const claims: EvidenceClaim[] = [
  claim("CLAIM-EXTRACT-F42-NAME", "extracted_fact", "Reported name: Amira Saleh", ["SPAN-F42-NAME"], [], "extract", "translated"),
  claim("CLAIM-EXTRACT-S118-NAME", "extracted_fact", "Shelter name: Ameera Salih", ["SPAN-S118-NAME"], [], "extract", "exact"),
  claim("CLAIM-NORMALIZED-NAME", "normalized_representation", "Comparable name form: amira saleh", ["SPAN-F42-NAME", "SPAN-S118-NAME"], ["CLAIM-EXTRACT-F42-NAME", "CLAIM-EXTRACT-S118-NAME"], "normalize", "translated"),
  claim("CLAIM-CONTACT-COMPATIBLE", "compatibility_claim", "The same emergency contact appears in both records and also in the rival.", ["SPAN-F42-CONTACT", "SPAN-S118-CONTACT", "SPAN-A209-CONTACT"], ["CLAIM-EXTRACT-F42-NAME", "CLAIM-EXTRACT-S118-NAME"], "hypothesis", "translated"),
  claim("CLAIM-TIMELINE-GAP", "timeline_interpretation", "A 34-hour interval between clinic treatment and later registration has no custody or transport record.", ["SPAN-C77-TIME", "SPAN-A209-TIME"], ["CLAIM-EXTRACT-F42-NAME"], "timeline", "inferred"),
  claim("CLAIM-CONTRADICTION-LOCATION", "contradiction_claim", "Narin Quay at 18:20 conflicts materially with Hillcrest School at 18:40.", ["SPAN-F42-LOC", "SPAN-F42-TIME", "SPAN-S118-LOC", "SPAN-S118-TIME"], ["CLAIM-EXTRACT-F42-NAME", "CLAIM-EXTRACT-S118-NAME"], "prosecutor", "translated"),
  claim("CLAIM-RIVAL-COVERAGE", "rival_comparison_claim", "AID-209 is credible because the birth date and contact align, but its copied contact and location conflict prevent preference.", ["SPAN-A209-NAME", "SPAN-A209-DOB", "SPAN-A209-CONTACT", "SPAN-A209-LOC", "SPAN-A209-TIME"], ["CLAIM-EXTRACT-F42-NAME"], "rivals", "inferred"),
];

const ruleNames = ["SOURCE_SPAN_INTEGRITY", "CLAIM_LINEAGE_COMPLETE", "CERTAINTY_PRESERVED", "TIMELINE_CONSISTENCY", "MATERIAL_CONTRADICTIONS_RESOLVED", "RIVAL_EXPLANATION_COVERAGE", "REQUIRED_SAFETY_NOTICE_PRESENT", "HUMAN_REVIEW_ROUTING_VALID", "AUDIT_EVENT_READY", "RELEASE_AUTHORIZATION_VALID"] as const;
const contract: EvidenceContract = {
  contract_id: "CONTRACT-CYCLONE-LEADING-001", case_id: CASE_ID, candidate_id: leading.candidate_id, classification: null, contract_status: "blocked", release_allowed: false, claims,
  violations: [{ violation_id: "VIOLATION-MATERIAL-LOCATION", rule_id: "EC-007", severity: "critical", claim_id: "CLAIM-CONTRADICTION-LOCATION", message: "A material location contradiction remains unresolved and the incident policy fails closed.", blocks_release: true, suggested_resolution: "Compare exact spans and request independently timestamped transport evidence.", rule_class: "blocking", evidence_span_ids: ["SPAN-F42-LOC", "SPAN-F42-TIME", "SPAN-S118-LOC", "SPAN-S118-TIME"] }],
  contradictions_considered: ["CONFLICT-LOCATION-001"], rivals_considered: ["AID-209"], decision_critical_evidence: [], audit_chain_status: { valid: true, status: "verified" }, created_at: CREATED_AT, verifier_version: "threadline-evidence-contracts/2.0.0", rule_set_version: "threadline-contract-rules/3.0.0", safety_notice: safetyNotice,
  rule_results: ruleNames.map((name) => {
    const blocked = name === "MATERIAL_CONTRADICTIONS_RESOLVED";
    const warning = name === "TIMELINE_CONSISTENCY";
    return { rule_id: name, rule_name: name, rule_version: "1.0.0", rule_class: "blocking" as const, severity: blocked ? "critical" as const : warning ? "warning" as const : "information" as const, passed: !blocked && !warning, status: blocked ? "block" as const : warning ? "warn" as const : "pass" as const, reason_code: blocked ? "MATERIAL_CONTRADICTIONS_RESOLVED_BLOCKED" : warning ? "TIMELINE_GAP_REVIEW_REQUIRED" : `${name}_SATISFIED`, affected_claim_ids: blocked || warning ? [blocked ? "CLAIM-CONTRADICTION-LOCATION" : "CLAIM-TIMELINE-GAP"] : [], affected_evidence_span_ids: blocked ? ["SPAN-F42-LOC", "SPAN-F42-TIME", "SPAN-S118-LOC", "SPAN-S118-TIME"] : [], input_artifact_ids: blocked ? ["CLAIM-CONTRADICTION-LOCATION"] : [], related_source_span_ids: blocked ? ["SPAN-F42-LOC", "SPAN-F42-TIME", "SPAN-S118-LOC", "SPAN-S118-TIME"] : [], operator_explanation: blocked ? "The 20-minute Narin Quay–Hillcrest location conflict is material and unresolved." : warning ? "A 34-hour source interval remains incomplete." : "The deterministic requirement is satisfied.", remediation_guidance: blocked ? "Request an independent transport or custody record before any downstream release." : "No remediation required.", evaluation_timestamp: CREATED_AT, evaluator_version: "threadline-evidence-contracts/2.0.0" };
  }),
  candidate_ledger: { ledger_id: "LEDGER-CYCLONE-LEADING-001", case_id: CASE_ID, candidate_id: leading.candidate_id, supporting_claim_ids: ["CLAIM-NORMALIZED-NAME", "CLAIM-CONTACT-COMPATIBLE"], contradiction_claim_ids: ["CLAIM-CONTRADICTION-LOCATION"], timeline_claim_ids: ["CLAIM-TIMELINE-GAP"], compatibility_claim_ids: ["CLAIM-CONTACT-COMPATIBLE"], rival_comparison_claim_ids: ["CLAIM-RIVAL-COVERAGE"], missing_evidence: ["No independently timestamped movement evidence resolves the 18:20–18:40 location conflict.", "No custody or transport record covers the 34-hour interval."], required_follow_up_evidence: ["Transport manifest, custody log, or independently timestamped observation."], safety_notices: [safetyNotice], contract_result_ids: [...ruleNames] },
};

export const cycloneAuditEvents: AuditEvent[] = [
  ["01", "source ingested", "Six fictional records accepted from authorized synthetic sources."],
  ["02", "span validated", "All displayed quotations matched their half-open source offsets."],
  ["03", "claim extracted", "Source-linked facts retained original language and certainty."],
  ["04", "claim normalized", "Amira Saleh / Ameera Salih normalized additively; originals preserved."],
  ["05", "candidate ledger updated", "Leading and rival ledgers remained separately scoped."],
  ["06", "contract evaluation started", "Ten versioned deterministic rules entered evaluation."],
  ["07", "rule evaluated", "SOURCE_SPAN_INTEGRITY passed."],
  ["08", "rule evaluated", "MATERIAL_CONTRADICTIONS_RESOLVED blocked."],
  ["09", "release blocked", "No candidate classification left the release boundary."],
  ["10", "review opened", "Authorized review packet prepared; no disposition yet."],
  ["11", "evidence inspected", "Conflicting location spans opened side by side."],
].map(([suffix, action, detail], index) => ({ event_id: `AUDIT-CYCLONE-${suffix}`, timestamp: `2026-06-15T09:${String(index).padStart(2, "0")}:00Z`, actor: action === "review opened" || action === "evidence inspected" ? "Authorized demo reviewer" : "THREADLINE deterministic workflow", action, detail, event_type: action as AuditEvent["event_type"], workflow_version: "threadline-workflow/2.0.0", source_record_ids: ["FAMILY-042", "SHELTER-118"], before_value: index === 8 ? "contract_evaluating" : "append-only chain", after_value: action, reason: detail, origin: action === "review opened" || action === "evidence inspected" ? "human" : "machine" }));

export const cycloneReconstructionData: ReconstructionData = {
  locations: [
    { location_id: "narin", label: "Narin Quay", x: 74, y: 176, kind: "contradiction", record_ids: ["FAMILY-042", "EVAC-031"], description: "Family relay places the leading thread here at 18:20." },
    { location_id: "clinic", label: "East Levee Clinic", x: 188, y: 84, kind: "verified", record_ids: ["CLINIC-077"], description: "Point-of-care record at 08:15 on 13 June." },
    { location_id: "canal", label: "South Canal Camp", x: 320, y: 238, kind: "approximate", record_ids: ["WITNESS-064", "AID-209"], description: "Translated witness report and rival origin; certainty differs." },
    { location_id: "riverbend", label: "Riverbend Depot", x: 418, y: 106, kind: "contradiction", record_ids: ["AID-209", "EVAC-031"], description: "Rival registration at 17:55 conflicts with the family observation." },
    { location_id: "hillcrest", label: "Hillcrest School", x: 518, y: 190, kind: "contradiction", record_ids: ["SHELTER-118"], description: "Direct shelter intake at 18:40; no valid 20-minute transfer record exists." },
  ],
  events: [
    { event_id: "EVENT-EVAC", time: "12 Jun · 13:20", timestamp_kind: "exact", location_id: "narin", title: "Evacuation manifest fragment", description: "A. Salih boarded for Riverbend Depot.", record_ids: ["EVAC-031"], evidence_span_ids: ["SPAN-E31-TIME", "SPAN-E31-LOC"] },
    { event_id: "EVENT-CLINIC", time: "13 Jun · 08:15", timestamp_kind: "exact", location_id: "clinic", title: "Clinic treatment", description: "The last reliable event before a 34-hour interval.", record_ids: ["CLINIC-077"], evidence_span_ids: ["SPAN-C77-TIME", "SPAN-C77-LOC"] },
    { event_id: "EVENT-GAP", time: "34h gap", timestamp_kind: "missing", location_id: "canal", title: "Custody and movement unknown", description: "No source records the interval from clinic treatment to later observations.", record_ids: ["CLINIC-077", "WITNESS-064"], evidence_span_ids: ["SPAN-C77-TIME", "SPAN-W64-TIME"] },
    { event_id: "EVENT-RIVAL", time: "14 Jun · 17:55", timestamp_kind: "contradiction", location_id: "riverbend", title: "Rival aid registration", description: "AID-209 supports a rival explanation but conflicts geographically.", record_ids: ["AID-209"], evidence_span_ids: ["SPAN-A209-TIME", "SPAN-A209-LOC"] },
    { event_id: "EVENT-FAMILY", time: "14 Jun · 18:20", timestamp_kind: "contradiction", location_id: "narin", title: "Family-relayed observation", description: "Translated telephone relay; exact quoted value, translated certainty.", record_ids: ["FAMILY-042"], evidence_span_ids: ["SPAN-F42-TIME", "SPAN-F42-LOC"] },
    { event_id: "EVENT-SHELTER", time: "14 Jun · 18:40", timestamp_kind: "contradiction", location_id: "hillcrest", title: "Shelter intake", description: "Direct intake 20 minutes later; conflict remains material.", record_ids: ["SHELTER-118"], evidence_span_ids: ["SPAN-S118-TIME", "SPAN-S118-LOC"] },
  ],
  route_location_ids: ["clinic", "canal", "riverbend", "narin", "hillcrest"],
  estimated_travel_window: "12 Jun 13:20–14 Jun 18:40 · 34-hour undocumented interval",
  text_alternative: "The reconstruction starts at Narin Quay on 12 June, reaches East Levee Clinic on 13 June, then has a 34-hour missing interval. On 14 June the rival is recorded at Riverbend Depot at 17:55, a family relay places the leading thread at Narin Quay at 18:20, and shelter intake places it at Hillcrest School at 18:40. The last two locations cannot be reconciled with available transport evidence.",
};

export const cycloneCaseData: CaseData = {
  case_id: CASE_ID, workflow_run_id: RUN_ID, status: "review_required", mode: "mock", incident: { incident_id: "INCIDENT-CYCLONE-ILYRA", name: "Synthetic Cyclone Ilyra record-reconnection exercise", description: "Fictional records fragmented after a fictional cyclone in Maruva Bay.", languages: ["English", "Arabic"], simulation_label: "Synthetic data · no real people or locations" }, records: cycloneRecords, candidates: [leading, rival], evidence_contract: contract, evidence_contracts: [contract], contract_release_status: "withheld", release_state: { state: "contract_blocked", contract_ids: [contract.contract_id], blocking_rule_ids: ["MATERIAL_CONTRADICTIONS_RESOLVED"], authorized_review_required: true }, workflow_trace: workflowNodes, audit_events: cycloneAuditEvents, summary: { records_processed: 6, languages_detected: 2, candidate_connections: 2, awaiting_human_review: 1, hard_conflicts: 2, quarantined_instructions: 0 }, safety_notices: [safetyNotice], human_review_requirement: "An authorized reviewer must record a structured disposition; THREADLINE cannot make an identity decision.", audit_integrity: { workflow_run_id: RUN_ID, status: "verified", valid: true, first_invalid_event_id: null, first_invalid_sequence: null, expected_previous_hash: null, observed_previous_hash: null, expected_payload_hash: null, observed_payload_hash: null, expected_event_hash: null, observed_event_hash: null, missing_sequence_numbers: [], duplicated_sequence_numbers: [], verified_event_count: cycloneAuditEvents.length, terminal_hash: "sha256:cyclone-demo-terminal", hash_algorithm: "sha256", verifier_version: "threadline-audit-verifier/1.0.0", limitation: "Tamper evidence detects changes; it does not prevent offline database modification." },
};

export const cycloneWorkflowTraces: WorkflowNodeTrace[] = workflowNodes.map((node, index) => ({ node_id: node.node_id, node_version: "threadline-node/2.0.0", input_record_ids: cycloneRecords.map((item) => item.record_id), input_schema: `${node.node_id}/input`, prompt_template: node.method === "Configured LLM" ? "Use only cited evidence spans; preserve source certainty." : "Not applicable — deterministic or human step.", prompt_variables: {}, configured_model: node.method === "Configured LLM" ? "Configured LLM" : "Not applicable", structured_output: node.node_id === "prosecutor" ? "Material Narin Quay–Hillcrest contradiction retained." : node.node_id === "rivals" ? "AID-209 retained as a credible rival." : node.node_id === "review" ? "Authorized checkpoint open; no autonomous disposition." : node.output, output_schema: `${node.node_id}/output`, deterministic_checks: node.constraints, evidence_span_ids: index > 4 ? ["SPAN-F42-LOC", "SPAN-S118-LOC"] : ["SPAN-F42-NAME", "SPAN-S118-NAME"], warnings: node.node_id === "timeline" ? ["34-hour interval has no custody or transport record."] : [], failure_conditions: [node.failure_condition], abstention_reason: node.node_id === "adjudicate" ? "Material contradiction prevents release." : null, duration: { value: null, label: "Deterministic fixture" }, token_usage: { value: null, label: "No paid generation" }, estimated_cost: { value: 0, label: "0 credits" }, next_node: workflowNodes[index + 1]?.node_id ?? null, human_review_requirement: node.human_input_requirement, before_state: node.input, after_state: node.output }));
