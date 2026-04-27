import { describe, it, expect } from "vitest";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildBundle } from "../src/stage1/writeBundle.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixtures = path.resolve(__dirname, "fixtures");

const fakeProbe = () => ({ durationMs: 2500, width: 1440, height: 2560, fps: 60 });

describe("buildBundle", () => {
  it("produces a master-aligned bundle from transcript + EDL + injected probe", () => {
    const bundle = buildBundle({
      slug: "demo",
      transcriptPath: path.join(fixtures, "transcript.sample.json"),
      edlPath: path.join(fixtures, "edl.sample.json"),
      masterPath: "/unused/master.mp4",
      probeMaster: fakeProbe,
    });
    expect(bundle.schemaVersion).toBe(1);
    expect(bundle.slug).toBe("demo");
    expect(bundle.master).toEqual({ durationMs: 2500, width: 1440, height: 2560, fps: 60 });
  });

  it("derives N+1 boundaries from N EDL ranges (start + N-1 seams + end)", () => {
    const bundle = buildBundle({
      slug: "demo",
      transcriptPath: path.join(fixtures, "transcript.sample.json"),
      edlPath: path.join(fixtures, "edl.sample.json"),
      masterPath: "/unused/master.mp4",
      probeMaster: fakeProbe,
    });
    expect(bundle.boundaries).toEqual([
      { atMs: 0, kind: "start" },
      { atMs: 1500, kind: "seam" },
      { atMs: 2500, kind: "end" },
    ]);
  });

  it("emits master-aligned word timings (raw -> master via EDL)", () => {
    const bundle = buildBundle({
      slug: "demo",
      transcriptPath: path.join(fixtures, "transcript.sample.json"),
      edlPath: path.join(fixtures, "edl.sample.json"),
      masterPath: "/unused/master.mp4",
      probeMaster: fakeProbe,
    });
    expect(bundle.transcript.words).toEqual([
      { text: "Hello", startMs: 0,    endMs: 350 },
      { text: "world", startMs: 380,  endMs: 720 },
      { text: "today", startMs: 1100, endMs: 1480 },
    ]);
  });

  it("uses 'en' as the default transcript language", () => {
    const bundle = buildBundle({
      slug: "demo",
      transcriptPath: path.join(fixtures, "transcript.sample.json"),
      edlPath: path.join(fixtures, "edl.sample.json"),
      masterPath: "/unused/master.mp4",
      probeMaster: fakeProbe,
    });
    expect(bundle.transcript.language).toBe("en");
  });
});
