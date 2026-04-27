import { describe, it, expect } from "vitest";
import { writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { loadEdl, remapWordsToMaster, type Edl } from "../src/edl.js";

function writeTempEdl(obj: unknown): string {
  const dir = mkdtempSync(path.join(tmpdir(), "edl-test-"));
  const p = path.join(dir, "edl.json");
  writeFileSync(p, JSON.stringify(obj));
  return p;
}

describe("loadEdl", () => {
  it("parses a minimal valid file", () => {
    const p = writeTempEdl({
      version: 1,
      sources: { raw: "raw.mp4" },
      ranges: [{ source: "raw", start: 0, end: 2 }],
    });
    const edl = loadEdl(p);
    expect(edl.version).toBe(1);
    expect(edl.ranges).toHaveLength(1);
    expect(edl.ranges[0]).toMatchObject({ source: "raw", start: 0, end: 2 });
  });

  it("throws on missing ranges", () => {
    const p = writeTempEdl({ version: 1, sources: {} });
    expect(() => loadEdl(p)).toThrow(/ranges/i);
  });

  it("throws on empty ranges", () => {
    const p = writeTempEdl({ version: 1, sources: {}, ranges: [] });
    expect(() => loadEdl(p)).toThrow(/ranges/i);
  });

  it("throws when end <= start", () => {
    const p = writeTempEdl({
      version: 1,
      sources: {},
      ranges: [{ source: "raw", start: 5, end: 5 }],
    });
    expect(() => loadEdl(p)).toThrow(/end.*start/i);
  });

  it("throws when version is not a number", () => {
    const p = writeTempEdl({
      version: "1",
      sources: {},
      ranges: [{ source: "raw", start: 0, end: 1 }],
    });
    expect(() => loadEdl(p)).toThrow(/version/i);
  });
});

describe("remapWordsToMaster", () => {
  const edl: Edl = {
    version: 1,
    sources: { raw: "raw.mp4" },
    ranges: [
      { source: "raw", start: 2.0, end: 5.0 },
      { source: "raw", start: 10.0, end: 12.0 },
    ],
  };

  it("remaps words across two ranges and drops words in dropped segments", () => {
    const out = remapWordsToMaster(
      [
        { text: "alpha", start: 2.5, end: 3.0 },
        { text: "bravo", start: 4.5, end: 4.9 },
        { text: "gap", start: 7.0, end: 7.5 },
        { text: "charlie", start: 10.5, end: 11.0 },
        { text: "delta", start: 11.8, end: 12.3 },
      ],
      edl,
    );
    expect(out).toEqual([
      { text: "alpha", start_ms: 500, end_ms: 1000 },
      { text: "bravo", start_ms: 2500, end_ms: 2900 },
      { text: "charlie", start_ms: 3500, end_ms: 4000 },
      { text: "delta", start_ms: 4800, end_ms: 5000 },
    ]);
  });

  it("accepts start_ms/end_ms (raw ms) and converts to seconds for lookup", () => {
    const out = remapWordsToMaster(
      [{ text: "alpha", start_ms: 2500, end_ms: 3000 }],
      edl,
    );
    expect(out).toEqual([{ text: "alpha", start_ms: 500, end_ms: 1000 }]);
  });

  it("throws when a word has neither start/end nor start_ms/end_ms", () => {
    expect(() =>
      remapWordsToMaster(
        [{ text: "broken" } as unknown as { text: string }],
        edl,
      ),
    ).toThrow(/missing timing.*broken/i);
  });
});
