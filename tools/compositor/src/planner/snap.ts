import type { Scene } from "./types.js";

interface WordTiming { startMs: number; endMs: number; }

export function computePhraseBoundaries(words: WordTiming[], minGapMs: number): number[] {
  const out: number[] = [];
  for (let i = 0; i < words.length - 1; i++) {
    const gap = words[i + 1].startMs - words[i].endMs;
    if (gap > minGapMs) out.push(Math.round(words[i].endMs + gap / 2));
  }
  return out;
}

export function snapScenes(scenes: Scene[], phraseBoundaries: number[], toleranceMs: number): Scene[] {
  if (scenes.length === 0) return [];
  const sorted = [...phraseBoundaries].sort((a, b) => a - b);
  const out = scenes.map((s) => ({ ...s }));
  for (let i = 0; i < out.length - 1; i++) {
    const target = out[i].endMs;
    const nearest = nearestBoundary(target, sorted);
    if (nearest !== null && Math.abs(nearest - target) <= toleranceMs &&
        nearest > out[i].startMs && nearest < out[i + 1].endMs) {
      out[i].endMs = nearest;
      out[i + 1].startMs = nearest;
    }
  }
  return out;
}

function nearestBoundary(target: number, sorted: number[]): number | null {
  if (sorted.length === 0) return null;
  let best = sorted[0]; let bestDist = Math.abs(target - best);
  for (let i = 1; i < sorted.length; i++) {
    const d = Math.abs(target - sorted[i]);
    if (d < bestDist) { best = sorted[i]; bestDist = d; }
  }
  return best;
}
