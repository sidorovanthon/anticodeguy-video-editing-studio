import { describe, it, expect } from "vitest";
import { computePromptHash } from "../../src/state/promptHash.js";

describe("computePromptHash", () => {
  const base = { prompt: "hello", model: "claude-opus-4-7", allowedTools: ["Read", "Write"] };

  it("returns sha256: prefixed string", () => {
    const h = computePromptHash(base);
    expect(h).toMatch(/^sha256:[0-9a-f]{64}$/);
  });

  it("is stable across calls with identical input", () => {
    expect(computePromptHash(base)).toBe(computePromptHash(base));
  });

  it("is order-stable across allowedTools permutations", () => {
    const a = computePromptHash({ ...base, allowedTools: ["Read", "Write"] });
    const b = computePromptHash({ ...base, allowedTools: ["Write", "Read"] });
    expect(a).toBe(b);
  });

  it("changes when prompt changes", () => {
    expect(computePromptHash(base)).not.toBe(computePromptHash({ ...base, prompt: "hello!" }));
  });

  it("changes when model changes", () => {
    expect(computePromptHash(base)).not.toBe(computePromptHash({ ...base, model: "claude-sonnet-4-6" }));
  });
});
