import { describe, it, expect } from "vitest";
import { snapScenes, computePhraseBoundaries } from "../../src/planner/snap.js";
import type { Scene } from "../../src/planner/types.js";

const WORDS = [
  { startMs: 0,    endMs: 350,  text: "Hello" },
  { startMs: 380,  endMs: 720,  text: "today" },
  { startMs: 1100, endMs: 1480, text: "the" },     // gap 380 before → boundary at 910
  { startMs: 1500, endMs: 1900, text: "topic" },
  { startMs: 2050, endMs: 2400, text: "is" },          // gap 150 ≤ minGap → no boundary
  { startMs: 2700, endMs: 3300, text: "DRM" },     // gap 300 before → boundary at 2550
  { startMs: 4400, endMs: 4900, text: "fin" },     // gap 1100 → boundary at 3850
];

describe("snap pass", () => {
  it("computes phrase boundaries from gaps > 150ms", () => {
    const bs = computePhraseBoundaries(WORDS, 150);
    expect(bs).toEqual([910, 2550, 3850]);
  });

  it("snaps a boundary within ±300ms tolerance", () => {
    const scenes: Scene[] = [
      { startMs: 0, endMs: 1000, beatId: "B1", narrativePosition: "opening",
        energyHint: "medium", keyPhrase: "p", scriptChunk: "x" },
      { startMs: 1000, endMs: 5000, beatId: "B1", narrativePosition: "main",
        energyHint: "medium", keyPhrase: "p2", scriptChunk: "y" },
    ];
    const snapped = snapScenes(scenes, [910, 2550, 3850], 300);
    expect(snapped[0].endMs).toBe(910);
    expect(snapped[1].startMs).toBe(910);
  });

  it("leaves boundary unchanged when no phrase boundary is within tolerance", () => {
    const scenes: Scene[] = [
      { startMs: 0, endMs: 5000, beatId: "B1", narrativePosition: "opening",
        energyHint: "medium", keyPhrase: "p", scriptChunk: "x" },
      { startMs: 5000, endMs: 10000, beatId: "B1", narrativePosition: "main",
        energyHint: "medium", keyPhrase: "p2", scriptChunk: "y" },
    ];
    const snapped = snapScenes(scenes, [910, 2550, 3850], 300);
    expect(snapped[0].endMs).toBe(5000);
  });

  it("preserves monotonic ordering", () => {
    const scenes: Scene[] = [
      { startMs: 0, endMs: 800, beatId: "B1", narrativePosition: "opening",
        energyHint: "medium", keyPhrase: "p", scriptChunk: "x" },
      { startMs: 800, endMs: 4000, beatId: "B1", narrativePosition: "main",
        energyHint: "medium", keyPhrase: "p2", scriptChunk: "y" },
    ];
    const snapped = snapScenes(scenes, [910], 300);
    expect(snapped[0].endMs).toBeLessThan(snapped[1].endMs);
  });
});
