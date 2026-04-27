export type SceneMode = "head" | "split" | "full" | "overlay";

export interface TranscriptWord {
  text: string;
  start_ms: number;
  end_ms: number;
}

export interface Transcript {
  words: TranscriptWord[];
  duration_ms: number;
}

/**
 * Raw transcript shape as it may appear on disk. Stage 1 currently writes the
 * ElevenLabs-native response which carries `audio_duration_secs` (seconds) and
 * no `duration_ms`. `loadTranscript` normalizes either form into the canonical
 * `Transcript` (with `duration_ms`). Until Stage 1 is updated to emit the
 * canonical schema directly, both fields are accepted on input.
 */
export interface RawTranscript {
  words?: TranscriptWord[];
  duration_ms?: number;
  audio_duration_secs?: number;
}

export interface CutSpan {
  start_ms: number;
  end_ms: number;
  reason: "silence" | "filler" | "stumble" | "manual" | "other";
}

export interface Seam {
  index: number;
  at_ms: number;
  scene: SceneMode;
  graphic?: {
    component: string;
    data: Record<string, unknown>;
  };
  ends_at_ms: number;
}

export interface SeamPlan {
  episode_slug: string;
  master_duration_ms: number;
  seams: Seam[];
}
