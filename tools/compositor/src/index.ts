#!/usr/bin/env node
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { planSeams } from "./seamPlanner.js";
import { writeSeamPlan, readSeamPlan } from "./seamPlanWriter.js";
import { writeCompositionFiles } from "./composer.js";
import { loadBundle } from "./stage2/loadBundle.js";
import { writeFileSync } from "node:fs";
import { writeEpisodeMeta } from "./episodeMeta.js";

const [, , cmd, ...rest] = process.argv;

function usage(): never {
  console.error("Usage: compositor <write-bundle|seam-plan|compose|render> --episode <path>");
  process.exit(1);
}

function arg(flag: string): string | undefined {
  const i = rest.indexOf(flag);
  return i >= 0 ? rest[i + 1] : undefined;
}

const episodeDir = arg("--episode");
if (!episodeDir) usage();

const repoRoot = process.env.REPO_ROOT ?? path.resolve(episodeDir, "../..");
const seamPlanPath = path.join(episodeDir, "stage-2-composite/seam-plan.md");
const masterPath = path.join(episodeDir, "stage-1-cut/master.mp4");
const designMdPath = path.join(repoRoot, "DESIGN.md");

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
    masterPath,
  });
  const bundlePath = path.join(masterDir, "bundle.json");
  writeBundleFile(bundle, bundlePath);
  console.log(`Wrote ${bundlePath}`);
} else if (cmd === "seam-plan") {
  const bundle = loadBundle(episodeDir);
  const seamTimestamps = bundle.boundaries.filter((b) => b.kind !== "end").map((b) => b.atMs);
  const seams = planSeams(seamTimestamps, bundle.master.durationMs);
  const plan = { episode_slug: bundle.slug, master_duration_ms: bundle.master.durationMs, seams };
  writeFileSync(seamPlanPath, writeSeamPlan(plan));
  console.log(`Wrote ${seamPlanPath}`);
} else if (cmd === "compose") {
  if (!existsSync(designMdPath)) {
    console.error(`ERROR: DESIGN.md not found at ${designMdPath}`);
    process.exit(2);
  }
  const bundle = loadBundle(episodeDir);
  const plan = readSeamPlan(readFileSync(seamPlanPath, "utf8"));

  const compositionsDir = path.join(episodeDir, "stage-2-composite/compositions");
  const existingSeamFiles = new Set<number>();
  for (const seam of plan.seams) {
    const candidate = path.join(compositionsDir, `seam-${seam.index}.html`);
    if (existsSync(candidate)) existingSeamFiles.add(seam.index);
  }

  const { indexPath, captionsPath } = writeCompositionFiles({
    designMdPath,
    plan,
    bundle,
    masterRelPath: "../stage-1-cut/master.mp4",
    existingSeamFiles,
    episodeDir,
  });
  console.log(`Wrote ${indexPath}`);
  console.log(`Wrote ${captionsPath}`);
  const compositeDir = path.join(episodeDir, "stage-2-composite");
  const slug = path.basename(path.resolve(episodeDir));
  const meta = writeEpisodeMeta({ episodeSlug: slug, outDir: compositeDir });
  console.log(`Wrote ${meta.hyperframesJsonPath}`);
  console.log(`Wrote ${meta.metaJsonPath}`);
  if (existingSeamFiles.size > 0) {
    console.log(`Wired ${existingSeamFiles.size} per-seam sub-composition(s): ${[...existingSeamFiles].join(", ")}`);
  }
} else if (cmd === "render") {
  console.error("Use tools/scripts/render-final.sh <slug> for final render.");
  process.exit(2);
} else {
  usage();
}
