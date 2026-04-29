// tools/compositor/src/bin/aggregate-generate-wallclocks.ts
//
// Reads every episode's generate.manifest.json under episodes/, prints
// p50/p95/p99 of wallclockMs across all recorded scenes. Used to calibrate
// realDispatcher.timeoutMs.

import { readdirSync, existsSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import type { GenerateManifest } from "../state/types.js";

const repoRoot = process.argv[2] ?? process.cwd();
const episodesDir = path.join(repoRoot, "episodes");

function* allManifests(): Generator<GenerateManifest> {
  if (!existsSync(episodesDir)) return;
  for (const name of readdirSync(episodesDir)) {
    const m = path.join(episodesDir, name, "stage-2-composite", "generate.manifest.json");
    if (existsSync(m) && statSync(m).isFile()) {
      yield JSON.parse(readFileSync(m, "utf-8")) as GenerateManifest;
    }
  }
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  const idx = Math.min(sorted.length - 1, Math.floor(sorted.length * p));
  return sorted[idx];
}

const samples: number[] = [];
for (const m of allManifests()) {
  for (const id of Object.keys(m.scenes)) {
    samples.push(m.scenes[id].wallclockMs);
  }
}
samples.sort((a, b) => a - b);

console.log(`samples: ${samples.length}`);
if (samples.length === 0) {
  console.log("no data — run generate on at least one episode first");
  process.exit(0);
}
console.log(`p50: ${percentile(samples, 0.5)} ms`);
console.log(`p95: ${percentile(samples, 0.95)} ms`);
console.log(`p99: ${percentile(samples, 0.99)} ms`);
console.log(`max: ${samples[samples.length - 1]} ms`);
console.log(`recommended timeoutMs (p99 * 1.5, clamped 180000..720000): ${
  Math.max(180000, Math.min(720000, Math.round(percentile(samples, 0.99) * 1.5)))
}`);
