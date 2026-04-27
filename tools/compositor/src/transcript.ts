import { readFileSync } from "node:fs";
import type { Transcript } from "./types.js";

export function loadTranscript(filePath: string): Transcript {
  const raw = readFileSync(filePath, "utf8");
  const data = JSON.parse(raw) as Transcript;
  if (!Array.isArray(data.words) || data.words.length === 0) {
    throw new Error(`Transcript has no words: ${filePath}`);
  }
  if (typeof data.duration_ms !== "number" || data.duration_ms <= 0) {
    throw new Error(`Transcript missing duration_ms: ${filePath}`);
  }
  return data;
}
