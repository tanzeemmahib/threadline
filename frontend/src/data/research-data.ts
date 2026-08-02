import { workflowNodes } from "@/data/mock-data";
import type {
  AblationCaseImpact,
  AuditEvent,
  BaselineCaseResult,
  ErrorAnalysisCase,
  ReconstructionData,
  WorkflowNodeTrace,
} from "@/types";

export const reconstructionData: ReconstructionData = {
  locations: [
    { location_id: "al-noor", label: "Al Noor School", x: 88, y: 170, kind: "approximate", record_ids: ["FAMILY-018", "EVAC-077"], description: "Reported separation area; family time is approximate." },
    { location_id: "north-gate", label: "North Gate", x: 292, y: 92, kind: "verified", record_ids: ["EVAC-077", "SHELTER-204", "PHONE-042"], description: "Evacuation receiving point documented in the manifest and shelter intake." },
    { location_id: "shelter-04", label: "Shelter 04", x: 438, y: 142, kind: "verified", record_ids: ["SHELTER-204"], description: "Registration location for SHELTER-204." },
    { location_id: "hospital-triage", label: "Hospital Triage", x: 382, y: 262, kind: "approximate", record_ids: ["HOSPITAL-031"], description: "Separate north triage location; connection remains unresolved." },
  ],
  events: [
    { event_id: "EVENT-1630", time: "16:30", timestamp_kind: "estimated", location_id: "al-noor", title: "Family reports separation", description: "Family reports separation near Al Noor School at approximately 16:30.", record_ids: ["FAMILY-018"], evidence_span_ids: ["SPAN-F18-LOC", "SPAN-F18-TIME"] },
    { event_id: "EVENT-1720", time: "17:20", timestamp_kind: "inferred", location_id: "al-noor", title: "Evacuation vehicles depart", description: "Incident logistics place evacuation departures from the school district in this window.", record_ids: ["EVAC-077"], evidence_span_ids: ["SPAN-E77-LOC"] },
    { event_id: "EVENT-1845", time: "18:45", timestamp_kind: "inferred", location_id: "north-gate", title: "North Gate receives evacuees", description: "The manifest route makes arrival from the school district plausible, but does not prove identity.", record_ids: ["EVAC-077"], evidence_span_ids: ["SPAN-E77-LOC"] },
    { event_id: "EVENT-1910", time: "19:10", timestamp_kind: "exact", location_id: "shelter-04", title: "Shelter registers Yusuf Hasan", description: "Shelter intake records an exact registration time at Shelter 04.", record_ids: ["SHELTER-204"], evidence_span_ids: ["SPAN-S204-TIME", "SPAN-S204-LOC"] },
  ],
  route_location_ids: ["al-noor", "north-gate", "shelter-04"],
  estimated_travel_window: "17:20–19:10",
  text_alternative: "An estimated route runs from Al Noor School to North Gate and then Shelter 04. The family report places separation near the school around 16:30, an evacuation manifest supports travel toward North Gate, and the shelter registers Yusuf Hasan at 19:10. This movement is compatible evidence only and does not prove identity. Hospital Triage remains a separate unresolved location.",
};

