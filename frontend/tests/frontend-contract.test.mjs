import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");

test("all required routes exist with descriptive page content", async () => {
  const [routes, landing] = await Promise.all([
    Promise.all([
    read("../src/app/page.tsx"),
    read("../src/app/workspace/page.tsx"),
    read("../src/app/benchmark/page.tsx"),
    read("../src/app/trials/page.tsx"),
    read("../src/app/methodology/page.tsx"),
    read("../src/app/prompt-lab/page.tsx"),
    ]),
    read("../src/components/reverie-landing.tsx"),
  ]);
  assert.match(landing, /Connect the records/);
  assert.match(landing, /Never guess the person/);
  assert.match(landing, /Synthetic research demonstration/);
  assert.match(routes[1], /WorkspaceShell/);
  assert.match(routes[2], /awaiting measured benchmark output/);
  assert.match(routes[3], /TrialsLab/);
  assert.match(routes[4], /Node-by-node reasoning/);
  assert.match(routes[5], /PromptLab/);
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

test("cyclone demo covers the fail-closed end-to-end journey", async () => {
  const route = await read("../src/app/demo/page.tsx");
  const data = await read("../src/data/cyclone-case.ts");
  const guide = await read("../src/components/workspace/guided-demo.tsx");
  assert.match(route, /fixtureOnly/);
  for (const record of ["FAMILY-042", "SHELTER-118", "CLINIC-077", "EVAC-031", "AID-209", "WITNESS-064"]) assert.match(data, new RegExp(record));
  for (const rule of ["SOURCE_SPAN_INTEGRITY", "CLAIM_LINEAGE_COMPLETE", "CERTAINTY_PRESERVED", "TIMELINE_CONSISTENCY", "MATERIAL_CONTRADICTIONS_RESOLVED", "RIVAL_EXPLANATION_COVERAGE", "REQUIRED_SAFETY_NOTICE_PRESENT", "HUMAN_REVIEW_ROUTING_VALID", "AUDIT_EVENT_READY", "RELEASE_AUTHORIZATION_VALID"]) assert.match(data, new RegExp(rule));
  assert.match(data, /state: "contract_blocked"/);
  assert.match(data, /classification: null/);
  assert.match(data, /34-hour interval/);
  assert.match(data, /candidate_ledger/);
  assert.match(guide, /Verify the audit history/);
  assert.match(guide, /Record the disposition/);
});

test("legacy technical workspace tour retains its artifact-scoped controls", async () => {
  const [guide, evidence, workspace, landing, styles, header, globals] = await Promise.all([
    read("../src/components/workspace/guided-demo.tsx"),
    read("../src/data/judge-evidence.ts"),
    read("../src/components/workspace/workspace-shell.tsx"),
    read("../src/components/reverie-landing.tsx"),
    read("../src/app/workspace.css"),
    read("../src/components/site-header.tsx"),
    read("../src/app/globals.css"),
  ]);
  for (const scene of ["Fragmented records", "Single-prompt baseline", "Evidence extraction", "Contradiction challenge", "Rival candidate", "Evidence contract", "Human review", "Measured comparison"]) assert.match(guide, new RegExp(scene));
  for (const control of ["Start evidence challenge", "Open source", "View technical evidence", "Back", "Next", "Reset", "Exit guided case"]) assert.match(guide, new RegExp(control));
  assert.match(guide, /onOpenSource\(claim\.spanId\)/);
  assert.match(guide, /aria-keyshortcuts="ArrowLeft ArrowRight Home End Escape"/);
  assert.match(workspace, /onOpenSource=\{setEvidenceSpanId\}/);
  assert.match(evidence, /Deterministic mock replay — not model performance/);
  assert.match(evidence, /4 \/ 4 different-identity cases withheld/);
  assert.match(evidence, /0 \/ 8 evaluated different-identity pairs false-merged/);
  assert.doesNotMatch(evidence, /8\.762%/);
  assert.match(landing, /Run the evidence case/);
  assert.match(landing, /Compare the prompts/);
  assert.match(styles, /\.guided-demo--judge/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
  for (const primary of ["Guided Case", "Prompt Lab", "Workspace", "Evaluation"]) assert.match(header, new RegExp(`>${primary}<`));
  assert.match(header, /<details className="site-nav__technical"/);
  assert.match(header, /site-nav__technical-label--full">Technical evidence<\/span>/);
  assert.match(header, /site-nav__technical-label--compact">Technical<\/span>/);
  for (const technical of ["Trials", "Methodology"]) assert.match(header, new RegExp(`>${technical}<`));
  assert.match(globals, /\.site-nav__technical-menu/);
});

test("judge baseline receives the complete Cyclone fixture with a stable input digest", async () => {
  const [cyclone, evidence] = await Promise.all([
    read("../src/data/cyclone-case.ts"),
    read("../src/data/judge-evidence.ts"),
  ]);
  const fixtureBlock = cyclone.match(/export const cycloneRecords:[\s\S]*?\n\];\r?\n\r?\nconst leading/);
  assert.ok(fixtureBlock, "Cyclone fixture record block must remain readable");
  const records = [...fixtureBlock[0].matchAll(/record_id:\s*"([^"]+)"[\s\S]*?\n\s*text:\s*"([^"]+)"/g)]
    .map((match) => ({ record_id: match[1], text: match[2] }));
  const expectedIds = ["FAMILY-042", "SHELTER-118", "CLINIC-077", "EVAC-031", "AID-209", "WITNESS-064"];
  assert.deepEqual(records.map((record) => record.record_id), expectedIds);
  const inputSha256 = createHash("sha256").update(JSON.stringify(records)).digest("hex");
  assert.equal(inputSha256, "7f63bba78ab1e58bb20693dbb63113360149569de398fe59b79edddee83ba421");
  assert.match(evidence, /const cycloneInputRecordIds = cycloneRecords\.map\(\(record\) => record\.record_id\)/);
  assert.match(evidence, /recordIds: cycloneInputRecordIds/);
  assert.match(evidence, /inputRecordIds: cycloneInputRecordIds/);
  assert.match(evidence, /candidateRecordIds: \["FAMILY-042", "SHELTER-118"\]/);
  assert.match(evidence, /7f63bba78ab1e58bb20693dbb63113360149569de398fe59b79edddee83ba421/);
  assert.match(evidence, /promptTemplateId: "generic_baseline"/);
  assert.match(evidence, /promptTemplateVersion: "v1"/);
  assert.match(evidence, /promptSha256: "4f44911def4cdf0bdcf7379489420573323381e43ec84eaffe8ceb8c99422800"/);
  const promptLiteral = evidence.match(/\n\s*prompt: ("[^\r\n]+"),/);
  assert.ok(promptLiteral, "Judge baseline must retain the exact artifact prompt text");
  const prompt = JSON.parse(promptLiteral[1]);
  assert.equal(createHash("sha256").update(prompt).digest("hex"), "4f44911def4cdf0bdcf7379489420573323381e43ec84eaffe8ceb8c99422800");
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
  for (const method of ["getHealth", "getDemoIncident", "analyzeRecords", "runBaselines", "generateBenchmark", "runBenchmark", "runAblation", "createTrial", "runTrial", "getTrialRun", "getWorkflowRun", "getEvidenceContract", "submitReviewOutcome", "getStoredResult", "exportResultManifest"]) assert.match(client, new RegExp(`${method}\\(`));
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
  assert.match(trials, /trials-progression/);
  assert.match(trials, /aria-pressed=/);
  assert.match(trials, /role="status"/);
  assert.match(styles, /grid-template-columns: minmax\(17rem/);
  assert.match(styles, /grid-template-areas:/);
  assert.match(styles, /min-height: 44px/);
  assert.match(styles, /@media \(max-width: 760px\)/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
  assert.doesNotMatch(styles, /rgb\(12 26 37/);
});

test("review UI excludes autonomous identity confirmation language", async () => {
  const review = await read("../src/components/workspace/review-panel.tsx");
  assert.match(review, /Record Authorized Decision/);
  assert.match(review, /Escalate to authorized process/);
  assert.match(review, /Additional evidence required/);
  assert.doesNotMatch(review, /Confirm match/i);
});

test("premium investigation flow exposes real lineage contradiction and contract states", async () => {
  const sources = await Promise.all([
    read("../src/app/page.tsx"),
    read("../src/components/reverie-landing.tsx"),
    read("../src/components/workspace/workspace-shell.tsx"),
    read("../src/components/workspace/evidence-lineage.tsx"),
    read("../src/components/workspace/contradiction-workspace.tsx"),
    read("../src/components/workspace/review-panel.tsx"),
    read("../src/components/workspace/guided-demo.tsx"),
  ]);
  const productSource = sources.join("\n");
  for (const label of ["Run the evidence case", "Candidate claim", "Normalized claim", "Extracted evidence", "Exact source span", "Rival explanations", "Run Evidence Contract", "Validating Evidence…", "Resolve Contract Violations", "Send to Authorized Review", "Record Authorized Decision"]) {
    assert.match(productSource, new RegExp(label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i"));
  }
  for (const forbidden of ["AI Match Confirmed", "Identity Confirmed", "Person Found", "Guaranteed Match", "Autonomous Verification"]) {
    assert.doesNotMatch(productSource, new RegExp(forbidden, "i"));
  }
});

test("candidate review fails closed and exposes the evidence contract ledger", async () => {
  const review = await read("../src/components/workspace/review-panel.tsx");
  const workspace = await read("../src/components/workspace/workspace-shell.tsx");
  const types = await read("../src/types/index.ts");
  const styles = await read("../src/app/workspace.css");
  assert.match(review, /OUTPUT WITHHELD — EVIDENCE CONTRACT FAILED/);
  assert.match(review, /Claim ledger/);
  assert.match(review, /Export certificate/);
  assert.match(review, /aria-live="assertive"/);
  assert.match(types, /interface EvidenceContract/);
  assert.match(types, /contract_release_status/);
  assert.match(styles, /evidence-contract--blocked/);
  assert.match(workspace, /searchParams\.get\("run"\)/);
  assert.match(workspace, /getWorkflowRun\(requestedRunId/);
});

test("corrupted contract data fails closed before workspace presentation", async () => {
  const workspace = await read("../src/components/workspace/workspace-shell.tsx");
  assert.match(workspace, /function isSafeContract/);
  assert.match(workspace, /label: "Output withheld"/);
  assert.match(workspace, /contract_release_status: analysis\.contract_release_status \?\? "withheld"/);
  assert.match(workspace, /Array\.isArray\(contract\.claims\)/);
});

test("decision integrity UI exposes real replay counterfactual and lineage controls", async () => {
  const review = await read("../src/components/workspace/review-panel.tsx");
  const client = await read("../src/lib/api/client.ts");
  for (const label of ["Decision reproducibility", "Run deterministic replay", "Test first source removal", "Decision-critical evidence", "Claim lineage", "Terminal chain hash"]) assert.match(review, new RegExp(label));
  for (const method of ["verifyAuditChain", "replayWorkflowRun", "runCounterfactual", "exportEvidenceContract"]) assert.match(client, new RegExp(`${method}\\(`));
  assert.match(review, /aria-live="polite"/);
});

test("shared request and response examples are valid JSON", async () => {
  const input = JSON.parse(await read("../../shared/sample-input.json"));
  const output = JSON.parse(await read("../../shared/sample-output.json"));
  assert.equal(input.incident.incident_id, "INCIDENT-NDE-001");
  assert.equal(output.status, "review_required");
  assert.equal(output.candidates[0].candidate_id, "MATCH-001");
});
