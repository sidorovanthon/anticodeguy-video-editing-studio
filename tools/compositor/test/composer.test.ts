import { describe, it, expect } from "vitest";
import { buildCompositionHtml } from "../src/composer.js";
import { loadTranscript } from "../src/transcript.js";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { SeamPlan, Transcript } from "../src/types.js";
import type { Edl } from "../src/edl.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Identity EDL: master == raw, 0..1.5s, so existing fixture timings pass through
const identityEdl: Edl = {
  version: 1,
  sources: { raw: "raw.mp4" },
  ranges: [{ source: "raw", start: 0, end: 1.5 }],
};

describe("buildCompositionHtml", () => {
  it("includes master video src, caption layer, seam fragment, and HyperFrames root attributes", () => {
    const transcript = loadTranscript(
      path.resolve(__dirname, "fixtures/transcript.sample.json"),
    );
    const plan: SeamPlan = {
      episode_slug: "demo",
      master_duration_ms: 1500,
      seams: [
        {
          index: 0,
          at_ms: 0,
          ends_at_ms: 1500,
          scene: "broll",
          graphic: { component: "title-card", data: { title: "Demo", subtitle: "Test" } },
        },
      ],
    };
    const html = buildCompositionHtml({
      repoRoot: path.resolve(__dirname, "../../.."),
      episodeDir: path.resolve(__dirname, "fixtures"),
      plan,
      transcript,
      masterRelPath: "../master.mp4",
      edl: identityEdl,
    });

    expect(html).toContain('src="../master.mp4"');
    expect(html).toContain('data-component="title-card"');
    expect(html).toContain('data-component="caption-karaoke"');
    expect(html).toContain("--video-width: 1440");

    expect(html).toContain('data-composition-id="main"');
    expect(html).toContain('data-width="1440"');
    expect(html).toContain('data-height="2560"');
    expect(html).toContain("muted");
    expect(html).toContain('data-has-audio="true"');
  });

  it("remaps raw-timeline word timings to master timeline via EDL", () => {
    // EDL: keep raw [2.0,5.0] → master [0,3.0]; and [10.0,12.0] → master [3.0,5.0]
    const edl: Edl = {
      version: 1,
      sources: { raw: "raw.mp4" },
      ranges: [
        { source: "raw", start: 2.0, end: 5.0 },
        { source: "raw", start: 10.0, end: 12.0 },
      ],
    };
    const transcript: Transcript = {
      words: [
        { text: "alpha", start: 2.5, end: 3.0 },
        { text: "charlie", start: 10.5, end: 11.0 },
      ],
      duration_ms: 5000,
    };
    const plan: SeamPlan = {
      episode_slug: "demo",
      master_duration_ms: 5000,
      seams: [],
    };
    const html = buildCompositionHtml({
      repoRoot: path.resolve(__dirname, "../../.."),
      episodeDir: path.resolve(__dirname, "fixtures"),
      plan,
      transcript,
      masterRelPath: "../master.mp4",
      edl,
    });

    expect(html).toContain(
      '[{"text":"alpha","start_ms":500,"end_ms":1000},{"text":"charlie","start_ms":3500,"end_ms":4000}]',
    );
    // Raw timings must NOT leak into the embedded JSON
    expect(html).not.toMatch(/"start_ms":2500/);
    expect(html).not.toMatch(/"start_ms":10500/);
  });

  it("excludes words whose raw start falls in a dropped EDL segment", () => {
    const edl: Edl = {
      version: 1,
      sources: { raw: "raw.mp4" },
      ranges: [
        { source: "raw", start: 2.0, end: 5.0 },
        { source: "raw", start: 10.0, end: 12.0 },
      ],
    };
    const transcript: Transcript = {
      words: [
        { text: "alpha", start: 2.5, end: 3.0 },
        { text: "gap", start: 7.0, end: 7.5 },
        { text: "charlie", start: 10.5, end: 11.0 },
      ],
      duration_ms: 5000,
    };
    const plan: SeamPlan = {
      episode_slug: "demo",
      master_duration_ms: 5000,
      seams: [],
    };
    const html = buildCompositionHtml({
      repoRoot: path.resolve(__dirname, "../../.."),
      episodeDir: path.resolve(__dirname, "fixtures"),
      plan,
      transcript,
      masterRelPath: "../master.mp4",
      edl,
    });

    expect(html).not.toContain('"text":"gap"');
    expect(html).toContain('"text":"alpha"');
    expect(html).toContain('"text":"charlie"');
  });

  it("throws a clear error when a word has neither start_ms/end_ms nor start/end", () => {
    const transcript: Transcript = {
      words: [{ text: "Hello" } as unknown as Transcript["words"][number]],
      duration_ms: 1500,
    };
    const plan: SeamPlan = {
      episode_slug: "demo",
      master_duration_ms: 1500,
      seams: [],
    };
    expect(() =>
      buildCompositionHtml({
        repoRoot: path.resolve(__dirname, "../../.."),
        episodeDir: path.resolve(__dirname, "fixtures"),
        plan,
        transcript,
        masterRelPath: "../master.mp4",
        edl: identityEdl,
      }),
    ).toThrow(/Word missing timing.*Hello/);
  });
});
