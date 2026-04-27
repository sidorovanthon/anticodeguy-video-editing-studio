import type { Seam, SceneMode } from "./types.js";

const ORDER: SceneMode[] = ["full", "split", "head", "split", "full", "overlay"];

const FORBIDDEN: ReadonlySet<string> = new Set([
  "head>head",
  "head>overlay",
  "overlay>head",
  "overlay>overlay",
  "split>split",
  "full>full",
]);

export function isAllowed(prev: SceneMode | null, next: SceneMode): boolean {
  if (prev === null) return true;
  return !FORBIDDEN.has(`${prev}>${next}`);
}

export function pickScene(index: number, prev: SceneMode | null): SceneMode {
  if (prev === null) return "full";
  for (let offset = 0; offset < ORDER.length; offset++) {
    const candidate = ORDER[(index + offset) % ORDER.length];
    if (isAllowed(prev, candidate)) return candidate;
  }
  return "full";
}

export function planSeams(at_ms_list: number[], master_duration_ms: number): Seam[] {
  const seams: Seam[] = [];
  let prev: SceneMode | null = null;
  for (let i = 0; i < at_ms_list.length; i++) {
    const scene = pickScene(i, prev);
    const ends_at_ms =
      i + 1 < at_ms_list.length ? at_ms_list[i + 1] : master_duration_ms;
    seams.push({
      index: i,
      at_ms: at_ms_list[i],
      scene,
      ends_at_ms,
    });
    prev = scene;
  }
  return seams;
}
