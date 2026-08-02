import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");

test("all required routes exist with descriptive page content", async () => {
  const routes = await Promise.all([
    read("../src/app/page.tsx"),
    read("../src/app/workspace/page.tsx"),
    read("../src/app/benchmark/page.tsx"),
    read("../src/app/trials/page.tsx"),
    read("../src/app/methodology/page.tsx"),
  ]);
  assert.match(routes[0], /One person can exist as five disconnected records/);
  assert.match(routes[1], /WorkspaceShell/);
  assert.match(routes[2], /awaiting measured benchmark output/);
  assert.match(routes[3], /TrialsLab/);
  assert.match(routes[4], /Node-by-node reasoning/);
});

test("synthetic dataset is deterministic and contains required safety cases", async () => {
  const data = await read("../src/data/mock-data.ts");
  assert.doesNotMatch(data, /Math\.random/);
  assert.match(data, /FAMILY-018/);
  assert.match(data, /SHELTER-204/);
  assert.match(data, /PHONE-066/);
  assert.match(data, /Instruction quarantined/);
  assert.match(data, /HOSPITAL-052/);
  assert.match(data, /hard_conflict/);
});

test("API adapter centralizes fetch and has a visible mock fallback", async () => {
  const client = await read("../src/lib/api/client.ts");
  const sourceFiles = await Promise.all([
    read("../src/components/workspace/workspace-shell.tsx"),
    read("../src/components/workspace/review-panel.tsx"),
    read("../src/app/benchmark/page.tsx"),
  ]);
  assert.match(client, /NEXT_PUBLIC_API_URL/);
  assert.match(client, /POST/);
  assert.match(client, /Backend unavailable — synthetic fallback active/);
  for (const source of sourceFiles) assert.doesNotMatch(source, /fetch\s*\(/);
});

test("central API client exposes the complete integrated contract", async () => {
  const client = await read("../src/lib/api/client.ts");
  for (const method of ["getHealth", "getDemoIncident", "analyzeRecords", "runBaselines", "generateBenchmark", "runBenchmark", "runAblation", "createTrial", "runTrial", "getTrialRun", "getWorkflowRun", "submitReviewOutcome", "getStoredResult", "exportResultManifest"]) assert.match(client, new RegExp(`${method}\\(`));
  assert.match(client, /requestId/);
  assert.match(client, /retryable/);
  assert.doesNotMatch(client, /return this\.mock/);
});

test("trials UI covers all deterministic mutations and responsive research tabs", async () => {
  const trials = await read("../src/components/trials/trials-lab.tsx");
  const route = await read("../src/app/trials/page.tsx");
  const styles = await read("../src/app/trials.css");
  for (const mutation of ["transliteration_corruption", "spelling_corruption", "missing_surname", "estimated_age_shift", "missing_location", "changed_location", "impossible_timeline", "conflicting_distinctive_feature", "translation_detail_loss", "common_name_collision", "duplicate_submission", "equally_plausible_rivals", "prompt_injection", "source_reliability_noise", "contradictory_relative_information"]) assert.match(trials, new RegExp(mutation));
  for (const tab of ["Configure", "Mutation diff", "Results", "Divergence", "Trace", "Export"]) assert.match(trials, new RegExp(tab));
  assert.match(route, /THREADLINE Trials/);
  assert.match(styles, /grid-template-columns: minmax\(17rem/);
  assert.match(styles, /@media \(max-width: 760px\)/);
});

test("review UI excludes autonomous identity confirmation language", async () => {
  const review = await read("../src/components/workspace/review-panel.tsx");
  assert.match(review, /Record authorized verification outcome/);
  assert.match(review, /Escalate for authorized review/);
  assert.doesNotMatch(review, /Confirm match/i);
});

test("shared request and response examples are valid JSON", async () => {
  const input = JSON.parse(await read("../../shared/sample-input.json"));
  const output = JSON.parse(await read("../../shared/sample-output.json"));
  assert.equal(input.incident.incident_id, "INCIDENT-NDE-001");
  assert.equal(output.status, "review_required");
  assert.equal(output.candidates[0].candidate_id, "MATCH-001");
});
