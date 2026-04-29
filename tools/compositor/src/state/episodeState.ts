import { existsSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { writeJsonAtomic } from "./atomicWrite.js";
import {
  EpisodeState,
  STATE_SCHEMA_VERSION,
  GenerateManifest,
  GenerateSceneEntry,
  GENERATE_MANIFEST_SCHEMA_VERSION,
} from "./types.js";
import type { StepName, CheckpointId } from "./types.js";

export function statePath(episodeDir: string): string {
  return path.join(episodeDir, "state.json");
}

export function initState(episodeDir: string, episodeSlug: string): EpisodeState {
  const file = statePath(episodeDir);
  if (existsSync(file)) {
    throw new Error(`state.json already exists at ${file}`);
  }
  const now = new Date().toISOString();
  const state: EpisodeState = {
    schemaVersion: STATE_SCHEMA_VERSION,
    episode: episodeSlug,
    stage: "stage-2",
    lastCheckpoint: null,
    completedSteps: [],
    inProgressStep: null,
    stepStartedAt: null,
    fixesApplied: [],
    lastUpdate: now,
  };
  writeJsonAtomic(file, state);
  return state;
}

export function readState(episodeDir: string): EpisodeState {
  const file = statePath(episodeDir);
  if (!existsSync(file)) {
    throw new Error(`state.json not found at ${file}`);
  }
  const parsed = JSON.parse(readFileSync(file, "utf-8"));
  if (parsed.schemaVersion !== STATE_SCHEMA_VERSION) {
    throw new Error(
      `state.json schemaVersion ${parsed.schemaVersion} not supported (expected ${STATE_SCHEMA_VERSION})`
    );
  }
  return parsed as EpisodeState;
}

function mutate(episodeDir: string, fn: (s: EpisodeState) => EpisodeState): EpisodeState {
  const current = readState(episodeDir);
  const next = fn(current);
  next.lastUpdate = new Date().toISOString();
  writeJsonAtomic(statePath(episodeDir), next);
  return next;
}

export function markStepStarted(episodeDir: string, step: StepName): EpisodeState {
  return mutate(episodeDir, (s) => ({
    ...s,
    inProgressStep: step,
    stepStartedAt: new Date().toISOString(),
  }));
}

export function markStepDone(
  episodeDir: string,
  step: StepName,
  checkpoint: CheckpointId,
): EpisodeState {
  return mutate(episodeDir, (s) => ({
    ...s,
    inProgressStep: null,
    stepStartedAt: null,
    completedSteps: s.completedSteps.includes(step)
      ? s.completedSteps
      : [...s.completedSteps, step],
    lastCheckpoint: checkpoint,
  }));
}

export function recordFix(episodeDir: string, label: string): EpisodeState {
  return mutate(episodeDir, (s) => ({
    ...s,
    fixesApplied: s.fixesApplied.includes(label)
      ? s.fixesApplied
      : [...s.fixesApplied, label],
  }));
}

const MIN_SCENE_BYTES = 256;

export function generateManifestPath(episodeDir: string): string {
  return path.join(episodeDir, "stage-2-composite", "generate.manifest.json");
}

export function readGenerateManifest(episodeDir: string): GenerateManifest {
  const file = generateManifestPath(episodeDir);
  if (!existsSync(file)) {
    return { schemaVersion: GENERATE_MANIFEST_SCHEMA_VERSION, scenes: {} };
  }
  const parsed = JSON.parse(readFileSync(file, "utf-8"));
  if (parsed.schemaVersion !== GENERATE_MANIFEST_SCHEMA_VERSION) {
    throw new Error(
      `generate.manifest.json schemaVersion ${parsed.schemaVersion} not supported`
    );
  }
  return parsed as GenerateManifest;
}

export function recordSceneCompleted(
  episodeDir: string,
  sceneId: string,
  entry: Omit<GenerateSceneEntry, "completedAt">,
): GenerateManifest {
  const m = readGenerateManifest(episodeDir);
  m.scenes[sceneId] = { ...entry, completedAt: new Date().toISOString() };
  writeJsonAtomic(generateManifestPath(episodeDir), m);
  return m;
}

/**
 * True iff the manifest has a recorded scene with matching prompt hash AND
 * the recorded output file still exists with size >= MIN_SCENE_BYTES.
 * Used by the dispatcher to skip already-generated scenes on resume.
 */
export function isSceneSatisfied(
  episodeDir: string,
  sceneId: string,
  expectedHash: string,
): boolean {
  const m = readGenerateManifest(episodeDir);
  const entry = m.scenes[sceneId];
  if (!entry) return false;
  if (entry.promptHash !== expectedHash) return false;
  const abs = path.join(episodeDir, "stage-2-composite", entry.outputPath);
  if (!existsSync(abs)) return false;
  try {
    const sz = statSync(abs).size;
    return sz >= MIN_SCENE_BYTES;
  } catch {
    return false;
  }
}
