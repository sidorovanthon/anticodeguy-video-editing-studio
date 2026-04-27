import { describe, it, expect } from "vitest";
import { parseSceneMode, SCENE_MODES } from "../src/sceneMode.js";

describe("parseSceneMode", () => {
  it("accepts each canonical name", () => {
    expect(parseSceneMode("head")).toBe("head");
    expect(parseSceneMode("split")).toBe("split");
    expect(parseSceneMode("broll")).toBe("broll");
    expect(parseSceneMode("overlay")).toBe("overlay");
  });

  it("rejects the legacy 'full' name explicitly", () => {
    expect(() => parseSceneMode("full")).toThrow(
      /'full' was renamed to 'broll'/,
    );
  });

  it("rejects unknown values with the offending value in the message", () => {
    expect(() => parseSceneMode("unknown")).toThrow(/unknown/);
    expect(() => parseSceneMode("")).toThrow();
  });

  it("exposes SCENE_MODES as a readonly tuple of all four names", () => {
    expect(SCENE_MODES).toEqual(["head", "split", "broll", "overlay"]);
  });
});
