import { describe, it, expect } from "vitest";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseDesignMd, designMdToCss } from "../src/designMd.js";
import { readFileSync } from "node:fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.join(__dirname, "fixtures", "design-minimal.md");

describe("parseDesignMd", () => {
  it("extracts the hyperframes-tokens fenced JSON block", () => {
    const md = readFileSync(FIXTURE, "utf8");
    const tree = parseDesignMd(md);
    expect(tree).toEqual({
      color: { text: { primary: "#FFFFFF" } },
      spacing: { md: "24px" },
    });
  });

  it("throws when no hyperframes-tokens block is present", () => {
    expect(() => parseDesignMd("# no block here")).toThrow(/hyperframes-tokens/);
  });

  it("throws when JSON is malformed", () => {
    const bad = "```json hyperframes-tokens\n{ not json\n```";
    expect(() => parseDesignMd(bad)).toThrow(/JSON/);
  });
});

describe("designMdToCss", () => {
  it("flattens nested keys into kebab-cased CSS variables", () => {
    const css = designMdToCss({ color: { text: { primary: "#FFFFFF" } }, spacing: { md: "24px" } });
    expect(css).toContain("--color-text-primary: #FFFFFF;");
    expect(css).toContain("--spacing-md: 24px;");
    expect(css.startsWith(":root {")).toBe(true);
    expect(css.trimEnd().endsWith("}")).toBe(true);
  });
});
