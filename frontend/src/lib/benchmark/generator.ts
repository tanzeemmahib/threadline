import type {
  BenchmarkComposition,
  GeneratedSyntheticRecord,
  SourceType,
  SyntheticBenchmarkConfig,
} from "@/types";

export const defaultBenchmarkConfig: SyntheticBenchmarkConfig = {
  seed: 41027,
  identities: 12,
  records_per_identity: 3,
  languages: ["English", "Arabic", "French"],
  transliteration_severity: 35,
  spelling_corruption: 12,
  missing_field_percentage: 24,
  estimated_age_variance: 2,
  changed_location_frequency: 30,
  duplicate_record_frequency: 8,
  contradictory_timestamp_frequency: 10,
  rival_candidate_count: 2,
  prompt_injection_frequency: 5,
  common_name_frequency: 18,
};

const names = [
  { English: "Youssef Al Hassan", Arabic: "يوسف الحسن", French: "Youssef Al Hassan" },
  { English: "Mina Darzi", Arabic: "مينا درزي", French: "Mina Darzi" },
  { English: "Amal Rafiq", Arabic: "أمل رفيق", French: "Amal Rafiq" },
  { English: "Samir Nader", Arabic: "سمير نادر", French: "Samir Nader" },
  { English: "Lina Haddad", Arabic: "لينا حداد", French: "Lina Haddad" },
  { English: "Karim Mansour", Arabic: "كريم منصور", French: "Karim Mansour" },
] as const;

const sourceTypes: SourceType[] = [
  "family_report",
  "shelter_record",
  "hospital_intake",
  "evacuation_log",
  "translated_phone_submission",
  "volunteer_note",
];

function seededUnit(seed: number, index: number) {
  let value = (seed ^ (index * 2654435761)) >>> 0;
  value = Math.imul(value ^ (value >>> 16), 2246822507) >>> 0;
  value = Math.imul(value ^ (value >>> 13), 3266489909) >>> 0;
  return ((value ^ (value >>> 16)) >>> 0) / 4294967296;
}

function occurs(percent: number, seed: number, index: number) {
  return seededUnit(seed, index) * 100 < percent;
}

function corruptName(value: string, severity: number, seed: number, index: number) {
  if (severity === 0 || value.length < 5 || !occurs(severity, seed, index)) return value;
  const position = 1 + Math.floor(seededUnit(seed, index + 17) * (value.length - 2));
  return `${value.slice(0, position)}${value.slice(position + 1)}`;
}

export function generateSyntheticBenchmark(config: SyntheticBenchmarkConfig): {
  records: GeneratedSyntheticRecord[];
  composition: BenchmarkComposition;
} {
  const records: GeneratedSyntheticRecord[] = [];
  const fields = ["name", "age", "language", "location", "timestamp", "clothing", "distinctive_feature"];

  for (let identityIndex = 0; identityIndex < config.identities; identityIndex += 1) {
    const identityId = `SYN-ID-${String(identityIndex + 1).padStart(3, "0")}`;
    for (let recordIndex = 0; recordIndex < config.records_per_identity; recordIndex += 1) {
      const index = identityIndex * config.records_per_identity + recordIndex;
      const language = config.languages[index % config.languages.length] ?? "English";
      const nameSet = names[identityIndex % names.length];
      const baseName = nameSet[language];
      const flags: string[] = [];

      if (occurs(config.transliteration_severity, config.seed, index + 101) && language !== "Arabic") flags.push("transliteration variant");
      if (occurs(config.spelling_corruption, config.seed, index + 202)) flags.push("spelling corruption");
      if (occurs(config.changed_location_frequency, config.seed, index + 303)) flags.push("changed location");
      if (config.estimated_age_variance > 0 && occurs(45, config.seed, index + 313)) flags.push(`estimated age ±${config.estimated_age_variance}`);
      if (occurs(config.duplicate_record_frequency, config.seed, index + 404)) flags.push("duplicate record");
      if (occurs(config.contradictory_timestamp_frequency, config.seed, index + 505)) flags.push("contradictory timestamp");
      if (occurs(config.prompt_injection_frequency, config.seed, index + 606)) flags.push("embedded instruction");
      if (occurs(config.common_name_frequency, config.seed, index + 707)) flags.push("common name");
      if (recordIndex === 0 && config.rival_candidate_count > 0) flags.push(`${config.rival_candidate_count} configured rivals`);

      const fieldsPresent = fields.filter((_, fieldIndex) => !occurs(config.missing_field_percentage, config.seed, index * 11 + fieldIndex));
      records.push({
        record_id: `SYN-REC-${String(index + 1).padStart(4, "0")}`,
        fictional_identity_id: identityId,
        language,
        display_name: corruptName(baseName, config.spelling_corruption, config.seed, index + 808),
        source_type: sourceTypes[index % sourceTypes.length],
        fields_present: fieldsPresent,
        flags,
      });
    }
  }

  const total = records.length;
  const positivePairsPerIdentity = (config.records_per_identity * (config.records_per_identity - 1)) / 2;
  const positivePairs = config.identities * positivePairsPerIdentity;
  const allPairs = (total * (total - 1)) / 2;
  const ambiguousCases = records.filter((record) => record.flags.includes("common name") || record.flags.some((flag) => flag.includes("configured rivals")) || record.fields_present.length <= 3).length;
  const hardCases = records.filter((record) => record.flags.some((flag) => ["contradictory timestamp", "transliteration variant", "embedded instruction"].includes(flag))).length;

  return {
    records,
    composition: {
      identities: config.identities,
      total_records: total,
      languages: config.languages.length,
      positive_record_pairs: positivePairs,
      negative_record_pairs: Math.max(0, allPairs - positivePairs),
      ambiguous_cases: ambiguousCases,
      injected_records: records.filter((record) => record.flags.includes("embedded instruction")).length,
      hard_cases: hardCases,
    },
  };
}
