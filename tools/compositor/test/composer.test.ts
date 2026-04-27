import { describe, it, expect } from "vitest";
import { buildCompositionHtml } from "../src/composer.js";
import { loadTranscript } from "../src/transcript.js";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { SeamPlan, Transcript } from "../src/types.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

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
          scene: "full",
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
    });

    // Original plan assertions
    expect(html).toContain('src="../master.mp4"');
    expect(html).toContain('data-component="title-card"');
    expect(html).toContain('data-component="caption-karaoke"');
    expect(html).toContain("--video-width: 1440");

    // HyperFrames adaptation assertions
    expect(html).toContain('data-composition-id="main"');
    expect(html).toContain('data-width="1440"');
    expect(html).toContain('data-height="2560"');
    expect(html).toContain("muted");
    expect(html).toContain('data-has-audio="true"');
  });

  it("normalizes ElevenLabs-native start/end (seconds) to start_ms/end_ms (rounded ms) in the embedded caption JSON", () => {
    const transcript: Transcript = {
      words: [
        { text: "Hello", start: 0, end: 0.3504 },
        { text: "world", start: 0.381, end: 0.7201 },
      ],
      duration_ms: 1500,
    };
    const plan: SeamPlan = {
      episode_slug: "demo",
      master_duration_ms: 1500,
      seams: [],
    };
    const html = buildCompositionHtml({
      repoRoot: path.resolve(__dirname, "../../.."),
      episodeDir: path.resolve(__dirname, "fixtures"),
      plan,
      transcript,
      masterRelPath: "../master.mp4",
    });

    expect(html).toContain(
      '[{"text":"Hello","start_ms":0,"end_ms":350},{"text":"world","start_ms":381,"end_ms":720}]',
    );
    // Raw seconds-form fields must NOT leak into the embedded JSON.
    expect(html).not.toMatch(/"start":0\.3504/);
  });

  it("passes start_ms/end_ms words through unchanged in the embedded caption JSON", () => {
    const transcript: Transcript = {
      words: [
        { text: "Hello", start_ms: 0, end_ms: 350 },
        { text: "world", start_ms: 380, end_ms: 720 },
      ],
      duration_ms: 1500,
    };
    const plan: SeamPlan = {
      episode_slug: "demo",
      master_duration_ms: 1500,
      seams: [],
    };
    const html = buildCompositionHtml({
      repoRoot: path.resolve(__dirname, "../../.."),
      episodeDir: path.resolve(__dirname, "fixtures"),
      plan,
      transcript,
      masterRelPath: "../master.mp4",
    });

    expect(html).toContain(
      '[{"text":"Hello","start_ms":0,"end_ms":350},{"text":"world","start_ms":380,"end_ms":720}]',
    );
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
      }),
    ).toThrow(/Word missing timing.*Hello/);
  });
});
