import { describe, it, expect } from "vitest";
import { groupWords } from "../src/groupWords.js";

describe("groupWords (medium-energy default)", () => {
  it("breaks on a >120ms gap to the next word", () => {
    const words = [
      { text: "one",   startMs: 0,    endMs: 200 },
      { text: "two",   startMs: 220,  endMs: 400 },
      { text: "three", startMs: 600,  endMs: 800 },
    ];
    const groups = groupWords(words, { maxWordsPerGroup: 5, breakAfterPauseMs: 120 });
    expect(groups).toHaveLength(2);
    expect(groups[0].words.map((w) => w.text)).toEqual(["one", "two"]);
    expect(groups[1].words.map((w) => w.text)).toEqual(["three"]);
  });

  it("caps group size at maxWordsPerGroup even without a pause", () => {
    const words = Array.from({ length: 7 }, (_, i) => ({ text: `w${i}`, startMs: i * 100, endMs: i * 100 + 80 }));
    const groups = groupWords(words, { maxWordsPerGroup: 5, breakAfterPauseMs: 120 });
    expect(groups).toHaveLength(2);
    expect(groups[0].words).toHaveLength(5);
    expect(groups[1].words).toHaveLength(2);
  });

  it("sets group.startMs to first word.startMs and group.endMs to last word.endMs", () => {
    const words = [
      { text: "a", startMs: 100, endMs: 200 },
      { text: "b", startMs: 220, endMs: 380 },
    ];
    const [g] = groupWords(words, { maxWordsPerGroup: 5, breakAfterPauseMs: 120 });
    expect(g.startMs).toBe(100);
    expect(g.endMs).toBe(380);
  });

  it("returns an empty array on empty input", () => {
    expect(groupWords([], { maxWordsPerGroup: 5, breakAfterPauseMs: 120 })).toEqual([]);
  });

  it("assigns sequential ids g0, g1, g2…", () => {
    const words = [
      { text: "a", startMs: 0, endMs: 100 },
      { text: "b", startMs: 300, endMs: 400 },
      { text: "c", startMs: 600, endMs: 700 },
    ];
    const groups = groupWords(words, { maxWordsPerGroup: 5, breakAfterPauseMs: 120 });
    expect(groups.map((g) => g.id)).toEqual(["g0", "g1", "g2"]);
  });
});
