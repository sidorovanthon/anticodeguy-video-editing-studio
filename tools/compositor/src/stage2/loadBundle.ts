import { readFileSync } from "node:fs";
import path from "node:path";
import type {
  BundleBoundary,
  BundleMaster,
  BundleWord,
  MasterBundle,
} from "../types.js";

export class BundleSchemaError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "BundleSchemaError";
  }
}

function fail(field: string, detail: string): never {
  throw new BundleSchemaError(`bundle.${field}: ${detail}`);
}

function ensureNumber(field: string, value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    fail(field, `expected finite number, got ${JSON.stringify(value)}`);
  }
  return value;
}

function ensureString(field: string, value: unknown): string {
  if (typeof value !== "string") {
    fail(field, `expected string, got ${JSON.stringify(value)}`);
  }
  return value;
}

function parseMaster(field: string, raw: unknown): BundleMaster {
  if (!raw || typeof raw !== "object") fail(field, "expected object");
  const obj = raw as Record<string, unknown>;
  return {
    durationMs: ensureNumber(`${field}.durationMs`, obj.durationMs),
    width: ensureNumber(`${field}.width`, obj.width),
    height: ensureNumber(`${field}.height`, obj.height),
    fps: ensureNumber(`${field}.fps`, obj.fps),
  };
}

function parseBoundary(field: string, raw: unknown): BundleBoundary {
  if (!raw || typeof raw !== "object") fail(field, "expected object");
  const obj = raw as Record<string, unknown>;
  const atMs = ensureNumber(`${field}.atMs`, obj.atMs);
  const kind = ensureString(`${field}.kind`, obj.kind);
  if (kind !== "start" && kind !== "seam" && kind !== "end") {
    fail(`${field}.kind`, `expected one of start|seam|end, got ${JSON.stringify(kind)}`);
  }
  return { atMs, kind };
}

function parseWord(field: string, raw: unknown): BundleWord {
  if (!raw || typeof raw !== "object") fail(field, "expected object");
  const obj = raw as Record<string, unknown>;
  return {
    text: ensureString(`${field}.text`, obj.text),
    startMs: ensureNumber(`${field}.startMs`, obj.startMs),
    endMs: ensureNumber(`${field}.endMs`, obj.endMs),
  };
}

export function loadBundle(episodeDir: string): MasterBundle {
  const bundlePath = path.join(episodeDir, "master", "bundle.json");
  let raw: string;
  try {
    raw = readFileSync(bundlePath, "utf8");
  } catch (e) {
    throw new BundleSchemaError(
      `bundle file missing at ${bundlePath}: ${(e as Error).message}`,
    );
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    throw new BundleSchemaError(
      `bundle JSON parse failed at ${bundlePath}: ${(e as Error).message}`,
    );
  }
  if (!parsed || typeof parsed !== "object") {
    throw new BundleSchemaError(`bundle: expected object, got ${typeof parsed}`);
  }
  const obj = parsed as Record<string, unknown>;
  if (obj.schemaVersion !== 1) {
    fail("schemaVersion", `expected 1, got ${JSON.stringify(obj.schemaVersion)}`);
  }
  const slug = ensureString("slug", obj.slug);
  const master = parseMaster("master", obj.master);

  if (!Array.isArray(obj.boundaries)) {
    fail("boundaries", "expected array");
  }
  const boundaries = (obj.boundaries as unknown[]).map((b, i) =>
    parseBoundary(`boundaries[${i}]`, b),
  );
  if (boundaries.length < 2) {
    fail("boundaries", `expected at least 2 (start + end), got ${boundaries.length}`);
  }
  if (boundaries[0].kind !== "start" || boundaries[0].atMs !== 0) {
    fail("boundaries[0]", "first boundary must be { atMs: 0, kind: 'start' }");
  }
  const last = boundaries[boundaries.length - 1];
  if (last.kind !== "end" || last.atMs !== master.durationMs) {
    fail(
      `boundaries[${boundaries.length - 1}]`,
      `last boundary must be 'end' at master.durationMs (${master.durationMs}), got kind=${last.kind} atMs=${last.atMs}`,
    );
  }

  const transcriptRaw = obj.transcript;
  if (!transcriptRaw || typeof transcriptRaw !== "object") {
    fail("transcript", "expected object");
  }
  const tObj = transcriptRaw as Record<string, unknown>;
  const language = ensureString("transcript.language", tObj.language);
  if (!Array.isArray(tObj.words)) {
    fail("transcript.words", "expected array");
  }
  const words = (tObj.words as unknown[]).map((w, i) =>
    parseWord(`transcript.words[${i}]`, w),
  );

  return {
    schemaVersion: 1,
    slug,
    master,
    boundaries,
    transcript: { language, words },
  };
}
