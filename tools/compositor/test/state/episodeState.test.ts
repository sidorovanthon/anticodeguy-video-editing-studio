import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdtempSync, rmSync, existsSync, readFileSync, writeFileSync } from "node:fs";
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