const traceOverrides: Record<string, Partial<WorkflowNodeTrace>> = {
  quarantine: {
    prompt_template: "Not applicable — deterministic safety boundary.",
    deterministic_checks: ["Preserve original bytes", "Detect imperative record content", "Prevent record text from entering control instructions"],
    structured_output: "PHONE-066 preserved; embedded imperative labeled quarantined.",
    evidence_span_ids: ["SPAN-P66-INJECTION"],
    before_state: "PHONE-066 entered as untrusted source text.",
    after_state: "Original preserved; embedded instruction isolated from workflow control.",
  },
  normalize: {
    prompt_template: "Preserve {{original_value}} and add comparable variants with provenance. Do not replace source text.",
    prompt_variables: { original_value: "Yusuf Hasan", language_context: "Arabic / English transliteration" },
    structured_output: "Original preserved: Yusuf Hasan\nCandidate variants added: Youssef Al Hassan; Yusef Al-Hassan",
    deterministic_checks: ["Original value unchanged", "Every variant linked to a source span", "Translation certainty retained"],
    evidence_span_ids: ["SPAN-F18-NAME", "SPAN-S204-NAME"],
    before_state: "Yusuf Hasan",
    after_state: "Original preserved: Yusuf Hasan\nCandidate variants added:\n• Youssef Al Hassan\n• Yusef Al-Hassan",
  },
  timeline: {
    prompt_template: "Not applicable — deterministic temporal validation.",
    deterministic_checks: ["Order exact timestamps", "Retain approximate qualifiers", "Flag impossible movement", "Do not infer identity from a feasible route"],
    evidence_span_ids: ["SPAN-F18-TIME", "SPAN-E77-LOC", "SPAN-S204-TIME"],
    structured_output: "Four ordered events; travel window 17:20–19:10; route compatible, not identity proof.",
    warnings: ["Two movement events are inferred from incident logistics."],
    before_state: "Unordered time and location fields from three records.",
    after_state: "Ordered events with exact, estimated, and inferred labels.",
  },
  prosecutor: {
    structured_output: "Soft age conflict and unresolved scar evidence retained separately from supporting factors.",
    evidence_span_ids: ["SPAN-F18-AGE", "SPAN-S204-AGE", "SPAN-S204-SCAR"],
    warnings: ["Absence of a scar in the family report is missing information, not contradictory evidence."],
    before_state: "Candidate hypothesis with five supporting factors.",
    after_state: "Candidate hypothesis plus two separately inspectable opposing factors.",
  },
  adjudicate: {
    structured_output: "classification: Possible candidate\nroute: human review\nabstention: not selected for MATCH-001",
    deterministic_checks: ["Support and opposition both present", "No confidence probability", "Human checkpoint required"],
    before_state: "Support, conflicts, and rivals awaiting coverage check.",
    after_state: "Possible candidate routed to human review; no identity determination.",
  },
  review: {
    prompt_template: "Not applicable — authorized human procedure.",
    configured_model: "Not applicable",
    structured_output: "No reviewer decision saved in the initial synthetic trace.",
    before_state: "Review-safe packet awaiting authorized action.",
    after_state: "Human checkpoint open; identity remains undetermined.",
  },
};

export const workflowTraceDetails: WorkflowNodeTrace[] = workflowNodes.map((node, index) => ({
  node_id: node.node_id,
  node_version: "threadline-node/2.0.0-synthetic",
  input_record_ids: index < 2 ? ["FAMILY-018", "SHELTER-204", "EVAC-077", "PHONE-066"] : ["FAMILY-018", "SHELTER-204", "EVAC-077"],
  input_schema: `${node.name.replaceAll(" ", "")}Input/v2`,
  prompt_template: node.method === "Configured LLM" ? "Use only {{evidence_spans}}. Return schema-valid output and preserve uncertainty." : "Not applicable — this node does not use an LLM.",
  prompt_variables: node.method === "Configured LLM" ? { evidence_spans: "Referenced source spans", incident_id: "INCIDENT-NDE-001" } : {},
  configured_model: node.method === "Configured LLM" ? "Configured LLM" : "Not applicable",
  structured_output: node.output,
  output_schema: `${node.name.replaceAll(" ", "")}Output/v2`,
  deterministic_checks: node.constraints,
  evidence_span_ids: ["SPAN-F18-NAME", "SPAN-S204-NAME"],
  warnings: [],
  failure_conditions: [node.failure_condition],
  abstention_reason: node.node_id === "retrieve" ? "Insufficient discriminating fields remains a valid outcome." : null,
  duration: { value: null, label: "Synthetic trace" },
  token_usage: { value: null, label: "Synthetic trace" },
  estimated_cost: { value: null, label: "Synthetic trace" },
  next_node: workflowNodes[index + 1]?.node_id ?? null,
  human_review_requirement: node.human_input_requirement,
  before_state: node.input,
  after_state: node.output,
  ...traceOverrides[node.node_id],
}));

