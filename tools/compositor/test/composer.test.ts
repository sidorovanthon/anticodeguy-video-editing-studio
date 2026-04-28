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

describe("buildRootIndexHtml", () => {
  const html = buildRootIndexHtml({
    designMdPath,
    plan,
    bundle,
    masterRelPath: "../stage-1-cut/master.mp4",
    existingSeamFiles: new Set<number>([1, 2]),
  });

  it("declares root composition with correct dimensions and duration", () => {
    expect(html).toContain('data-composition-id="root"');
    expect(html).toContain('data-width="1440"');
    expect(html).toContain('data-height="2560"');
    expect(html).toContain('data-duration="60.000"');
  });

  it("inlines :root CSS variables from the DESIGN.md fenced block", () => {
    expect(html).toContain("--color-text-primary: #FFFFFF;");
    expect(html).toContain("--spacing-md: 24px;");
  });

  it("emits a muted video track and a separate audio track for master.mp4", () => {
    expect(html).toContain('src="../stage-1-cut/master.mp4"');
    expect(html).toMatch(/<video[^>]*muted/);
    expect(html).toMatch(/<video[^>]*data-has-audio="false"/);
    expect(html).toMatch(/<audio[^>]*data-volume="1"/);
  });

  it("loads the captions sub-composition for the full duration", () => {
    expect(html).toMatch(/data-composition-src="compositions\/captions\.html"[^>]*data-start="0"[^>]*data-duration="60\.000"/);
  });

  it("loads per-seam sub-compositions only when their file exists", () => {
    expect(html).toContain('data-composition-src="compositions/seam-2.html"');
    expect(html).toContain('data-composition-src="compositions/seam-1.html"');
  });

  it("places per-seam sub-composition at the seam window in seconds", () => {
    expect(html).toMatch(/data-composition-src="compositions\/seam-2\.html"[^>]*data-start="30\.000"[^>]*data-duration="30\.000"/);
  });

  it("uses exactly four distinct track indexes (video=0, captions=1, audio=2, seam=3)", () => {
    const trackIndexes = [...html.matchAll(/data-track-index="(\d+)"/g)].map((m) => Number(m[1]));
    expect(new Set(trackIndexes)).toEqual(new Set([0, 1, 2, 3]));
  });

  it("emits all seams on a single track index (3)", () => {
    const seamClipMatches = html.match(/data-composition-src="compositions\/seam-\d+\.html"[\s\S]*?data-track-index="(\d+)"/g);
    expect(seamClipMatches).not.toBeNull();
    for (const clip of seamClipMatches!) {
      const m = clip.match(/data-track-index="(\d+)"/);
      expect(m![1]).toBe("3");
    }
  });

  it("inlines literal hex/RGBA on captured elements (no var() in body styles)", () => {
    // The :root { --… } declarations are documentation only; the body's own
    // style attributes must use literal values for shader-compat.
    const bodyStyleMatch = html.match(/<style>[\s\S]*?<\/style>/);
    expect(bodyStyleMatch).toBeTruthy();
    const styleBlock = bodyStyleMatch![0];
    const bodyRule = styleBlock.match(/html,\s*body\s*\{[^}]*\}/);
    expect(bodyRule).toBeTruthy();
    expect(bodyRule![0]).not.toMatch(/var\(--/);
  });
});
