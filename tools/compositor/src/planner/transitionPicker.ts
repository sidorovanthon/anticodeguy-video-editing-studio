// tools/compositor/src/planner/transitionPicker.ts
import type { EnergyHint, NarrativePosition } from "./types.js";

export interface TransitionPickerState {
  totalScenes: number;
  accentsUsed: number;
}

interface Input {
  energyHint: EnergyHint;
  narrativePosition: NarrativePosition;
}

const ACCENT_BUDGET_RATIO = 0.3;

export function pickTransition(input: Input, projectPrimary: string, state: TransitionPickerState): string {
  if (input.narrativePosition === "outro") return projectPrimary;
  const wantsAccent =
    (input.narrativePosition === "topic_change" && input.energyHint === "high") ||
    (input.narrativePosition === "climax" && input.energyHint === "high");
  if (!wantsAccent) return projectPrimary;
  const budget = Math.floor(state.totalScenes * ACCENT_BUDGET_RATIO);
  if (state.accentsUsed >= budget) return projectPrimary;
  state.accentsUsed += 1;
  return accentTransitionFor(input.energyHint);
}

function accentTransitionFor(energy: EnergyHint): string {
  if (energy === "high") return "push-slide";
  if (energy === "medium") return "staggered-blocks";
  return "blur-crossfade";
}
