// tools/compositor/test/planner/decorator.test.ts
import { describe, it, expect } from "vitest";
import { decorate } from "../../src/planner/decorator.js";
import type { Scene } from "../../src/planner/types.js";
import type { SubagentDispatcher } from "../../src/planner/segmenter.js";

class Stub implements SubagentDispatcher {
  constructor(private r: string) {}
  async run(_p: string): Promise<string> { return this.r; }
}

const SCENES: Scene[] = [
  { startMs: 0, endMs: 4000, beatId: "B1", narrativePosition: "opening", energyHint: "medium",
    keyPhrase: "intro", scriptChunk: "Hello, today..." },
  { startMs: 4000, endMs: 8000, beatId: "B2", narrativePosition: "main", energyHint: "medium",
    keyPhrase: "three approaches", scriptChunk: "Three ways..." },
];

const RESPONSE = JSON.stringify([
  { scene_index: 0, mode: "head", graphic: { source: "none" } },
  { scene_index: 1, mode: "split", graphic: { source: "generative", brief: "side panel" } },
]);

describe("decorator", () => {
  it("returns enriched scenes with mode + transition + graphic", async () => {
    const d = new Stub(RESPONSE);
    const enriched = await decorate({
      scenes: SCENES, seamsInsideByScene: new Map(),
      designMd: "calm frosted-glass", catalogTable: "(test)",
      projectPrimaryTransition: "crossfade", dispatcher: d,
    });
    expect(enriched).toHaveLength(2);
    expect(enriched[0].mode).toBe("head");
    expect(enriched[1].mode).toBe("split");
    expect(enriched[0].transitionOut).toBe("crossfade");
  });

  it("rejects decorator output outside the candidate set", async () => {
    const scenes: Scene[] = [{
      startMs: 0, endMs: 4000, beatId: "B1", narrativePosition: "outro", energyHint: "calm",
      keyPhrase: "thanks", scriptChunk: "Thanks for watching",
    }];
    const d = new Stub(JSON.stringify([
      { scene_index: 0, mode: "head", graphic: { source: "none" } },
    ]));
    await expect(decorate({
      scenes, seamsInsideByScene: new Map(),
      designMd: "x", catalogTable: "x", projectPrimaryTransition: "crossfade", dispatcher: d,
    })).rejects.toThrow(/not in candidate set/);
  });
});
