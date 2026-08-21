import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");

async function loadArtifact() {
  return JSON.parse(await read("../../docs/submission/reverie-prompt-lab.json"));
}

test("Prompt Lab is a first-class server-loaded route with progressive evidence", async () => {
  const [route, component, header, styles, loader, liveOutputRoute] = await Promise.all([
    read("../src/app/prompt-lab/page.tsx"),
    read("../src/components/prompt-lab/prompt-lab.tsx"),
    read("../src/components/site-header.tsx"),
    read("../src/app/prompt-lab.css"),
    read("../src/lib/reverie-evidence.ts"),
    read("../src/app/prompt-lab/live-output/[systemRunId]/route.ts"),
  ]);

  assert.match(route, /loadReverieEvidence/);
  assert.match(route, /loadReverieLiveEvaluation/);
  assert.match(route, /<PromptLab artifact=\{artifact\}/);
  assert.match(route, /liveEvaluation=\{liveEvaluation\}/);
  assert.doesNotMatch(route, /const\s+metrics\s*=/);
  for (const label of [
    "Prompt and model configuration",
    "Raw model or replay output",
    "Validated structured output",
    "Deterministic comparison and evidence contract",
    "Exact claim-to-source lineage",
    "Open full prompt comparison",
    "Inspect artifact-derived Prompt",
    "Same-model live comparison",
    "NOT MEASURED",
    "V3 TRADEOFF / PRECISION REGRESSION",
    "LIVE MODEL PERFORMANCE",
    "Source-span coverage",
    "Download sanitized raw \\+ validated output",
  ]) assert.match(component, new RegExp(label));
  assert.match(component, /role="tablist"/);
  assert.match(component, /ArrowRight/);
  assert.match(component, /ArrowLeft/);
  assert.match(component, /event\.key === "Home"/);
  assert.match(component, /event\.key === "End"/);
  assert.match(component, /buildPromptDiff/);
  assert.match(component, /<ins/);
  assert.match(component, /<del/);
  assert.match(component, /role="region"/);
  assert.match(component, /liveEvaluation\.state === "complete"/);
  assert.match(component, /liveEvaluation\.state === "incomplete"/);
  assert.match(component, /liveEvaluation\.state === "invalid"/);
  assert.match(loader, /threadline-reverie-live-evaluation-results\/1\.0\.0/);
  assert.match(loader, /reverie-live-evaluation-results\.json/);
  assert.match(loader, /reverie-live-evaluation-manifest\.json/);
  assert.match(loader, /validateLockedLiveEvaluationProvenance/);
  assert.match(loader, /publication-manifest digest/);
  assert.match(loader, /same_input_and_config_verified/);
  assert.match(loader, /technical_output_sha256/);
  assert.match(liveOutputRoute, /loadReverieLiveRunOutput/);
  assert.match(liveOutputRoute, /Content-Disposition/);
  assert.match(liveOutputRoute, /X-THREADLINE-SHA256/);
  assert.match(header, />Prompt Lab</);
  assert.match(styles, /@media \(max-width: 430px\)/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
});

test("Prompt Lab cases preserve identical input and exact source-span evidence", async () => {
  const artifact = await loadArtifact();
  assert.equal(artifact.schema_version, "threadline-reverie-prompt-lab/1.0.0");
  assert.equal(artifact.synthetic_only, true);
  assert.deepEqual(artifact.cases.map((item) => item.kind), [
    "cross_script_partial",
    "shared_contact_insufficient",
    "blocking_identity_conflict",
  ]);

  for (const item of artifact.cases) {
    assert.equal(item.identical_input_verified, true);
    assert.deepEqual(item.systems.one_shot.candidate_record_ids, item.input_manifest.record_ids);
    assert.deepEqual(item.systems.threadline.candidate_record_ids, item.input_manifest.record_ids);
    const records = new Map(item.records.map((record) => [record.record_id, record.text]));
    for (const span of item.source_spans) {
      const source = records.get(span.record_id);
      assert.ok(source, `${span.span_id} must resolve to a displayed source record`);
      assert.equal(source.slice(span.start, span.end), span.quote, `${span.span_id} must retain an exact source quote`);
      assert.equal(span.valid, true);
    }
  }
});

test("Prompt Lab safety outcomes remain fail-closed and artifact-backed", async () => {
  const artifact = await loadArtifact();
  const crossScript = artifact.cases.find((item) => item.kind === "cross_script_partial");
  const sharedContact = artifact.cases.find((item) => item.kind === "shared_contact_insufficient");
  const blocked = artifact.cases.find((item) => item.kind === "blocking_identity_conflict");

  assert.equal(crossScript.decision.state, "human_review_required");
  assert.equal(sharedContact.decision.state, "human_review_required");
  assert.equal(blocked.decision.state, "blocked_by_conflict");
  assert.equal(blocked.decision.release_allowed_for_authorized_review, false);
  assert.equal(blocked.decision.blocking_conflicts[0].field_name, "date_of_birth");
  assert.equal(blocked.systems.one_shot.classification, "possible_candidate");
  assert.equal(blocked.systems.threadline.evidence_contract.contract_status, "blocked");
});

test("Prompt versions and measured promotion decision cannot silently drift", async () => {
  const artifact = await loadArtifact();
  for (const prompt of Object.values(artifact.prompt_iterations.prompts)) {
    const source = await read(`../../${prompt.source_path}`);
    assert.equal(createHash("sha256").update(source).digest("hex"), prompt.sha256);
  }

  const fullCohort = artifact.prompt_iterations.cohorts.find((cohort) => cohort.cohort_id === "full-58-record-live-cohort");
  assert.deepEqual(fullCohort.comparable_versions, ["v2", "v3"]);
  const [v2, v3] = fullCohort.runs;
  assert.equal(v2.fixture_sha256, v3.fixture_sha256);
  assert.equal(v2.record_count, 58);
  assert.equal(v3.record_count, 58);
  assert.equal(artifact.prompt_iterations.promotion_decision.production_version, "v2");
  assert.equal(artifact.prompt_iterations.promotion_decision.not_promoted, "v3");
  assert.equal(artifact.prompt_iterations.promotion_decision.reason_code, "PRECISION_REGRESSION");
  assert.ok(v3.extraction_quality.micro_precision < v2.extraction_quality.micro_precision);
  assert.ok(v3.extraction_quality.micro_f1 < v2.extraction_quality.micro_f1);
  assert.ok(v3.extraction_quality.micro_recall > v2.extraction_quality.micro_recall);
  assert.match(artifact.prompt_iterations.comparison_limit, /No full 58-record V1 live artifact exists/);
});

test("optional live-provider evidence is either absent or complete, verified, and release-locked", async () => {
  let liveContents;
  try {
    liveContents = await read("../../docs/submission/reverie-live-evaluation-results.json");
  } catch (error) {
    if (error?.code === "ENOENT") {
      const component = await read("../src/components/prompt-lab/prompt-lab.tsx");
      assert.match(component, /NOT MEASURED/);
      return;
    }
    throw error;
  }

  const live = JSON.parse(liveContents);
  const manifest = JSON.parse(await read("../../docs/submission/reverie-live-evaluation-manifest.json"));
  assert.equal(live.schema_version, "threadline-reverie-live-evaluation-results/1.0.0");
  assert.equal(live.status, "complete");
  assert.equal(live.synthetic_only, true);
  assert.equal(live.same_input_and_config_verified, true);
  assert.equal(live.completed_system_runs + live.failed_system_runs, live.expected_system_runs);
  assert.equal(live.cases.length * 2, live.expected_system_runs);
  assert.equal(manifest.schema_version, "threadline-reverie-live-evaluation-publication/1.0.0");
  assert.equal(manifest.artifact_id, live.artifact_id);
  assert.equal(manifest.spec.sha256, live.spec_sha256);
  assert.equal(manifest.raw_provider_recorder.sha256, live.recorder_artifact_sha256);
  assert.equal(manifest.raw_provider_recorder.contains_credentials, false);
  assert.equal(manifest.results.sha256, createHash("sha256").update(liveContents).digest("hex"));
});
