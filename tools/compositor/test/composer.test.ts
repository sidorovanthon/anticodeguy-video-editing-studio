import { describe, it, expect } from "vitest";
import { buildCompositionHtml } from "../src/composer.js";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { SeamPlan, MasterBundle } from "../src/types.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function makeBundle(words: MasterBundle["transcript"]["words"], durationMs: number): MasterBundle {
  return {
    schemaVersion: 1,
    slug: "demo",
    master: { durationMs, width: 1440, height: 2560, fps: 60 },
    boundaries: [
      { atMs: 0, kind: "start" },
      { atMs: durationMs, kind: "end" },
    ],
    transcript: { language: "en", words },
  };
}

describe("buildCompositionHtml", () => {
  it("includes master video src, caption layer, seam fragment, and HyperFrames root attributes", () => {
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
      bundle: makeBundle(
        [
          { text: "Hello", startMs: 0,    endMs: 350 },
          { text: "world", startMs: 380,  endMs: 720 },
          { text: "today", startMs: 1100, endMs: 1480 },
        ],
        1500,
      ),
      masterRelPath: "../master.mp4",
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

  it("emits caption words as start_ms/end_ms (component boundary conversion)", () => {
    const plan: SeamPlan = { episode_slug: "demo", master_duration_ms: 5000, seams: [] };
    const html = buildCompositionHtml({
      repoRoot: path.resolve(__dirname, "../../.."),
      episodeDir: path.resolve(__dirname, "fixtures"),
      plan,
      bundle: makeBundle(
        [
          { text: "alpha",   startMs: 0,    endMs: 500 },
          { text: "charlie", startMs: 3000, endMs: 3500 },
        ],
        5000,
      ),
      masterRelPath: "../master.mp4",
    });
    expect(html).toContain('"text":"alpha","start_ms":0,"end_ms":500');
    expect(html).toContain('"text":"charlie","start_ms":3000,"end_ms":3500');
  });
});