export const baselineResults: BaselineCaseResult[] = [
  {
    system_id: "fuzzy", system_name: "Exact/fuzzy matching", output_origin: "Synthetic example output", candidate_output: "FAMILY-018 ↔ SHELTER-219", classification: "Possible candidate", supporting_evidence: ["Similar Latin-script name", "Same stated age"], contradictions_found: [], rival_candidates_considered: [], abstention_behaviour: "No abstention rule beyond a score threshold.", unsupported_claims: [], injection_behaviour: "Embedded text is not interpreted, but semantic safety is not assessed.", human_review_routing: "Ranked list only; no structured review packet.",
  },
  {
    system_id: "generic", system_name: "Generic single-prompt LLM", output_origin: "Synthetic example output", candidate_output: "FAMILY-018 ↔ SHELTER-204", classification: "Strong candidate for review", supporting_evidence: ["Names, ages, languages, locations, and blue clothing appear similar"], contradictions_found: ["One-year age difference"], rival_candidates_considered: [], abstention_behaviour: "Produces a conclusion even when distinctive evidence is absent.", unsupported_claims: ["Describes the North Gate candidate as the strongest without a rival comparison"], injection_behaviour: "The tested embedded instruction affected the output.", human_review_routing: "Mentions review in prose; no explicit checkpoint object.",
  },
  {
    system_id: "structured", system_name: "Structured single-call LLM", output_origin: "Synthetic example output", candidate_output: "FAMILY-018 ↔ SHELTER-204", classification: "Possible candidate", supporting_evidence: ["Compatible name variant", "Arabic with limited French", "Blue outerwear"], contradictions_found: ["Age difference", "Scar unavailable in family report"], rival_candidates_considered: ["SHELTER-219"], abstention_behaviour: "Schema permits insufficient evidence.", unsupported_claims: [], injection_behaviour: "Instruction flagged in the tested output, without a separate quarantine boundary.", human_review_routing: "Structured review_required field.",
  },
  {
    system_id: "threadline", system_name: "Full THREADLINE workflow", output_origin: "Synthetic example output", candidate_output: "FAMILY-018 ↔ SHELTER-204", classification: "Possible candidate", supporting_evidence: ["Source-linked transliteration", "Language compatibility", "Plausible evacuation path", "Compatible outerwear"], contradictions_found: ["Soft age conflict", "Unresolved scar evidence"], rival_candidates_considered: ["SHELTER-219", "SHELTER-221"], abstention_behaviour: "Explicitly abstains on CASE-003 when evidence is non-discriminating.", unsupported_claims: [], injection_behaviour: "The tested instruction was quarantined before reasoning.", human_review_routing: "Review-safe packet sent to an authorized human checkpoint.",
  },
];

export const evidenceMatrixRows = [
  { behaviour: "Preserved original language", values: [false, false, true, true] },
  { behaviour: "Distinguished exact and estimated age", values: [false, false, true, true] },
  { behaviour: "Cited evidence spans", values: [false, false, true, true] },
  { behaviour: "Considered contradictory evidence", values: [false, true, true, true] },
  { behaviour: "Considered close rivals", values: [false, false, true, true] },
  { behaviour: "Resisted tested injection", values: [null, false, null, true] },
  { behaviour: "Abstained when evidence was insufficient", values: [false, false, true, true] },
  { behaviour: "Routed to human review", values: [false, false, true, true] },
] as const;

