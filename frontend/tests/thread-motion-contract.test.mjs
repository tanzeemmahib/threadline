import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");

test("THREADLINE exposes one reusable motion vocabulary and centralized rhythm", async () => {
  const [components, tokens, layout] = await Promise.all([
    read("../src/components/thread-motion.tsx"),
    read("../src/lib/thread-motion.ts"),
    read("../src/app/layout.tsx"),
  ]);

  for (const primitive of [
    "ThreadButton",
    "ThreadLink",
    "ThreadTrace",
    "ThreadNode",
    "ThreadPulse",
    "ThreadLoader",
    "ThreadInput",
    "TraceBorder",
    "ConnectionState",
    "ResolutionTransition",
    "SignalPath",
  ]) assert.match(components, new RegExp(`export (?:const|function) ${primitive}`));

  assert.match(tokens, /trace: 580/);
  assert.match(tokens, /resolve: 720/);
  assert.match(tokens, /route: 320/);
  assert.match(tokens, /magneticControl: 4/);
  assert.match(layout, /threadMotionCssVariables/);
  assert.match(layout, /thread-motion\.css/);
});

test("motion remains semantic, restrained, and accessible", async () => {
  const [styles, interaction, workflow] = await Promise.all([
    read("../src/app/thread-motion.css"),
    read("../src/components/threadline-interaction-layer.tsx"),
    read("../src/components/workflow-explorer.tsx"),
  ]);

  assert.match(styles, /@media \(hover: hover\) and \(pointer: fine\)/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(styles, /thread-arrow__stem/);
  assert.match(styles, /thread-arrow__head/);
  assert.match(styles, /thread-loader-segment/);
  assert.match(styles, /data-thread-state="interrupted"/);
  assert.doesNotMatch(styles, /scale\(1\.0[5-9]/);
  assert.doesNotMatch(interaction, /offsetWidth/);
  assert.match(interaction, /requestAnimationFrame/);
  assert.match(interaction, /\(hover: hover\) and \(pointer: fine\)/);
  assert.match(interaction, /reducedMotion \? 0 : 320/);
  assert.match(workflow, /<ThreadLoader/);
  assert.doesNotMatch(styles, /processing-turn/);
});

test("evidence motion never visually overstates an identity decision", async () => {
  const [review, contradictions, lineage] = await Promise.all([
    read("../src/components/workspace/review-panel.tsx"),
    read("../src/components/workspace/contradiction-workspace.tsx"),
    read("../src/components/workspace/evidence-lineage.tsx"),
  ]);

  assert.match(review, /state="interrupted"/);
  assert.match(review, /state="partial"/);
  assert.doesNotMatch(review, /state="connected"/);
  assert.match(contradictions, /"interrupted" : "partial"/);
  assert.match(lineage, /Nothing in this path confirms identity/);
  assert.match(lineage, /Evidence path connected to the original source/);
});

test("custom tab motion keeps native roving keyboard behavior", async () => {
  const sources = await Promise.all([
    read("../src/components/workflow-explorer.tsx"),
    read("../src/components/workspace/contradiction-workspace.tsx"),
    read("../src/components/evaluation/baseline-arena.tsx"),
    read("../src/components/trials/trials-lab.tsx"),
  ]);

  for (const source of sources) {
    assert.match(source, /ArrowRight/);
    assert.match(source, /ArrowLeft/);
    assert.match(source, /Home/);
    assert.match(source, /End/);
    assert.match(source, /tabIndex=/);
  }
});
