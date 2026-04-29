// tools/compositor/test/planner/seamPlanFormat.test.ts
import { describe, it, expect } from "vitest";
import { parseSeamPlan, writeSeamPlan } from "../../src/planner/seamPlanFormat.js";

const SAMPLE = `# Seam plan: 2026-04-28-test (master_duration_ms=8800)

## Scene 1
- start_ms: 0
- end_ms: 4200
- beat_id: B1
- narrative_position: opening
- energy_hint: medium
- mode: head
- transition_out: crossfade
- key_phrase: "DRM is a moving target"
- graphic:
  - source: none

  script: |
    Hello, today we're talking about desktop software licensing
    and why every approach is wrong in a different way.

## Scene 2
- start_ms: 4200
- end_ms: 8800
- beat_id: B1
- narrative_position: setup
- energy_hint: medium
- mode: split
- transition_out: push-slide
- key_phrase: "three approaches"
- graphic:
  - source: generative
  - brief: |
      Right-side panel: three labelled vertical columns sliding in
      left-to-right with 120 ms staggers.

  script: |
    There are basically three approaches that actually ship in the wild...
`;

describe("seamPlanFormat", () => {
  it("parses the sample document", () => {
    const plan = parseSeamPlan(SAMPLE);
    expect(plan.slug).toBe("2026-04-28-test");
    expect(plan.masterDurationMs).toBe(8800);
    expect(plan.scenes).toHaveLength(2);
    expect(plan.scenes[0].mode).toBe("head");
    expect(plan.scenes[0].graphic.kind).toBe("none");
    expect(plan.scenes[1].mode).toBe("split");
    expect(plan.scenes[1].graphic.kind).toBe("generative");
    if (plan.scenes[1].graphic.kind === "generative") {
      expect(plan.scenes[1].graphic.brief).toContain("Right-side panel");
    }
    expect(plan.scenes[1].keyPhrase).toBe("three approaches");
  });

  it("round-trips: parse → write → parse yields the same plan", () => {
    const plan = parseSeamPlan(SAMPLE);
    const re = writeSeamPlan(plan);
    expect(parseSeamPlan(re)).toEqual(plan);
  });

  it("rejects scenes that exceed the 5s cap", () => {
    const broken = SAMPLE.replace("end_ms: 4200", "end_ms: 6500");
    expect(() => parseSeamPlan(broken)).toThrow(/exceeds 5s cap/i);
  });

  it("rejects an unknown narrative_position", () => {
    const broken = SAMPLE.replace("narrative_position: opening", "narrative_position: warmup");
    expect(() => parseSeamPlan(broken)).toThrow(/narrative_position/i);
  });

  it("rejects a generative scene without brief", () => {
    const broken = SAMPLE
      .replace(/  - source: generative\s*\n\s*- brief:[\s\S]*?\n\n/, "  - source: generative\n\n");
    expect(() => parseSeamPlan(broken)).toThrow(/generative.*brief/i);
  });
});