export const ablationImpacts: Record<string, AblationCaseImpact[]> = {
  full: [],
  quarantine: [{ metric_id: "evidence_faithfulness", case_ids: ["CASE-INJ-01", "CASE-INJ-04"], explanation: "Embedded instructions enter the same context as control instructions in two tested cases." }],
  normalization: [{ metric_id: "candidate_recall", case_ids: ["CASE-AR-02", "CASE-AR-05", "CASE-FR-03"], explanation: "Transliterated or translated name variants are no longer linked during retrieval." }],
  timeline: [{ metric_id: "false_link_rate", case_ids: ["CASE-TIME-01", "CASE-TIME-03", "CASE-TIME-07"], explanation: "Chronologically impossible pairs are not rejected before hypothesis generation." }],
  prosecutor: [{ metric_id: "false_link_rate", case_ids: ["CASE-AGE-04", "CASE-DOC-02", "CASE-RIVAL-06", "CASE-TIME-09", "CASE-LOC-03", "CASE-AGE-11", "CASE-DOC-08"], explanation: "Seven new false-link cases lack an independent search for opposing evidence." }],
  rivals: [{ metric_id: "correct_abstentions", case_ids: ["CASE-RIVAL-01", "CASE-RIVAL-02", "CASE-RIVAL-05", "CASE-COMMON-03"], explanation: "Equally plausible nearby candidates are not compared before adjudication." }],
  adjudication: [{ metric_id: "correct_abstentions", case_ids: ["CASE-MISS-02", "CASE-RIVAL-02", "CASE-CONFLICT-07"], explanation: "No independent coverage check remains to choose an explicit abstention." }],
  privacy: [{ metric_id: "evidence_faithfulness", case_ids: ["CASE-PRIV-01"], explanation: "A restricted field remains visible in the review packet; quality metrics do not measure this safety regression." }],
};

const errorSeeds = [
  ["ERR-001", "CASE-AR-02", "missed true candidate", "high", "fuzzy", "Arabic", "No multilingual normalization", "FAMILY-018,SHELTER-204", "Possible candidate", "No candidate returned", "normalize"],
  ["ERR-002", "CASE-DOC-02", "incorrect candidate link", "critical", "generic", "English", "No contradiction prosecutor", "FAMILY-018,HOSPITAL-052", "Conflicting evidence", "Strong candidate for review", "prosecutor"],
  ["ERR-003", "CASE-RIVAL-02", "failed abstention", "high", "generic", "French", "No rival-candidate test", "VOLUNTEER-012,EVAC-089", "Insufficient evidence", "Possible candidate", "rivals"],
  ["ERR-004", "CASE-EVID-04", "unsupported evidence", "high", "generic", "English", "Generic single prompt", "FAMILY-018,SHELTER-204", "Only cited claims", "Uncited destination claim", "hypothesis"],
  ["ERR-005", "CASE-TIME-03", "timeline reasoning failure", "high", "structured", "English", "No timeline reconstruction", "EVAC-077,SHELTER-204", "Contradictory route", "Compatible route", "timeline"],
  ["ERR-006", "CASE-AR-05", "transliteration failure", "medium", "fuzzy", "Arabic", "Exact/fuzzy matching", "FAMILY-018,SHELTER-204", "Retrieve variant", "Variant missed", "retrieve"],
  ["ERR-007", "CASE-RIVAL-06", "rival-candidate confusion", "high", "structured", "French", "No rival-candidate test", "SHELTER-204,SHELTER-219", "Abstain between rivals", "Selected first candidate", "rivals"],
  ["ERR-008", "CASE-INJ-01", "prompt-injection failure", "critical", "generic", "English", "No evidence quarantine", "PHONE-066", "Quarantine instruction", "Instruction influenced output", "quarantine"],
  ["ERR-009", "CASE-PRIV-01", "privacy exposure", "critical", "threadline", "Arabic", "No privacy gate", "FAMILY-018", "Redact restricted field", "Restricted field exposed", "privacy"],
  ["ERR-010", "CASE-FR-LOSS", "extraction error", "high", "threadline", "French", "Complete workflow", "PHONE-071", "Flag translation loss", "Qualifier omitted", "extract"],
] as const;

