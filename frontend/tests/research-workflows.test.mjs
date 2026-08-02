import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { defaultBenchmarkConfig, generateSyntheticBenchmark } from "../src/lib/benchmark/generator.ts";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");

test("record selection synchronizes reconstruction state", async () => {
  const shell = await read("../src/components/workspace/workspace-shell.tsx");
  assert.match(shell, /function selectRecord/);
  assert.match(shell, /eventId: event\?\.event_id/);
  assert.match(shell, /locationId: event\?\.location_id/);
  assert.match(shell, /onSelectRecord=\{selectRecord\}/);
});

test("timeline-event and map-location selections synchronize records", async () => {
  const shell = await read("../src/components/workspace/workspace-shell.tsx");
  const canvas = await read("../src/components/workspace/reconstruction-canvas.tsx");
  assert.match(shell, /function selectEvent/);
  assert.match(shell, /recordId: event\.record_ids\[0\]/);
  assert.match(shell, /function selectLocation/);
  assert.match(canvas, /onSelectEvent\(event\.event_id\)/);
  assert.match(canvas, /onSelectLocation\(location\.location_id\)/);
});

test("workflow scrubber replays deterministic nodes", async () => {
  const explorer = await read("../src/components/workflow-explorer.tsx");
  assert.match(explorer, /Workflow scrubber/);
  assert.match(explorer, /type="range"/);
  assert.match(explorer, /Replay node by node/);
  assert.match(explorer, /No model calls are being made/);
});

test("node inspector exposes all required tabs", async () => {
  const explorer = await read("../src/components/workflow-explorer.tsx");
  for (const tab of ["Overview", "Input", "Prompt", "Output", "Validation", "Evidence", "Diff"]) assert.match(explorer, new RegExp(`"${tab}"`));
  assert.match(explorer, /Original evidence is never replaced/i);
});

test("dataset generation is deterministic for the same fixed configuration", () => {
  const first = generateSyntheticBenchmark(defaultBenchmarkConfig);
  const second = generateSyntheticBenchmark({ ...defaultBenchmarkConfig });
  assert.deepEqual(first, second);
  assert.equal(first.records.length, defaultBenchmarkConfig.identities * defaultBenchmarkConfig.records_per_identity);
  assert.equal(first.composition.languages, 3);
});

test("baseline arena compares all four systems and expected behaviours", async () => {
  const data = await read("../src/data/research-data.ts");
  const arena = await read("../src/components/evaluation/baseline-arena.tsx");
  for (const system of ["Exact/fuzzy matching", "Generic single-prompt LLM", "Structured single-call LLM", "Full THREADLINE workflow"]) assert.match(data, new RegExp(system.replace("/", "\\/")));
  assert.match(arena, /evidenceMatrixRows/);
  assert.match(arena, /Synthetic example output/);
  assert.match(arena, /Actual backend output/);
});

test("ablation laboratory toggles seven nodes and drills into changed cases", async () => {
  const lab = await read("../src/components/evaluation/ablation-lab.tsx");
  for (const node of ["Evidence quarantine", "Multilingual normalization", "Timeline reconstruction", "Contradiction prosecutor", "Rival-candidate test", "Independent adjudication", "Privacy gate"]) assert.match(lab, new RegExp(node));
  assert.match(lab, /type="checkbox"/);
  assert.match(lab, /Affected cases/);
  assert.match(lab, /Illustrative values — awaiting backend evaluation/);
  assert.match(lab, /runAblation/);
});

test("error workbench filters all ten error categories", async () => {
  const data = await read("../src/data/research-data.ts");
  const workbench = await read("../src/components/evaluation/error-workbench.tsx");
  for (const category of ["missed true candidate", "incorrect candidate link", "failed abstention", "unsupported evidence", "timeline reasoning failure", "transliteration failure", "rival-candidate confusion", "prompt-injection failure", "privacy exposure", "extraction error"]) assert.match(data, new RegExp(category));
  for (const filter of ["System", "Language", "Error type", "Configuration", "Severity"]) assert.match(workbench, new RegExp(filter));
});

test("audit ledger covers provenance events and chronological filters", async () => {
  const data = await read("../src/data/research-data.ts");
  const ledger = await read("../src/components/workspace/audit-ledger.tsx");
  for (const event of ["source ingested", "injection quarantined", "field extracted", "translation created", "normalization variant added", "candidate retrieved", "hypothesis produced", "contradiction found", "rival evaluated", "adjudication produced", "privacy field redacted", "human review requested", "reviewer decision saved"]) assert.match(data, new RegExp(event));
  assert.match(ledger, /Event type/);
  assert.match(ledger, /Origin/);
});

test("insufficient-evidence case explains safer abstention", async () => {
  const data = await read("../src/data/mock-data.ts");
  const review = await read("../src/components/workspace/review-panel.tsx");
  assert.match(data, /classification: "Insufficient evidence"/);
  for (const reason of ["Common given name", "Broad or missing age", "Missing destination", "No distinctive attributes", "Two equally plausible"]) assert.match(data, new RegExp(reason));
  assert.match(review, /Abstention is the safer result/);
});

test("Arabic evidence retains explicit right-to-left rendering", async () => {
  const canvas = await read("../src/components/evaluation/dataset-lab.tsx");
  const evidence = await read("../src/components/workspace/evidence-dialog.tsx");
  const data = await read("../src/data/mock-data.ts");
  assert.match(canvas, /dir=\{record\.language === "Arabic" \? "rtl"/);
  assert.match(evidence, /dir=\{record\.language === "Arabic" \? "rtl"/);
  assert.match(data, /translation_warning/);
});

test("case packet route contains print styles and safety content", async () => {
  const route = await read("../src/app/workspace/packet/page.tsx");
  const packet = await read("../src/components/workspace/case-packet.tsx");
  const styles = await read("../src/app/print.css");
  assert.match(route, /CasePacket/);
  assert.match(packet, /Safety statement/);
  assert.match(styles, /@media print/);
  assert.match(styles, /@page/);
});

test("mock and backend output modes remain visibly distinct", async () => {
  const client = await read("../src/lib/api/client.ts");
  const arena = await read("../src/components/evaluation/baseline-arena.tsx");
  const ablation = await read("../src/components/evaluation/ablation-lab.tsx");
  assert.match(client, /configuredMode/);
  assert.match(arena, /Synthetic example output/);
  assert.match(arena, /Actual backend output/);
  assert.match(ablation, /Actual backend output/);
  assert.match(ablation, /No displayed fixture percentage is a performance claim/);
});

test("persistent evaluation console exposes jobs, multi-seed uncertainty, risk coverage, and adaptive routing", async () => {
  const consoleSource = await read("../src/components/evaluation/evaluation-run-console.tsx");
  for (const term of ["createBenchmarkJob", "cancelJob", "fixed-seed bootstrap 95%", "Risk–coverage", "Adaptive router comparison", "listStoredResults", "exportResultManifest"]) assert.match(consoleSource, new RegExp(term));
});
