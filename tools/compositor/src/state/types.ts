// tools/compositor/src/state/types.ts
//
// Schema-versioned types for episode state. Bump SCHEMA_VERSION on any
// breaking change; readers must reject unknown versions.

export const STATE_SCHEMA_VERSION = 1 as const;
export const GENERATE_MANIFEST_SCHEMA_VERSION = 1 as const;

export type StepName = "plan" | "generate" | "compose" | "preview";
export type CheckpointId = "CP1" | "CP2" | "CP3" | "CP4";

export interface EpisodeState {
  schemaVersion: typeof STATE_SCHEMA_VERSION;
  episode: string;
  stage: "stage-2";
  lastCheckpoint: CheckpointId | null;
  completedSteps: StepName[];
  inProgressStep: StepName | null;
  stepStartedAt: string | null; // ISO 8601
  fixesApplied: string[];
  lastUpdate: string; // ISO 8601
}

export interface GenerateSceneEntry {
  kind: "generative" | "catalog" | "none";
  outputPath: string;
  promptHash: string; // "sha256:..."
  outputBytes: number;
  wallclockMs: number;
  completedAt: string; // ISO 8601
}

export interface GenerateManifest {
  schemaVersion: typeof GENERATE_MANIFEST_SCHEMA_VERSION;
  scenes: Record<string, GenerateSceneEntry>;
}
