import type { SceneMode } from "./types.js";

export const SCENE_MODES = ["head", "split", "broll", "overlay"] as const;

export function parseSceneMode(value: string): SceneMode {
  // Transitional shim: the legacy `full` scene-mode name is rejected here so a
  // stale seam-plan.md fails fast instead of silently misbehaving. Remove once
  // the FROZEN pilot is unfrozen and re-cut on 6a-aftermath (no other producer
  // emits `full`).
  if (value === "full") {
    throw new Error(
      "Scene mode 'full' was renamed to 'broll'. Update the source emitting this value.",
    );
  }
  if ((SCENE_MODES as readonly string[]).includes(value)) {
    return value as SceneMode;
  }
  throw new Error(
    `Unknown scene mode: ${JSON.stringify(value)}. Expected one of: ${SCENE_MODES.join(", ")}.`,
  );
}
