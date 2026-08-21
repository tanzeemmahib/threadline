import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");
const json = async (path) => JSON.parse(await read(path));

test("Reverie judge mode is a six-scene artifact-backed winning story", async () => {
  const [route, component, artifact] = await Promise.all([
    read("../src/app/demo/page.tsx"),
    read("../src/components/reverie-judge-mode.tsx"),
    json("../../docs/submission/reverie-prompt-lab.json"),
  ]);

  assert.match(route, /loadReverieEvidence/);
  assert.match(route, /loadSubmissionResults/);
  assert.match(route, /technicalWorkspace/);
  assert.match(route, /query\.present === "1"/);
  assert.match(route, /crossScriptCase=\{evidence\.cases\[0\]\}/);
  for (const scene of ["Human stakes", "One-shot baseline", "Source-cited extraction", "Supported thread", "Conflict gate", "Measured proof"]) {
    assert.match(component, new RegExp(scene));
  }
  for (const control of ["Reset", "Back", "Next evidence", "Compare the prompts", "Open the technical workspace"]) {
    assert.match(component, new RegExp(control));
  }
  assert.deepEqual(artifact.winning_story.supported_pair, ["FAMILY-018", "SHELTER-204"]);
  assert.deepEqual(artifact.winning_story.blocked_rival_pair, ["FAMILY-018", "HOSPITAL-052"]);
  assert.equal(artifact.winning_story.climax, "One connection recovered. One false merge prevented. Every decision traceable.");
});

test("presentation mode remains optional, offline, controllable, and reduced-motion safe", async () => {
  const [route, component, styles] = await Promise.all([
    read("../src/app/demo/page.tsx"),
    read("../src/components/reverie-judge-mode.tsx"),
    read("../src/app/reverie-demo.css"),
  ]);

  assert.match(route, /presentation=\{presentation\}/);
  assert.doesNotMatch(component, /fetch\(/);
  for (const label of ["Autoplay", "Pause", "Resume", "Replay", "Hide cues", "Show cues", "Restart", "Manual timing", "Speaker cue"]) {
    assert.match(component, new RegExp(label));
  }
  assert.match(component, /matchMedia\("\(prefers-reduced-motion: reduce\)"\)/);
  assert.match(component, /isNestedInteractive\(event\.target\)/);
  assert.match(component, /event\.shiftKey/);
  assert.match(styles, /\.reverie-judge--present/);
  assert.match(styles, /\.reverie-presentation-bar/);
  assert.match(styles, /@media \(max-width: 640px\)/);
});

test("source dialog is explicitly named and cross-script proof stays artifact-backed", async () => {
  const [component, artifact] = await Promise.all([
    read("../src/components/reverie-judge-mode.tsx"),
    json("../../docs/submission/reverie-prompt-lab.json"),
  ]);

  assert.match(component, /aria-labelledby="reverie-source-dialog-title"/);
  assert.match(component, /aria-describedby="reverie-source-dialog-description"/);
  assert.match(component, /Archived Prompt V2 extraction \/ separate evidence track/);
  assert.match(component, /derived transliteration \/ normalization/);
  assert.match(component, /lang="ar"/);
  const crossScript = artifact.cases.find((item) => item.kind === "cross_script_partial");
  assert.ok(crossScript);
  assert.equal(crossScript.records[0].archived_live_v2_extraction.evidence_track, "archived_live_provider_extraction");
  assert.equal(crossScript.records[0].archived_live_v2_extraction.unsupported_field_keys.length, 0);
  assert.equal(crossScript.decision.state, "human_review_required");
});

test("every winning-story source span resolves to immutable original text", async () => {
  const artifact = await json("../../docs/submission/reverie-prompt-lab.json");
  const records = new Map(artifact.winning_story.records.map((record) => [record.record_id, record]));
  for (const span of artifact.winning_story.source_spans) {
    const record = records.get(span.record_id);
    assert.ok(record, `record ${span.record_id} exists`);
    assert.equal(record.text.slice(span.start, span.end), span.quote, span.span_id);
    assert.equal(span.valid, true, span.span_id);
  }
});

test("the rival gate blocks and the supported pair remains review-only", async () => {
  const artifact = await json("../../docs/submission/reverie-prompt-lab.json");
  const supported = artifact.winning_story.evidence_contracts.find((contract) => contract.candidate_id === "MATCH-001");
  const blocked = artifact.winning_story.evidence_contracts.find((contract) => contract.candidate_id === "MATCH-002");
  assert.equal(supported.contract_status, "passed_with_review_requirements");
  assert.equal(supported.release_allowed_for_authorized_review, true);
  assert.equal(blocked.contract_status, "blocked");
  assert.equal(blocked.release_allowed_for_authorized_review, false);
  assert.ok(blocked.rule_results.some((rule) => rule.rule_id === "MATERIAL_CONTRADICTIONS_RESOLVED" && rule.status === "block"));
  assert.ok(blocked.rule_results.some((rule) => rule.affected_evidence_span_ids.includes("SPAN-HOSPITAL-052-AGE-36")));
});

test("Reverie surfaces preserve keyboard, reduced-motion, and narrow-screen contracts", async () => {
  const [judge, demoCss, landingCss, lab] = await Promise.all([
    read("../src/components/reverie-judge-mode.tsx"),
    read("../src/app/reverie-demo.css"),
    read("../src/app/reverie-landing.css"),
    read("../src/components/prompt-lab/prompt-lab.tsx"),
  ]);
  for (const key of ["ArrowLeft", "ArrowRight", "Home", "End"]) assert.match(judge, new RegExp(key));
  assert.match(judge, /aria-live="polite"/);
  assert.match(judge, /<dialog/);
  assert.match(judge, /button, a, input, select, textarea, summary, dialog/);
  assert.match(demoCss, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(landingCss, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(demoCss, /@media \(max-width: 640px\)/);
  assert.match(lab, /role="tablist"/);
  assert.match(lab, /tabIndex=\{selectedIndex === index \? 0 : -1\}/);
});

test("Reverie routes fail closed when locked artifacts cannot be validated", async () => {
  const [loader, demoError, labError] = await Promise.all([
    read("../src/lib/reverie-evidence.ts"),
    read("../src/app/demo/error.tsx"),
    read("../src/app/prompt-lab/error.tsx"),
  ]);
  for (const guard of ["ARTIFACT_PARSE_FAILED", "ARTIFACT_SCHEMA_INVALID", "ARTIFACT_PROVENANCE_INVALID", "source?.slice", "PRECISION_REGRESSION"]) {
    assert.match(loader, new RegExp(guard.replace("?", "\\?")));
  }
  assert.match(demoError, /ReverieArtifactErrorState/);
  assert.match(labError, /ReverieArtifactErrorState/);
});
