import { describe, it, expect } from "vitest";
import { writeSeamPlan, readSeamPlan } from "../src/seamPlanWriter.js";
import type { SeamPlan } from "../src/types.js";

describe("seam plan markdown round-trip", () => {
  const plan: SeamPlan = {
    episode_slug: "ep-001",
    master_duration_ms: 12000,
    seams: [
      { index: 0, at_ms: 0, scene: "broll", ends_at_ms: 4000 },
      {
        index: 1,
        at_ms: 4000,
        scene: "split",
        ends_at_ms: 9000,
        graphic: { component: "TitleCard", data: { title: "Hello" } },
      },
      { index: 2, at_ms: 9000, scene: "head", ends_at_ms: 12000 },
    ],
  };

  it("contains scene labels in markdown output", () => {
    const md = writeSeamPlan(plan);
    expect(md).toContain("scene: broll");
    expect(md).toContain("scene: split");
    expect(md).toContain("scene: head");
    expect(md).toContain("ep-001");
    expect(md).toContain("duration=12000ms");
  });

  it("round-trips a SeamPlan through markdown", () => {
    const md = writeSeamPlan(plan);
    const parsed = readSeamPlan(md);
    expect(parsed.episode_slug).toBe(plan.episode_slug);
    expect(parsed.master_duration_ms).toBe(plan.master_duration_ms);
    expect(parsed.seams).toHaveLength(plan.seams.length);
    expect(parsed.seams[0].scene).toBe("broll");
    expect(parsed.seams[1].scene).toBe("split");
    expect(parsed.seams[1].graphic?.component).toBe("TitleCard");
    expect(parsed.seams[1].graphic?.data).toEqual({ title: "Hello" });
    expect(parsed.seams[2].ends_at_ms).toBe(12000);
  });
});
