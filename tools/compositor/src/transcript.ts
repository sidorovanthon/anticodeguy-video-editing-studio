import { readFileSync } from "node:fs";
import type { RawTranscript, Transcript } from "./types.js";

export function loadTranscript(filePath: string): Transcript {
  const raw = readFileSync(filePath, "utf8");
  const data = JSON.parse(raw) as RawTranscript;
  if (!Array.isArray(data.words) || data.words.length === 0) {
    throw new Error(`Transcript has no words: ${filePath}`);
  }

  let duration_ms: number;
  if (typeof data.duration_ms === "number" && data.duration_ms > 0) {
    duration_ms = data.duration_ms;
  } else if (
    typeof data.audio_duration_secs === "number" &&
    data.audio_duration_secs > 0
  ) {
    duration_ms = Math.round(data.audio_duration_secs * 1000);
  } else {
    throw new Error(
      `Transcript missing duration (expected positive 'duration_ms' or 'audio_duration_secs'): ${filePath}`,
    );
  }

  return { words: data.words, duration_ms };
}
