import { describe, it, expect } from "vitest";
import { loadTokensCss } from "../src/tokens.js";
import path from "node:path";

describe("tokensToCss", () => {
  it("emits expected CSS variables from design-system tokens", () => {
    const css = loadTokensCss(
      path.resolve(__dirname, "../../../design-system/tokens/tokens.json"),
    );
    expect(css).toContain("--video-width: 1440");
    expect(css).toContain("--video-height: 2560");
    expect(css).toContain("--safezone-bottom: 22%");
    expect(css).toContain("--blur-glass-md: 24px");
  });
});