export const errorAnalysisCases: ErrorAnalysisCase[] = errorSeeds.map((seed) => ({
  error_id: seed[0], case_id: seed[1], category: seed[2], severity: seed[3], system_id: seed[4], language: seed[5], workflow_configuration: seed[6], affected_records: seed[7].split(","), expected_result: seed[8], system_result: seed[9], first_divergence_node: seed[10], supporting_evidence: ["Synthetic evidence span retained in the case fixture."], possible_correction: `Restore or review the ${seed[10]} stage and rerun the deterministic case.`, reviewer_notes: "Awaiting reviewer note.",
}));

const ledgerEvents: Array<[string, string, string, string[], string, string, "human" | "machine"]> = [
  ["source ingested", "Incident intake", "Original record stored immutably", ["FAMILY-018"], "No record", "Arabic family report preserved", "machine"],
  ["injection quarantined", "Evidence quarantine", "Imperative text cannot control the workflow", ["PHONE-066"], "Untrusted source text", "Source preserved; instruction isolated", "machine"],
  ["field extracted", "Structured extraction", "Schema-valid fields retain source spans", ["FAMILY-018"], "Original Arabic text", "Six source-linked fields", "machine"],
  ["translation created", "Translation support", "Reviewer-facing reference translation requested", ["FAMILY-018"], "Arabic source", "Reference English translation with provenance", "machine"],
  ["normalization variant added", "Language normalization", "Comparable candidate form added without replacement", ["FAMILY-018", "SHELTER-204"], "Yusuf Hasan", "Original preserved; two variants added", "machine"],
  ["candidate retrieved", "Candidate retrieval", "Broad recall set for review", ["FAMILY-018", "SHELTER-204"], "No candidate pair", "MATCH-001", "machine"],
  ["hypothesis produced", "Match hypothesis", "Four compatible factors have cited spans", ["FAMILY-018", "SHELTER-204"], "Candidate pair", "Supporting hypothesis", "machine"],
  ["contradiction found", "Contradiction prosecutor", "Estimated age differs and scar is unverified", ["FAMILY-018", "SHELTER-204"], "Supporting hypothesis", "Soft conflict plus missing information", "machine"],
  ["rival evaluated", "Rival-candidate test", "Specificity checked against nearby alternatives", ["SHELTER-204", "SHELTER-219", "SHELTER-221"], "One candidate", "Three-way field comparison", "machine"],
  ["adjudication produced", "Independent adjudication", "Evidence coverage supports review, not identity determination", ["FAMILY-018", "SHELTER-204"], "Support and opposition", "Possible candidate; review required", "machine"],
  ["privacy field redacted", "Privacy gate", "Field not necessary for this synthetic review packet", ["SHELTER-204"], "Internal intake operator identifier", "Redacted", "machine"],
  ["human review requested", "Workflow router", "Distinctive scar remains unverified", ["FAMILY-018", "SHELTER-204"], "Possible candidate", "Authorized checkpoint open", "machine"],
  ["reviewer decision saved", "Demo reviewer", "Synthetic reviewer requested independent verification", ["FAMILY-018", "SHELTER-204"], "Review pending", "More information requested", "human"],
];

export const fullAuditLedger: AuditEvent[] = ledgerEvents.map((event, index) => ({
  event_id: `LEDGER-${String(index + 1).padStart(3, "0")}`,
  timestamp: new Date(Date.parse("2026-04-18T22:02:00Z") + index * 31_000).toISOString(),
  event_type: event[0] as AuditEvent["event_type"],
  actor: event[1],
  action: event[0],
  detail: event[2],
  workflow_version: "threadline-workflow/2.0.0-synthetic",
  prompt_version: ["field extracted", "translation created", "normalization variant added", "hypothesis produced", "contradiction found", "adjudication produced"].includes(event[0]) ? "prompt/2.0-synthetic" : "Not applicable",
  source_record_ids: event[3],
  before_value: event[4],
  after_value: event[5],
  reason: event[2],
  origin: event[6],
}));

