import { describe, it, expect } from "vitest";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildRootIndexHtml } from "../src/composer.js";
import type { SeamPlan, MasterBundle } from "../src/types.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const designMdPath = path.join(__dirname, "fixtures", "design-minimal.md");

const bundle: MasterBundle = {
  slug: "fixture",
  master: { durationMs: 60_000 },
  transcript: { words: [{ text: "hi", startMs: 100, endMs: 400 }] },
  boundaries: [],
} as unknown as MasterBundle;

const plan: SeamPlan = {
  episode_slug: "fixture",
  master_duration_ms: 60_000,
  seams: [
    { index: 1, at_ms: 0, ends_at_ms: 30_000, scene_mode: "head" },
    { index: 2, at_ms: 30_000, ends_at_ms: 60_000, scene_mode: "broll" },
  ],
} as unknown as SeamPlan;

const baseArgs = {
  designMdPath,
  plan,
  bundle,
  existingSeamFiles: new Set<number>([1, 2]),
};

describe("buildRootIndexHtml", () => {
  const htmlNoMusic = buildRootIndexHtml({
    ...baseArgs,
    masterRelPath: "assets/master.mp4",
  });

  const htmlWithMusic = buildRootIndexHtml({
    ...baseArgs,
    masterRelPath: "assets/master.mp4",
    musicRelPath: "assets/music.wav",
  });

  it("declares root composition with correct dimensions and duration", () => {
    expect(htmlNoMusic).toContain('data-composition-id="root"');
    expect(htmlNoMusic).toContain('data-width="1440"');
    expect(htmlNoMusic).toContain('data-height="2560"');
    expect(htmlNoMusic).toContain('data-duration="60.000"');
  });

  it("inlines :root CSS variables from the DESIGN.md fenced block", () => {
    expect(htmlNoMusic).toContain("--color-text-primary: #FFFFFF;");
    expect(htmlNoMusic).toContain("--spacing-md: 24px;");
  });

  it("emits a muted video track and a separate audio track for master.mp4", () => {
    expect(htmlNoMusic).toContain('src="assets/master.mp4"');
    expect(htmlNoMusic).toMatch(/<video[^>]*muted/);
    expect(htmlNoMusic).toMatch(/<video[^>]*data-has-audio="false"/);
    expect(htmlNoMusic).toMatch(/<audio[^>]*data-volume="1"/);
  });

  it("loads the captions sub-composition for the full duration", () => {
    expect(htmlNoMusic).toMatch(/data-composition-src="compositions\/captions\.html"[^>]*data-start="0"[^>]*data-duration="60\.000"/);
  });

  it("loads per-seam sub-compositions only when their file exists", () => {
    expect(htmlNoMusic).toContain('data-composition-src="compositions/seam-2.html"');
    expect(htmlNoMusic).toContain('data-composition-src="compositions/seam-1.html"');
  });

  it("places per-seam sub-composition at the seam window in seconds", () => {
    expect(htmlNoMusic).toMatch(/data-composition-src="compositions\/seam-2\.html"[^>]*data-start="30\.000"[^>]*data-duration="30\.000"/);
  });

  it("uses exactly five distinct track indexes when no music (video=0, captions=1, audio=2, seam=3, transitions=4)", () => {
    const trackIndexes = [...htmlNoMusic.matchAll(/data-track-index="(\d+)"/g)].map((m) => Number(m[1]));
    expect(new Set(trackIndexes)).toEqual(new Set([0, 1, 2, 3, 4]));
  });

  it("emits a transitions clip referencing compositions/transitions.html", () => {
    expect(htmlNoMusic).toContain('data-composition-src="compositions/transitions.html"');
    expect(htmlNoMusic).toContain('data-composition-id="transitions"');
  });

  it("emits all seams on a single track index (3)", () => {
    const seamClipMatches = htmlNoMusic.match(/data-composition-src="compositions\/seam-\d+\.html"[\s\S]*?data-track-index="(\d+)"/g);
    expect(seamClipMatches).not.toBeNull();
    for (const clip of seamClipMatches!) {
      const m = clip.match(/data-track-index="(\d+)"/);
      expect(m![1]).toBe("3");
    }
  });

  it("inlines literal hex/RGBA on captured elements (no var() in body styles)", () => {
    // The :root { --… } declarations are documentation only; the body's own
    // style attributes must use literal values for shader-compat.
    const bodyStyleMatch = htmlNoMusic.match(/<style>[\s\S]*?<\/style>/);
    expect(bodyStyleMatch).toBeTruthy();
    const styleBlock = bodyStyleMatch![0];
    const bodyRule = styleBlock.match(/html,\s*body\s*\{[^}]*\}/);
    expect(bodyRule).toBeTruthy();
    expect(bodyRule![0]).not.toMatch(/var\(--/);
  });

  it("emits a music audio clip when musicRelPath is provided", () => {
    expect(htmlWithMusic).toContain('src="assets/music.wav"');
    expect(htmlWithMusic).toContain('data-volume="0.5"');
    expect(htmlWithMusic).toContain('data-track-index="5"');
  });

  it("emits no music clip when musicRelPath is undefined", () => {
    expect(htmlNoMusic).not.toMatch(/id="music"/);
  });

  it("uses exactly six distinct track indexes when music is present (0-5)", () => {
    const trackIndexes = [...htmlWithMusic.matchAll(/data-track-index="(\d+)"/g)].map((m) => Number(m[1]));
    expect(new Set(trackIndexes)).toEqual(new Set([0, 1, 2, 3, 4, 5]));
  });
});
