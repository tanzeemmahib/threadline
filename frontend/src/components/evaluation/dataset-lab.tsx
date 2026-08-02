"use client";

import { useMemo, useRef, useState } from "react";
import { useEvaluationSession } from "@/components/evaluation/evaluation-session";
import { FALLBACK_NOTICE, MOCK_EVALUATION_LABEL, threadlineService } from "@/lib/api/client";
import { defaultBenchmarkConfig, generateSyntheticBenchmark } from "@/lib/benchmark/generator";
import type { SyntheticBenchmarkConfig } from "@/types";

const rangeControls: Array<{ key: keyof SyntheticBenchmarkConfig; label: string; min: number; max: number; step?: number; suffix?: string }> = [
  { key: "identities", label: "Fictional identities", min: 3, max: 50 },
  { key: "records_per_identity", label: "Records per identity", min: 2, max: 8 },
  { key: "transliteration_severity", label: "Transliteration severity", min: 0, max: 100, suffix: "%" },
  { key: "spelling_corruption", label: "Spelling corruption", min: 0, max: 100, suffix: "%" },
  { key: "missing_field_percentage", label: "Missing fields", min: 0, max: 90, suffix: "%" },
  { key: "estimated_age_variance", label: "Estimated-age variance", min: 0, max: 8, suffix: " years" },
  { key: "changed_location_frequency", label: "Changed-location frequency", min: 0, max: 100, suffix: "%" },
  { key: "duplicate_record_frequency", label: "Duplicate-record frequency", min: 0, max: 60, suffix: "%" },
  { key: "contradictory_timestamp_frequency", label: "Contradictory timestamps", min: 0, max: 60, suffix: "%" },
  { key: "rival_candidate_count", label: "Rival candidates", min: 0, max: 6 },
  { key: "prompt_injection_frequency", label: "Prompt-injection frequency", min: 0, max: 50, suffix: "%" },
  { key: "common_name_frequency", label: "Common-name frequency", min: 0, max: 80, suffix: "%" },
];

function downloadJson(filename: string, value: unknown) {
  const blob = new Blob([JSON.stringify(value, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function DatasetLab() {
  const [config, setConfig] = useState(defaultBenchmarkConfig);
  const { dataset, setDataset, setBenchmark } = useEvaluationSession();
  const [backendState, setBackendState] = useState("Backend dataset not generated.");
  const [busy, setBusy] = useState<"generate" | "benchmark" | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const generated = useMemo(() => generateSyntheticBenchmark(config), [config]);

  function updateNumber(key: keyof SyntheticBenchmarkConfig, value: number) {
    setConfig((current) => ({ ...current, [key]: value }));
  }

  function toggleLanguage(language: "English" | "Arabic" | "French") {
    setConfig((current) => {
      const selected = current.languages.includes(language);
      if (selected && current.languages.length === 1) return current;
      return { ...current, languages: selected ? current.languages.filter((item) => item !== language) : [...current.languages, language] };
    });
  }

  async function generateBackendDataset() {
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy("generate");
    setBackendState("Generating and persisting the deterministic backend dataset…");
    try {
      const value = await threadlineService.generateBenchmark(config, { signal: controller.signal });
      setDataset(value);
      setBenchmark(null);
      setBackendState(`${MOCK_EVALUATION_LABEL} · ${value.benchmark_id} · hash ${value.content_hash.slice(0, 12)}…`);
    } catch {
      setBackendState(FALLBACK_NOTICE);
    } finally {
      setBusy(null);
    }
  }

  async function runBackendBenchmark() {
    if (!dataset) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy("benchmark");
    setBackendState("Running four systems against persisted ground truth…");
    try {
      const value = await threadlineService.runBenchmark({ dataset, provider_mode: "mock", candidate_k: 5 }, { signal: controller.signal });
      setBenchmark(value);
      setBackendState(`${MOCK_EVALUATION_LABEL} · ${value.benchmark_run_id}`);
    } catch {
      setBackendState(FALLBACK_NOTICE);
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="research-lab-section" id="dataset-lab" aria-labelledby="dataset-lab-title">
      <header className="research-section-heading"><div><p className="eyebrow">Crisis dataset laboratory</p><h2 className="section-title" id="dataset-lab-title">Build a deterministic fictional benchmark.</h2></div><p>Fixed seed {config.seed}. Settings generate local templates only; the browser never calls an LLM.</p></header>
      <div className="dataset-lab-grid">
        <form className="dataset-controls" onSubmit={(event) => event.preventDefault()}>
          <fieldset><legend>Languages</legend><div className="checkbox-row">{(["English", "Arabic", "French"] as const).map((language) => <label key={language}><input type="checkbox" checked={config.languages.includes(language)} onChange={() => toggleLanguage(language)} />{language}</label>)}</div></fieldset>
          <div className="range-control-grid">{rangeControls.map((control) => { const value = config[control.key] as number; return <label key={control.key}><span><strong>{control.label}</strong><output>{value}{control.suffix}</output></span><input aria-label={control.label} type="range" min={control.min} max={control.max} step={control.step ?? 1} value={value} onChange={(event) => updateNumber(control.key, Number(event.target.value))} /></label>; })}</div>
          <label className="seed-field"><span>Fixed seed</span><input type="number" value={config.seed} onChange={(event) => updateNumber("seed", Number(event.target.value))} /></label>
          <div className="dataset-export-actions"><button className="button-secondary" type="button" onClick={() => downloadJson("threadline-benchmark-config.json", config)}>Export configuration JSON</button><button className="button-secondary" type="button" onClick={() => downloadJson("threadline-synthetic-records.json", dataset ?? { config, ...generated })}>Export records JSON</button><button className="button-primary" type="button" disabled={busy !== null} onClick={() => void generateBackendDataset()}>{busy === "generate" ? "Generating…" : "Generate backend dataset"}</button><button className="button-primary" type="button" disabled={!dataset || busy !== null} onClick={() => void runBackendBenchmark()}>{busy === "benchmark" ? "Running…" : "Run benchmark"}</button>{busy ? <button className="button-quiet" type="button" onClick={() => abortRef.current?.abort()}>Cancel</button> : null}</div>
          <p className="ablation-run-status" role="status" aria-live="polite">{backendState}</p>
        </form>
        <div className="dataset-preview">
          <div className="composition-grid">{Object.entries(generated.composition).map(([key, value]) => <article key={key}><span>{key.replaceAll("_", " ")}</span><strong>{value.toLocaleString()}</strong></article>)}</div>
          <div className="generated-records"><header><h3>Generated record preview</h3><span>{generated.records.length} fictional records</span></header><div>{generated.records.slice(0, 8).map((record) => <article key={record.record_id}><div><strong>{record.record_id}</strong><span>{record.fictional_identity_id} · {record.language}</span></div><p lang={record.language === "Arabic" ? "ar" : undefined} dir={record.language === "Arabic" ? "rtl" : undefined}>{record.display_name}</p><small>{record.fields_present.length} fields · {record.flags.join(", ") || "standard template"}</small></article>)}</div></div>
          <p className="synthetic-value-note">All generated names, records, and pair labels are fictional. Browser preview values remain illustrative until “Generate backend dataset” is run; backend results carry a stable ID and content hash.</p>
        </div>
      </div>
    </section>
  );
}
