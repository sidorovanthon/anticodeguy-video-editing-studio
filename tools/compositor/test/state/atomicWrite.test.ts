import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdtempSync, rmSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { writeJsonAtomic } from "../../src/state/atomicWrite.js";

describe("writeJsonAtomic", () => {
  let dir: string;
  beforeEach(() => { dir = mkdtempSync(path.join(tmpdir(), "atom-")); });
  afterEach(() => { rmSync(dir, { recursive: true, force: true }); });

  it("writes JSON to the target path", () => {
    const target = path.join(dir, "out.json");
    writeJsonAtomic(target, { a: 1 });
    expect(JSON.parse(readFileSync(target, "utf-8"))).toEqual({ a: 1 });
  });

  it("overwrites existing file in-place", () => {
    const target = path.join(dir, "out.json");
    writeJsonAtomic(target, { a: 1 });
    writeJsonAtomic(target, { a: 2 });
    expect(JSON.parse(readFileSync(target, "utf-8"))).toEqual({ a: 2 });
  });

  it("does not leave a .tmp sibling on success", () => {
    const target = path.join(dir, "out.json");
    writeJsonAtomic(target, { a: 1 });
    expect(existsSync(target + ".tmp")).toBe(false);
  });
});
