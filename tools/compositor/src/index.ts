#!/usr/bin/env node
import { writeFileSync, readFileSync } from "node:fs";
import path from "node:path";
import { planSeams } from "./seamPlanner.js";
import { writeSeamPlan, readSeamPlan } from "./seamPlanWriter.js";
import { writeCompositionHtml } from "./composer.js";
import { loadBundle } from "./stage2/loadBundle.js";

const [, , cmd, ...rest] = process.argv;

function usage(): never {
  console.error("Usage: compositor <write-bundle|seam-plan|compose|render> --episode <path> [...]");
  process.exit(1);
}

function arg(flag: string): string | undefined {
  const i = rest.indexOf(flag);
  return i >= 0 ? rest[i + 1] : undefined;
}

const episodeDir = arg("--episode");
if (!episodeDir) usage();

const repoRoot = process.env.REPO_ROOT ?? path.resolve(episodeDir, "../..");
const seamPlanPath    = path.join(episodeDir, "stage-2-composite/seam-plan.md");
const compositionPath = path.join(episodeDir, "stage-2-composite/composition.html");
const masterPath      = path.join(episodeDir, "stage-1-cut/master.mp4");

if (cmd === "write-bundle") {
  const { buildBundle, writeBundleFile } = await import("./stage1/writeBundle.js");
  const fs = await import("node:fs");
  const slug = path.basename(path.resolve(episodeDir));
  const masterDir = path.join(episodeDir, "master");
  fs.mkdirSync(masterDir, { recursive: true });
  const bundle = buildBundle({
    slug,
    transcriptPath: path.join(episodeDir, "stage-1-cut/transcript.json"),
    edlPath: path.join(episodeDir, "stage-1-cut/edl.json"),
    masterPath: path.join(episodeDir, "stage-1-cut/master.mp4"),
  });
  const bundlePath = path.join(masterDir, "bundle.json");
  writeBundleFile(bundle, bundlePath);
  console.log(`Wrote ${bundlePath}`);
} else if (cmd === "seam-plan") {
  const bundle = loadBundle(episodeDir);
  const seamTimestamps = bundle.boundaries
    .filter((b) => b.kind !== "end")
    .map((b) => b.atMs);
  const seams = planSeams(seamTimestamps, bundle.master.durationMs);
  const plan = {
    episode_slug: bundle.slug,
    master_duration_ms: bundle.master.durationMs,
    seams,
  };
  writeFileSync(seamPlanPath, writeSeamPlan(plan));
  console.log(`Wrote ${seamPlanPath}`);
} else if (cmd === "compose") {
  const bundle = loadBundle(episodeDir);
  const plan = readSeamPlan(readFileSync(seamPlanPath, "utf8"));
  writeCompositionHtml(
    {
      repoRoot, episodeDir, plan, bundle,
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
