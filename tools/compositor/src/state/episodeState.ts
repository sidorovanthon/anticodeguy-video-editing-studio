import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { writeJsonAtomic } from "./atomicWrite.js";
import {
  EpisodeState,
  STATE_SCHEMA_VERSION,
} from "./types.js";

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
