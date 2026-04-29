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
