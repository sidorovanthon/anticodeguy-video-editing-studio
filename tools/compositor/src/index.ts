#!/usr/bin/env node
import { writeFileSync, readFileSync } from "node:fs";
import path from "node:path";
import { loadTranscript } from "./transcript.js";
import { planSeams } from "./seamPlanner.js";
import { writeSeamPlan, readSeamPlan } from "./seamPlanWriter.js";
import { writeCompositionHtml } from "./composer.js";
import { loadEdl } from "./edl.js";

const [, , cmd, ...rest] = process.argv;

function usage(): never {
  console.error("Usage: compositor <seam-plan|compose|render> --episode <path> [...]");
  process.exit(1);
}

function arg(flag: string): string | undefined {
  const i = rest.indexOf(flag);
  return i >= 0 ? rest[i + 1] : undefined;
}

const episodeDir = arg("--episode");
if (!episodeDir) usage();

const repoRoot = process.env.REPO_ROOT ?? path.resolve(episodeDir, "../..");
const transcriptPath  = path.join(episodeDir, "stage-1-cut/transcript.json");
const cutListPath     = path.join(episodeDir, "stage-1-cut/cut-list.md");
const edlPath         = path.join(episodeDir, "stage-1-cut/edl.json");
const seamPlanPath    = path.join(episodeDir, "stage-2-composite/seam-plan.md");
const compositionPath = path.join(episodeDir, "stage-2-composite/composition.html");
const masterPath      = path.join(episodeDir, "stage-1-cut/master.mp4");

function deriveSeamTimestamps(cutListMd: string): number[] {
  const out: number[] = [0];
  for (const m of cutListMd.matchAll(/at_ms=(\d+)/g)) out.push(Number(m[1]));
  return [...new Set(out)].sort((a, b) => a - b);
}

if (cmd === "seam-plan") {
  const transcript = loadTranscript(transcriptPath);
  const cutList = readFileSync(cutListPath, "utf8");
  const seamTimestamps = deriveSeamTimestamps(cutList);
  const slug = path.basename(path.resolve(episodeDir));
  const seams = planSeams(seamTimestamps, transcript.duration_ms);
  const plan = {
    episode_slug: slug,
    master_duration_ms: transcript.duration_ms,
    seams,
  };
  writeFileSync(seamPlanPath, writeSeamPlan(plan));
  console.log(`Wrote ${seamPlanPath}`);
} else if (cmd === "compose") {
  const transcript = loadTranscript(transcriptPath);
  const plan = readSeamPlan(readFileSync(seamPlanPath, "utf8"));
  const edl = loadEdl(edlPath);
  writeCompositionHtml(
    {
      repoRoot, episodeDir, plan, transcript, edl,
      masterRelPath: path.relative(path.dirname(compositionPath), masterPath).replaceAll("\\", "/"),
    },
    compositionPath
  );
  console.log(`Wrote ${compositionPath}`);
} else if (cmd === "render") {
  console.error("Use tools/scripts/render-final.sh <slug> for final render.");
  process.exit(2);
} else {
  usage();
}
