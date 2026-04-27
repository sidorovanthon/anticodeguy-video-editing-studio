import type { SceneMode } from "./types.js";

export const SCENE_MODES = ["head", "split", "broll", "overlay"] as const;

export function parseSceneMode(value: string): SceneMode {
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
