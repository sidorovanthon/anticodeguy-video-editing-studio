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
});
