// tools/compositor/test/planner/integration.test.ts
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseSeamPlan, writeSeamPlan } from "../../src/planner/seamPlanFormat.js";
import { validateSeamPlan } from "../../src/planner/modeValidator.js";

const FIXTURE_DIR = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "fixtures/integration",
);

function readPlan() {
  return parseSeamPlan(readFileSync(path.join(FIXTURE_DIR, "expected-seam-plan.md"), "utf-8"));
}

describe("planner integration fixture", () => {
  it("the expected seam-plan parses and passes the validator", () => {
    const plan = readPlan();
    expect(plan.scenes.length).toBeGreaterThanOrEqual(8);
    expect(() => validateSeamPlan(plan, new Map())).not.toThrow();
  });

  it("round-trips parse → write → parse identically", () => {
    const plan = readPlan();
    expect(parseSeamPlan(writeSeamPlan(plan))).toEqual(plan);
  });

  it("contains at least three same-mode scenes with distinct briefs", () => {
    const plan = readPlan();
    const broll = plan.scenes.filter(s => s.mode === "broll" && s.graphic.kind === "generative");
    expect(broll.length).toBeGreaterThanOrEqual(3);
    const briefs = new Set(broll.map(s => (s.graphic as any).brief.trim()));
    expect(briefs.size).toBe(broll.length);
  });

  it("ends with outro = overlay + catalog/subscribe-cta", () => {
    const plan = readPlan();
    const last = plan.scenes.at(-1)!;
    expect(last.narrativePosition).toBe("outro");
    expect(last.mode).toBe("overlay");
    expect(last.graphic.kind).toBe("catalog");
    if (last.graphic.kind === "catalog") expect(last.graphic.name).toBe("subscribe-cta");
  });
});
