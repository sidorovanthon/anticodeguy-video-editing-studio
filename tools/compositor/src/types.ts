export type SceneMode = "head" | "split" | "broll" | "overlay";

/**
 * Raw transcript word as it may appear on disk. Stage 1 currently writes the
 * ElevenLabs-native `start`/`end` (seconds); the canonical caption component
 * contract is `start_ms`/`end_ms` (ms). The compositor normalizes — both
 * field-name pairs are accepted on input. Other fields (speaker_id, type, …)
 * are preserved (loose typing) so we don't lose data on round-trips.
 */
export interface TranscriptWord {
  text: string;
  start_ms?: number;
  end_ms?: number;
  start?: number;
  end?: number;
  [key: string]: unknown;
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
