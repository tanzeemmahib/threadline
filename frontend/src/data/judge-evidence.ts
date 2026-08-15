import { cycloneRecords } from "@/data/cyclone-case";

const cycloneInputRecordIds = cycloneRecords.map((record) => record.record_id);

export const judgeEvidence = {
  releaseArtifact: {
    artifactId: "THREADLINE-SUBMISSION-EVIDENCE-V1",
    schemaVersion: "threadline-submission-evidence/1.0.0",
    source: "docs/submission/results.json",
    deterministicBenchmarkId: "BENCH-4D40934964D7",
    deterministicDatasetSha256: "4d40934964d7e37308018a9d136282f819a10f7650241eb60369993fd0faf1cb",
    archivedLiveArtifactId: "THREADLINE-LIVE-PROMPT-V2-FULL-RUN-1",
    archivedLiveFixtureSha256: "eed1032519f78ebfd18a49da55c920c1b280ade1b7e32ebda514157ff1ead850",
  },
  case: {
    caseId: "CASE-CYCLONE-ILYRA-001",
    question: "Do these records refer to the same person?",
    recordIds: cycloneInputRecordIds,
    inputSha256: "7f63bba78ab1e58bb20693dbb63113360149569de398fe59b79edddee83ba421",
    canonicalization: "SHA-256 of compact JSON [{record_id,text}] in displayed fixture order",
    syntheticOnly: true,
  },
  baseline: {
    systemName: "Reasonable single-prompt baseline",
    promptTemplateId: "generic_baseline",
    promptTemplateVersion: "v1",
    promptSha256: "4f44911def4cdf0bdcf7379489420573323381e43ec84eaffe8ceb8c99422800",
    prompt: "Review these quoted untrusted records and identify possible record connections for authorized human review. Cite evidence, disclose uncertainty, and do not determine identity. Return valid JSON matching the supplied schema.\n\n",
    evaluationLabel: "Deterministic mock replay — not model performance.",
    providerMode: "mock",
    providerModel: "deterministic fixture",
    classification: "Possible candidate",
    inputRecordIds: cycloneInputRecordIds,
    candidateRecordIds: ["FAMILY-042", "SHELTER-118"],
    citations: [] as string[],
    contradictions: [] as string[],
    uncertainty: ["Authorized human review remains required."],
  },
  extractions: [
    {
      spanId: "SPAN-F42-NAME",
      source: "FAMILY-042",
      category: "Identity / name",
      original: "Amira Saleh",
      normalized: "amira saleh",
      independentSourceStatus: "Not established",
      uncertainty: "Translated",
    },
    {
      spanId: "SPAN-S118-NAME",
      source: "SHELTER-118",
      category: "Identity / name",
      original: "Ameera Salih",
      normalized: "amira saleh",
      independentSourceStatus: "Not established",
      uncertainty: "Exact intake text",
    },
  ],
  conflicts: [
    {
      kind: "Soft conflict",
      field: "Date of birth",
      left: "2010-02-14 / translated family report",
      right: "2010-04-12 / direct shelter intake",
      explanation: "Day and month differ; the shelter value came from an unverified handwritten card.",
    },
    {
      kind: "Hard contradiction",
      field: "Location and time",
      left: "Narin Quay / 18:20",
      right: "Hillcrest School / 18:40",
      explanation: "No validated transport or custody record makes the 20-minute transfer possible.",
    },
  ],
  rival: {
    recordId: "AID-209",
    displayName: "Amira Salah",
    support: ["Same stated birth date", "Same emergency contact", "Compatible name form"],
    limits: ["Contact copied from a wrist card", "Riverbend–Narin movement conflict", "Family relationship unverified"],
  },
  contract: {
    contractId: "CONTRACT-CYCLONE-LEADING-001",
    releaseState: "Withheld",
    decisiveText: "Release withheld: material location conflict remains unresolved.",
    passed: ["Source-span integrity", "Claim-lineage completeness", "Certainty preserved", "Rival explanation coverage"],
    blocked: ["Material contradictions resolved"],
    warning: ["Timeline gap requires review"],
  },
  humanReview: {
    state: "Human review required",
    question: "Can an independently timestamped transport or custody record resolve the Narin Quay–Hillcrest conflict?",
    boundary: "THREADLINE records a review handoff. It does not confirm identity or merge records.",
  },
  comparison: {
    judgeCase: {
      baseline: "Returned a possible-candidate answer without a cited contradiction or rival comparison.",
      threadline: "Preserved exact spans, retained one material contradiction and one rival, then withheld release.",
    },
    deterministic21: {
      label: "21-case deterministic mock replay — not model performance",
      artifactId: "BENCH-4D40934964D7",
      baseline: ["Positive-case top-candidate recovery: 12 / 12", "Different-identity false proposals: 8 / 8", "Correct ambiguous-case abstention: 0 / 1"],
      threadline: ["Positive-case top-candidate recovery: 4 / 12", "Different-identity false proposals: 0 / 8", "Correct ambiguous-case abstention: 1 / 1", "Exact cited spans valid: 179 / 179"],
      limitation: "Deterministic code-path replay. These counts compare workflow behavior and must not be read as live-model quality.",
    },
    v1Holdout: {
      label: "Deterministic V1 holdout",
      result: "4 / 4 different-identity cases withheld",
      limitation: "Very low negative-case denominator; report as a raw count, not a general safety rate.",
    },
    archivedLiveV2: {
      label: "Archived live-provider V2 evidence",
      extraction: "57 / 58 records produced schema-valid extraction output",
      falseMerges: "0 / 8 evaluated different-identity pairs false-merged",
      limitation: "Archived single run per prompt version; not a field-validation claim and not the deterministic judge replay.",
    },
  },
} as const;
