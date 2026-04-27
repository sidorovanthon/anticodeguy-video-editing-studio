import { describe, it, expect } from "vitest";
import { planSeams } from "../src/seamPlanner.js";

describe("planSeams", () => {
  it("starts with full scene at seam 0", () => {
    const seams = planSeams([0, 5000, 10000], 15000);
    expect(seams[0].scene).toBe("full");
    expect(seams[0].at_ms).toBe(0);
  });

  it("never produces forbidden transitions", () => {
    const ats = [0, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000];
    const seams = planSeams(ats, 9000);
    const forbidden = new Set([
      "head>head",
      "head>overlay",
      "overlay>head",
      "overlay>overlay",
      "split>split",
      "full>full",
    ]);
    for (let i = 1; i < seams.length; i++) {
      const key = `${seams[i - 1].scene}>${seams[i].scene}`;
      expect(forbidden.has(key)).toBe(false);
    }
  });

  it("computes ends_at_ms as next seam at_ms or master_duration_ms", () => {
    const seams = planSeams([0, 4000, 9000], 12000);
    expect(seams[0].ends_at_ms).toBe(4000);
    expect(seams[1].ends_at_ms).toBe(9000);
    expect(seams[2].ends_at_ms).toBe(12000);
  });
});
