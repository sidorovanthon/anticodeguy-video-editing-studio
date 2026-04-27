import { describe, it, expect } from "vitest";
import { buildCompositionHtml } from "../src/composer.js";
import { loadTranscript } from "../src/transcript.js";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { SeamPlan } from "../src/types.js";

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
});
