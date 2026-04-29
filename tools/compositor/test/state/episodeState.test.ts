import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdtempSync, rmSync, existsSync, readFileSync, writeFileSync, mkdirSync, writeFileSync as fsWriteFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { initState, readState } from "../../src/state/episodeState.js";

describe("episodeState init + read", () => {
  let episodeDir: string;
  beforeEach(() => { episodeDir = mkdtempSync(path.join(tmpdir(), "ep-")); });
  afterEach(() => { rmSync(episodeDir, { recursive: true, force: true }); });

  it("initState creates state.json with empty completedSteps", () => {
    initState(episodeDir, "test-slug");
    const s = readState(episodeDir);
    expect(s.episode).toBe("test-slug");
    expect(s.completedSteps).toEqual([]);
    expect(s.inProgressStep).toBeNull();
    expect(s.lastCheckpoint).toBeNull();
    expect(s.schemaVersion).toBe(1);
  });

  it("initState does not overwrite existing state", () => {
    initState(episodeDir, "test-slug");
    expect(() => initState(episodeDir, "test-slug")).toThrow(/already exists/);
  });

  it("readState rejects unknown schema version", () => {
    const file = path.join(episodeDir, "state.json");
    writeFileSync(file, JSON.stringify({ schemaVersion: 999 }));
    expect(() => readState(episodeDir)).toThrow(/schemaVersion/);
  });

  it("readState throws clear error when missing", () => {
    expect(() => readState(episodeDir)).toThrow(/state\.json not found/);
  });
});

import { markStepStarted, markStepDone, recordFix } from "../../src/state/episodeState.js";

describe("step transitions", () => {
  let episodeDir: string;
  beforeEach(() => {
    episodeDir = mkdtempSync(path.join(tmpdir(), "ep-"));
    initState(episodeDir, "test-slug");
  });
  afterEach(() => { rmSync(episodeDir, { recursive: true, force: true }); });

  it("markStepStarted sets inProgressStep and stepStartedAt", () => {
    markStepStarted(episodeDir, "plan");
    const s = readState(episodeDir);
    expect(s.inProgressStep).toBe("plan");
    expect(s.stepStartedAt).not.toBeNull();
  });

  it("markStepDone clears inProgressStep, appends to completedSteps, sets checkpoint", () => {
    markStepStarted(episodeDir, "plan");
    markStepDone(episodeDir, "plan", "CP1");
    const s = readState(episodeDir);
    expect(s.inProgressStep).toBeNull();
    expect(s.stepStartedAt).toBeNull();
    expect(s.completedSteps).toEqual(["plan"]);
    expect(s.lastCheckpoint).toBe("CP1");
  });

  it("markStepDone is idempotent — re-calling does not duplicate completedSteps", () => {
    markStepStarted(episodeDir, "plan");
    markStepDone(episodeDir, "plan", "CP1");
    markStepDone(episodeDir, "plan", "CP1");
    const s = readState(episodeDir);
    expect(s.completedSteps).toEqual(["plan"]);
  });

  it("recordFix appends and dedupes", () => {
    recordFix(episodeDir, "D17");
    recordFix(episodeDir, "D21");
    recordFix(episodeDir, "D17");
    const s = readState(episodeDir);
    expect(s.fixesApplied).toEqual(["D17", "D21"]);
  });
});

import {
  readGenerateManifest,
  recordSceneCompleted,
  isSceneSatisfied,
} from "../../src/state/episodeState.js";

describe("generate manifest", () => {
  let episodeDir: string;
  let stageDir: string;
  beforeEach(() => {
    episodeDir = mkdtempSync(path.join(tmpdir(), "ep-"));
    stageDir = path.join(episodeDir, "stage-2-composite");
    mkdirSync(stageDir, { recursive: true });
    initState(episodeDir, "test-slug");
  });
  afterEach(() => { rmSync(episodeDir, { recursive: true, force: true }); });

  it("readGenerateManifest returns empty when missing", () => {
    const m = readGenerateManifest(episodeDir);
    expect(m.scenes).toEqual({});
  });

  it("recordSceneCompleted persists scene entry", () => {
    recordSceneCompleted(episodeDir, "B-1", {
      kind: "generative",
      outputPath: "compositions/scene-B-1.html",
      promptHash: "sha256:abc",
      outputBytes: 4096,
      wallclockMs: 250000,
    });
    const m = readGenerateManifest(episodeDir);
    expect(m.scenes["B-1"].promptHash).toBe("sha256:abc");
    expect(m.scenes["B-1"].wallclockMs).toBe(250000);
  });

  it("isSceneSatisfied true when hash matches and file exists at >= 256 B", () => {
    const outRel = "compositions/scene-B-1.html";
    const outAbs = path.join(stageDir, outRel);
    mkdirSync(path.dirname(outAbs), { recursive: true });
    fsWriteFileSync(outAbs, "x".repeat(4096));
    recordSceneCompleted(episodeDir, "B-1", {
      kind: "generative",
      outputPath: outRel,
      promptHash: "sha256:abc",
      outputBytes: 4096,
      wallclockMs: 100,
    });
    expect(isSceneSatisfied(episodeDir, "B-1", "sha256:abc")).toBe(true);
  });

  it("isSceneSatisfied false on hash mismatch", () => {
    recordSceneCompleted(episodeDir, "B-1", {
      kind: "generative",
      outputPath: "compositions/scene-B-1.html",
      promptHash: "sha256:abc",
      outputBytes: 4096,
      wallclockMs: 100,
    });
    expect(isSceneSatisfied(episodeDir, "B-1", "sha256:DIFFERENT")).toBe(false);
  });

  it("isSceneSatisfied false when output file missing", () => {
    recordSceneCompleted(episodeDir, "B-1", {
      kind: "generative",
      outputPath: "compositions/missing.html",
      promptHash: "sha256:abc",
      outputBytes: 4096,
      wallclockMs: 100,
    });
    expect(isSceneSatisfied(episodeDir, "B-1", "sha256:abc")).toBe(false);
  });
});
