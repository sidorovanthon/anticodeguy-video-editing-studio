import { describe, it, expect } from "vitest";
import { mkdtempSync, readFileSync, existsSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { writeEpisodeMeta } from "../src/episodeMeta.js";

describe("writeEpisodeMeta", () => {
  it("writes hyperframes.json with the canonical paths config", () => {
    const dir = mkdtempSync(path.join(os.tmpdir(), "epmeta-"));
    writeEpisodeMeta({ episodeSlug: "demo-episode", outDir: dir, createdAt: "2026-04-28T00:00:00.000Z" });
    const hf = JSON.parse(readFileSync(path.join(dir, "hyperframes.json"), "utf8"));
    expect(hf).toEqual({
      $schema: "https://hyperframes.heygen.com/schema/hyperframes.json",
      registry: "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
      paths: {
        blocks: "compositions",
        components: "compositions/components",
        assets: "assets",
      },
    });
  });

  it("writes meta.json with id, name, createdAt", () => {
    const dir = mkdtempSync(path.join(os.tmpdir(), "epmeta-"));
    writeEpisodeMeta({ episodeSlug: "demo-episode", outDir: dir, createdAt: "2026-04-28T00:00:00.000Z" });
    const meta = JSON.parse(readFileSync(path.join(dir, "meta.json"), "utf8"));
    expect(meta).toEqual({ id: "demo-episode", name: "demo-episode", createdAt: "2026-04-28T00:00:00.000Z" });
  });

  it("creates the output dir if missing", () => {
    const dir = path.join(mkdtempSync(path.join(os.tmpdir(), "epmeta-")), "nested");
    writeEpisodeMeta({ episodeSlug: "x", outDir: dir, createdAt: "2026-04-28T00:00:00.000Z" });
    expect(existsSync(path.join(dir, "hyperframes.json"))).toBe(true);
  });
});
