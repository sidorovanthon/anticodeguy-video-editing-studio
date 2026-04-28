import { describe, it, expect } from "vitest";
import { buildTransitionsHtml } from "../src/transitionsComposition.js";
import type { Seam } from "../src/types.js";

const seams: Seam[] = [
  { index: 0, at_ms: 0,     ends_at_ms: 7040,  scene: "broll" },
  { index: 1, at_ms: 7040,  ends_at_ms: 17480, scene: "split" },
  { index: 2, at_ms: 17480, ends_at_ms: 29420, scene: "head" },
];

describe("buildTransitionsHtml", () => {
  it("registers a window.__timelines['transitions'] entry", () => {
    const html = buildTransitionsHtml({
      seams,
      totalDurationMs: 29420,
      transition: { primary: "crossfade", duration: 0.4, easing: "power2.inOut" },
    });
    expect(html).toMatch(/window\.__timelines\["transitions"\]\s*=\s*tl/);
  });

  it("emits N-1 transition markers for N seams", () => {
    const html = buildTransitionsHtml({
      seams,
      totalDurationMs: 29420,
      transition: { primary: "crossfade", duration: 0.4, easing: "power2.inOut" },
    });
    const txMatches = html.match(/\/\* transition at /g) ?? [];
    expect(txMatches.length).toBe(2);
  });

  it("emits an empty template when seams.length < 2", () => {
    const html = buildTransitionsHtml({
      seams: [seams[0]],
      totalDurationMs: 7040,
      transition: { primary: "crossfade", duration: 0.4, easing: "power2.inOut" },
    });
    expect(html).not.toMatch(/window\.__timelines\["transitions"\]/);
    expect(html).toMatch(/<template/);
  });

  it("clamps the second tl.to so it never extends past the timeline duration", () => {
    // Degenerate: two seams ending exactly at totalDurationMs. The boundary
    // sits at 9_800 ms, so half-window crosses into the last `duration/2`.
    // Without the clamp, the second tl.to start would be at 9.800 + 0.200
    // = 10.000s, leaving zero room for the duration-0.2s tween before
    // timeline end. With the clamp it must be <= totalSec - duration = 9.6.
    const degenerate: Seam[] = [
      { index: 0, at_ms: 0,     ends_at_ms: 9800,  scene: "head" },
      { index: 1, at_ms: 9800,  ends_at_ms: 10000, scene: "head" },
    ];
    const html = buildTransitionsHtml({
      seams: degenerate,
      totalDurationMs: 10000,
      transition: { primary: "crossfade", duration: 0.4, easing: "power2.inOut" },
    });
    const m = html.match(/tl\.to\(maskEl,\s*\{ autoAlpha: 0[\s\S]*?\},\s*([0-9.]+)\)/);
    expect(m, "second tl.to call must be present").toBeTruthy();
    const start = Number(m![1]);
    expect(start).toBeLessThanOrEqual(9.6 + 1e-3);
  });
});
