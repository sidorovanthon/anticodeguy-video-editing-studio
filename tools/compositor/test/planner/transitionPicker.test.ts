// tools/compositor/test/planner/transitionPicker.test.ts
import { describe, it, expect } from "vitest";
import { pickTransition, type TransitionPickerState } from "../../src/planner/transitionPicker.js";

describe("transitionPicker", () => {
  it("calm + main → primary crossfade", () => {
    const st: TransitionPickerState = { totalScenes: 8, accentsUsed: 0 };
    expect(pickTransition({ energyHint: "calm", narrativePosition: "main" }, "crossfade", st)).toBe("crossfade");
  });

  it("high + topic_change → an accent, increments counter", () => {
    const st: TransitionPickerState = { totalScenes: 10, accentsUsed: 0 };
    const t = pickTransition({ energyHint: "high", narrativePosition: "topic_change" }, "crossfade", st);
    expect(t).not.toBe("crossfade");
    expect(st.accentsUsed).toBe(1);
  });

  it("reverts to primary once accent budget is spent", () => {
    const st: TransitionPickerState = { totalScenes: 10, accentsUsed: 3 };
    expect(pickTransition({ energyHint: "high", narrativePosition: "topic_change" }, "crossfade", st)).toBe("crossfade");
    expect(st.accentsUsed).toBe(3);
  });

  it("outro returns primary even at high energy", () => {
    const st: TransitionPickerState = { totalScenes: 5, accentsUsed: 0 };
    expect(pickTransition({ energyHint: "high", narrativePosition: "outro" }, "crossfade", st)).toBe("crossfade");
  });
});
