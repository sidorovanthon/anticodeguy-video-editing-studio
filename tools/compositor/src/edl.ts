import { readFileSync } from "node:fs";

export interface EdlRange {
  source: string;
  start: number; // raw-clip seconds
  end: number; // raw-clip seconds
  beat?: string;
  reason?: string;
}

export interface Edl {
  version: number;
  sources: Record<string, string>;
  ranges: EdlRange[];
}

export interface RemappedWord {
  text: string;
  start_ms: number;
  end_ms: number;
}

export function loadEdl(filePath: string): Edl {
  const raw = readFileSync(filePath, "utf8");
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    throw new Error(`Failed to parse EDL JSON at ${filePath}: ${(e as Error).message}`);
  }
  if (!parsed || typeof parsed !== "object") {
    throw new Error(`EDL at ${filePath} is not an object`);
  }
  const obj = parsed as Record<string, unknown>;
  if (typeof obj.version !== "number") {
    throw new Error(`EDL at ${filePath}: 'version' must be a number`);
  }
  if (!Array.isArray(obj.ranges)) {
    throw new Error(`EDL at ${filePath}: 'ranges' must be an array`);
  }
  if (obj.ranges.length === 0) {
    throw new Error(`EDL at ${filePath}: 'ranges' must be a non-empty array`);
  }
  const ranges: EdlRange[] = obj.ranges.map((r, i) => {
    if (!r || typeof r !== "object") {
      throw new Error(`EDL at ${filePath}: ranges[${i}] is not an object`);
    }
    const rr = r as Record<string, unknown>;
    if (typeof rr.source !== "string") {
      throw new Error(`EDL at ${filePath}: ranges[${i}].source must be a string`);
    }
    if (typeof rr.start !== "number" || typeof rr.end !== "number") {
      throw new Error(`EDL at ${filePath}: ranges[${i}].start/end must be numbers`);
    }
    if (rr.end <= rr.start) {
      throw new Error(
        `EDL at ${filePath}: ranges[${i}] end (${rr.end}) must be > start (${rr.start})`,
      );
    }
    return {
      source: rr.source,
      start: rr.start,
      end: rr.end,
      beat: typeof rr.beat === "string" ? rr.beat : undefined,
      reason: typeof rr.reason === "string" ? rr.reason : undefined,
    };
  });
  const sources =
    obj.sources && typeof obj.sources === "object"
      ? (obj.sources as Record<string, string>)
      : {};
  return { version: obj.version, sources, ranges };
}

interface RawWordTiming {
  text: string;
  start?: number;
  end?: number;
  start_ms?: number;
  end_ms?: number;
}

function rawSecondsFor(w: RawWordTiming): { start: number; end: number } {
  let start: number | undefined;
  let end: number | undefined;
  if (typeof w.start === "number" && Number.isFinite(w.start)) start = w.start;
  else if (typeof w.start_ms === "number" && Number.isFinite(w.start_ms))
    start = w.start_ms / 1000;
  if (typeof w.end === "number" && Number.isFinite(w.end)) end = w.end;
  else if (typeof w.end_ms === "number" && Number.isFinite(w.end_ms))
    end = w.end_ms / 1000;
  if (start === undefined || end === undefined) {
    throw new Error(`Word missing timing: ${JSON.stringify(w)}`);
  }
  return { start, end };
}

export function remapWordsToMaster(
  words: ReadonlyArray<RawWordTiming>,
  edl: Edl,
): RemappedWord[] {
  // Precompute master offsets per range
  const offsets: number[] = [];
  let acc = 0;
  for (const r of edl.ranges) {
    offsets.push(acc);
    acc += r.end - r.start;
  }

  const out: RemappedWord[] = [];
  for (const w of words) {
    const { start: rawStart, end: rawEnd } = rawSecondsFor(w);
    const idx = edl.ranges.findIndex(
      (r) => rawStart >= r.start && rawStart < r.end,
    );
    if (idx === -1) {
      // Word starts in a dropped segment — exclude from master timeline
      continue;
    }
    const range = edl.ranges[idx];
    const masterOffset = offsets[idx];
    const clampedRawEnd = rawEnd > range.end ? range.end : rawEnd;
    const masterStartSec = rawStart - range.start + masterOffset;
    const masterEndSec = clampedRawEnd - range.start + masterOffset;
    out.push({
      text: String(w.text ?? ""),
      start_ms: Math.round(masterStartSec * 1000),
      end_ms: Math.round(masterEndSec * 1000),
    });
  }
  return out;
}
