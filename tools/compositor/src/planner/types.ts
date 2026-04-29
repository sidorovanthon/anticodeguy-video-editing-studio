// tools/compositor/src/planner/types.ts
import type { SceneMode } from "../types.js";

export type NarrativePosition =
  | "opening" | "setup" | "main" | "topic_change"
  | "climax" | "wind_down" | "outro";

export type EnergyHint = "calm" | "medium" | "high";

export type MoodHint =
  | "warm" | "cold" | "editorial" | "tech" | "tense"
  | "playful" | "dramatic" | "premium" | "retro";

export interface Beat {
  beatId: string;
  beatSummary: string;
  narrativePosition: NarrativePosition;
  energyHint: EnergyHint;
  moodHint?: MoodHint;
  startMs: number;
  endMs: number;
}

export interface Scene {
  startMs: number;
  endMs: number;
  beatId: string;
  narrativePosition: NarrativePosition;
  energyHint: EnergyHint;
  moodHint?: MoodHint;
  keyPhrase: string;
  scriptChunk: string;
}

export type GraphicSource =
  | { kind: "none" }
  | { kind: "catalog"; name: string; data?: unknown }
  | { kind: "generative"; brief: string; data?: unknown };

export interface EnrichedScene extends Scene {
  mode: SceneMode;
  transitionOut: string;
  graphic: GraphicSource;
}

export interface SeamPlan {
  slug: string;
  masterDurationMs: number;
  scenes: EnrichedScene[];
}
