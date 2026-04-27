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
