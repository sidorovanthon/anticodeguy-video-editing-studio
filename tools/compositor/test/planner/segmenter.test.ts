// tools/compositor/test/planner/segmenter.test.ts
import { describe, it, expect } from "vitest";
import { segment, type SubagentDispatcher } from "../../src/planner/segmenter.js";

const SCRIPT = `Hello today the topic is DRM. There are three approaches that ship in the wild. Each one breaks differently. Let me show you why.`;
const WORDS = SCRIPT.split(/\s+/).map((text, i) => ({
  startMs: i * 250, endMs: i * 250 + 200, text,
}));

const RESPONSE = JSON.stringify([
  { beat_id: "B1", beat_summary: "Intro", narrative_position: "opening",
    energy_hint: "medium", mood_hint: null, script_start_offset: 0, script_end_offset: 30 },
  { beat_id: "B2", beat_summary: "Three approaches", narrative_position: "main",
    energy_hint: "medium", mood_hint: null, script_start_offset: 30, script_end_offset: SCRIPT.length },
]);

class StubDispatcher implements SubagentDispatcher {
  constructor(private responses: string[]) {}
  async run(_p: string): Promise<string> {
    const r = this.responses.shift();
    if (!r) throw new Error("stub exhausted");
    return r;
  }
}

describe("segmenter", () => {
  it("produces scenes from a recorded beat-pass response", async () => {
    const d = new StubDispatcher([RESPONSE]);
    const scenes = await segment({
      script: SCRIPT, words: WORDS, masterDurationMs: WORDS.at(-1)!.endMs, dispatcher: d,
    });
    expect(scenes.length).toBeGreaterThanOrEqual(2);
    expect(scenes[0].beatId).toBe("B1");
    expect(scenes[0].narrativePosition).toBe("opening");
  });

  it("retries on invalid JSON, then succeeds", async () => {
    const d = new StubDispatcher(["not json", RESPONSE]);
    const scenes = await segment({
      script: SCRIPT, words: WORDS, masterDurationMs: WORDS.at(-1)!.endMs,
      dispatcher: d, maxRetries: 2,
    });
    expect(scenes.length).toBeGreaterThanOrEqual(2);
  });

  it("aborts after maxRetries with all-invalid responses", async () => {
    const d = new StubDispatcher(["not json", "bad", "[]"]);
    await expect(segment({
      script: SCRIPT, words: WORDS, masterDurationMs: WORDS.at(-1)!.endMs,
      dispatcher: d, maxRetries: 2,
    })).rejects.toThrow();
  });
});
