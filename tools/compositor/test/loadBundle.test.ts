import { describe, it, expect } from "vitest";
import { writeFileSync, mkdtempSync, mkdirSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadBundle, BundleSchemaError } from "../src/stage2/loadBundle.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixtures = path.resolve(__dirname, "fixtures");

function withBundleObject(obj: unknown): string {
  const dir = mkdtempSync(path.join(tmpdir(), "bundle-test-"));
  const masterDir = path.join(dir, "master");
  mkdirSync(masterDir, { recursive: true });
  writeFileSync(path.join(masterDir, "bundle.json"), JSON.stringify(obj));
  return dir;
}

describe("loadBundle", () => {
  it("loads a valid bundle from <episode>/master/bundle.json", () => {
    const validBundle = JSON.parse(
      readFileSync(path.join(fixtures, "bundle.sample.json"), "utf8"),
    );
    const dir = withBundleObject(validBundle);
    const bundle = loadBundle(dir);
    expect(bundle.slug).toBe("demo");
    expect(bundle.master.durationMs).toBe(2500);
    expect(bundle.transcript.words).toHaveLength(1);
  });

  it("rejects missing schemaVersion (drift class: schema versioning)", () => {
    const dir = withBundleObject({ slug: "x" });
    expect(() => loadBundle(dir)).toThrow(BundleSchemaError);
    expect(() => loadBundle(dir)).toThrow(/schemaVersion/);
  });

  it("rejects raw-timeline duration field (drift #1: audio_duration_secs)", () => {
    const bad = {
      schemaVersion: 1,
      slug: "x",
      master: { audio_duration_secs: 2.5, width: 1440, height: 2560, fps: 60 },
      boundaries: [],
      transcript: { language: "en", words: [] },
    };
    const dir = withBundleObject(bad);
    expect(() => loadBundle(dir)).toThrow(/master\.durationMs/);
  });

  it("rejects words with snake_case timings (drift #4: start/end vs startMs/endMs)", () => {
    const bad = {
      schemaVersion: 1,
      slug: "x",
      master: { durationMs: 2500, width: 1440, height: 2560, fps: 60 },
      boundaries: [
        { atMs: 0, kind: "start" },
        { atMs: 2500, kind: "end" },
      ],
      transcript: {
        language: "en",
        words: [{ text: "x", start_ms: 0, end_ms: 100 }],
      },
    };
    const dir = withBundleObject(bad);
    expect(() => loadBundle(dir)).toThrow(/transcript\.words\[0\]\.startMs/);
  });

  it("rejects boundary kind outside {start,seam,end}", () => {
    const bad = {
      schemaVersion: 1,
      slug: "x",
      master: { durationMs: 2500, width: 1440, height: 2560, fps: 60 },
      boundaries: [{ atMs: 0, kind: "begin" }, { atMs: 2500, kind: "end" }],
      transcript: { language: "en", words: [] },
    };
    const dir = withBundleObject(bad);
    expect(() => loadBundle(dir)).toThrow(/boundaries\[0\]\.kind/);
  });

  it("rejects last boundary not aligned to master.durationMs (drift #3)", () => {
    const bad = {
      schemaVersion: 1,
      slug: "x",
      master: { durationMs: 2500, width: 1440, height: 2560, fps: 60 },
      boundaries: [
        { atMs: 0, kind: "start" },
        { atMs: 9999, kind: "end" },
      ],
      transcript: { language: "en", words: [] },
    };
    const dir = withBundleObject(bad);
    expect(() => loadBundle(dir)).toThrow(/master\.durationMs/);
  });

  it("throws BundleSchemaError when the file is missing entirely", () => {
    const dir = mkdtempSync(path.join(tmpdir(), "bundle-test-empty-"));
    expect(() => loadBundle(dir)).toThrow(BundleSchemaError);
  });
});
