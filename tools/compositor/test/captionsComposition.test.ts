import { describe, it, expect } from "vitest";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildCaptionsCompositionHtml } from "../src/captionsComposition.js";
import { loadDesignMd } from "../src/designMd.js";
import type { MasterBundle } from "../src/types.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const designMdPath = path.join(__dirname, "fixtures", "design-minimal.md");

const bundle: MasterBundle = {
  schemaVersion: 1,
  slug: "fixture",
  master: { durationMs: 5000, width: 1440, height: 2560, fps: 60 },
  boundaries: [],
  transcript: {
    language: "en",
    words: [
      { text: "one",   startMs: 0,    endMs: 200 },
      { text: "two",   startMs: 220,  endMs: 400 },
      { text: "three", startMs: 600,  endMs: 800 },
      { text: "four",  startMs: 820,  endMs: 1000 },
    ],
  },
};

describe("buildCaptionsCompositionHtml (grouped rewrite)", () => {
  const tree = loadDesignMd(designMdPath);
  const html = buildCaptionsCompositionHtml({ bundle, tree });

  it("emits one .caption-group div per group", () => {
    const groupMatches = html.match(/class="caption-group"/g) ?? [];
    expect(groupMatches.length).toBe(2);
  });

  it("uses literal hex/rgba in element styles, no var(--…)", () => {
    const noScript = html.replace(/<script[\s\S]*?<\/script>/g, "");
    expect(noScript).not.toMatch(/var\(--/);
  });

  it("registers autoAlpha:0 hard-kill at group.endMs in the runtime script", () => {
    expect(html).toMatch(/tl\.set\([^,]+,\s*\{\s*autoAlpha:\s*0\s*\}\s*,\s*[\d.]+\s*\)/);
  });

  it("calls window.__hyperframes.fitTextFontSize per group", () => {
    expect(html).toMatch(/window\.__hyperframes\.fitTextFontSize/);
  });

  it("appends a self-lint sweep that throws on missing entry/exit", () => {
    expect(html).toMatch(/getChildren\(\)/);
    expect(html).toMatch(/throw/);
  });

  it("registers window.__timelines.captions", () => {
    expect(html).toMatch(/window\.__timelines\["captions"\]\s*=\s*tl/);
  });

  it("emits an empty template + no timeline registration when there are no words", () => {
    const emptyBundle: MasterBundle = { ...bundle, transcript: { language: "en", words: [] } };
    const out = buildCaptionsCompositionHtml({ bundle: emptyBundle, tree });
    expect(out).not.toMatch(/window\.__timelines\["captions"\]/);
    expect(out).toMatch(/<template/);
  });
});
