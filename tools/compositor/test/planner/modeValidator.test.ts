// tools/compositor/test/planner/modeValidator.test.ts
import { describe, it, expect } from "vitest";
import { validateSeamPlan } from "../../src/planner/modeValidator.js";
import type { SeamPlan, EnrichedScene } from "../../src/planner/types.js";

function scene(o: Partial<EnrichedScene>): EnrichedScene {
  return {
    startMs: 0, endMs: 4000, beatId: "B1",
    narrativePosition: "main", energyHint: "medium",
    keyPhrase: "p", scriptChunk: "s",
    mode: "head", transitionOut: "crossfade",
    graphic: { kind: "none" },
    ...o,
  };
}

const noSeams = new Map<number, number>();

describe("modeValidator", () => {
  it("accepts a valid two-scene plan", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 8000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "head" }),
      scene({ startMs: 4000, endMs: 8000, mode: "split", graphic: { kind: "generative", brief: "x" } }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).not.toThrow();
  });

  it("rejects head→head", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 8000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "head" }),
      scene({ startMs: 4000, endMs: 8000, mode: "head" }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).toThrow(/head→head/);
  });

  it("rejects head→overlay", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 8000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "head" }),
      scene({ startMs: 4000, endMs: 8000, mode: "overlay",
              graphic: { kind: "catalog", name: "subscribe-cta" } }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).toThrow(/head→overlay|overlay→head/);
  });

  it("rejects overlay→overlay", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 8000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "overlay",
              graphic: { kind: "catalog", name: "lower-third" } }),
      scene({ startMs: 4000, endMs: 8000, mode: "overlay",
              graphic: { kind: "catalog", name: "subscribe-cta" } }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).toThrow(/overlay→overlay/);
  });

  it("rejects same-graphic split→split", () => {
    const g = { kind: "generative" as const, brief: "same brief" };
    const plan: SeamPlan = { slug: "t", masterDurationMs: 8000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "split", graphic: g }),
      scene({ startMs: 4000, endMs: 8000, mode: "split", graphic: g }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).toThrow(/same-graphic split/);
  });

  it("rejects same-graphic broll→broll", () => {
    const g = { kind: "generative" as const, brief: "identical broll brief" };
    const plan: SeamPlan = { slug: "t", masterDurationMs: 8000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "broll", graphic: g }),
      scene({ startMs: 4000, endMs: 8000, mode: "broll", graphic: g }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).toThrow(/same-graphic broll/);
  });

  it("accepts broll→broll with different briefs", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 8000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "broll",
              graphic: { kind: "generative", brief: "first broll" } }),
      scene({ startMs: 4000, endMs: 8000, mode: "broll",
              graphic: { kind: "generative", brief: "second broll" } }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).not.toThrow();
  });

  it("rejects split with graphic.kind=none", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 4000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "split", graphic: { kind: "none" } }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).toThrow(/split requires a graphic/);
  });

  it("rejects broll with graphic.kind=none", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 4000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "broll", graphic: { kind: "none" } }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).toThrow(/broll requires a graphic/);
  });

  it("rejects overlay with graphic.kind=none", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 4000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "overlay", graphic: { kind: "none" } }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).toThrow(/overlay requires a graphic/);
  });

  it("rejects head with seamsInside>1", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 4000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "head" }),
    ]};
    const seams = new Map([[0, 3]]);
    expect(() => validateSeamPlan(plan, seams)).toThrow(/seamsInside.*head/);
  });

  it("rejects outro that is not overlay+subscribe-cta", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 4000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "head", narrativePosition: "outro" }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).toThrow(/outro/);
  });

  it("rejects short scene with non-{head,overlay} mode", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 4000, scenes: [
      scene({ startMs: 0, endMs: 1200, mode: "split",
              graphic: { kind: "generative", brief: "x" } }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).toThrow(/short scene/);
  });
});
