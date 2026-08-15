import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");

test("cinematic landing keeps important evidence in native accessible markup", async () => {
  const [story, fragments, workflow] = await Promise.all([
    read("../src/components/landing-story.tsx"),
    read("../src/components/landing-evidence-thread.tsx"),
    read("../src/components/workflow-strip.tsx"),
  ]);

  assert.match(story, /<h1/);
  assert.match(story, /RECORDS FRAGMENT\./);
  assert.match(story, /Identity shouldn/);
  assert.match(story, /Human review/);
  assert.match(story, /data-threadline-cta/);
  assert.match(fragments, /FAMILY-042/);
  assert.match(fragments, /SHELTER-118/);
  assert.match(fragments, /language: "ar"/);
  assert.match(workflow, /Source retained/);
  assert.match(workflow, /Abstention valid/);
  assert.doesNotMatch(story, /94% MATCH/i);
  assert.doesNotMatch(story, /1 PERSON/i);
});

test("Higgsfield atmosphere is bounded and has static fallbacks", async () => {
  const [story, styles, interaction, video, poster] = await Promise.all([
    read("../src/components/landing-story.tsx"),
    read("../src/app/landing.css"),
    read("../src/components/threadline-interaction-layer.tsx"),
    stat(new URL("../public/media/threadline/hero-archive-loop.webm", import.meta.url)),
    stat(new URL("../public/media/threadline/hero-archive-poster.webp", import.meta.url)),
  ]);

  assert.match(story, /preload="metadata"/);
  assert.match(story, /playsInline/);
  assert.match(story, /prefers-reduced-motion: reduce/);
  assert.match(story, /max-width: 760px/);
  assert.match(styles, /hero-archive-poster\.webp/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(interaction, /reducedMotion \? 0 : 320/);
  assert.ok(video.size < 3_000_000, `hero loop is ${video.size} bytes`);
  assert.ok(poster.size < 250_000, `hero poster is ${poster.size} bytes`);
});

test("operational typography and evidence ledgers stay systemic and accessible", async () => {
  const [layout, globals, story, landing, methodology, methodologyStyles] = await Promise.all([
    read("../src/app/layout.tsx"),
    read("../src/app/globals.css"),
    read("../src/components/landing-story.tsx"),
    read("../src/app/landing.css"),
    read("../src/app/methodology/page.tsx"),
    read("../src/app/methodology.css"),
  ]);

  assert.match(layout, /@fontsource\/ibm-plex-sans\/300\.css/);
  assert.match(layout, /@fontsource\/ibm-plex-mono\/600\.css/);
  assert.doesNotMatch(layout, /Cormorant|Manrope/);
  assert.match(globals, /--font-display: "IBM Plex Sans"/);
  assert.match(globals, /font-variant-numeric: tabular-nums slashed-zero/);
  assert.match(story, /typeset-audit__current/);
  assert.match(landing, /@keyframes audit-current-trace/);
  assert.match(landing, /\.typeset-audit__current \{ opacity: 0\.52; transform: none; \}/);
  assert.match(methodology, /<ol className="node-method-list">/);
  assert.match(methodology, /<details className="node-method">/);
  assert.match(methodology, /node-method__method/);
  assert.match(methodology, /node-method__handoff/);
  assert.match(methodologyStyles, /\.node-method-ledger__head/);
  assert.match(methodologyStyles, /min-height: 3\.75rem/);
});
