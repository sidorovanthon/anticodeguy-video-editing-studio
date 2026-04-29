#!/usr/bin/env node
import { readFileSync, existsSync, readdirSync } from "node:fs";
import path from "node:path";
import { planSeams } from "./seamPlanner.js";
import { writeSeamPlan as writeLegacySeamPlan, readSeamPlan } from "./seamPlanWriter.js";
import { writeCompositionFiles } from "./composer.js";
import { loadBundle } from "./stage2/loadBundle.js";
import { writeFileSync } from "node:fs";
import { writeEpisodeMeta } from "./episodeMeta.js";
import {
  parseSeamPlan as parseEnrichedSeamPlan,
  writeSeamPlan as writeEnrichedSeamPlan,
} from "./planner/seamPlanFormat.js";
import { segment } from "./planner/segmenter.js";
import { decorate } from "./planner/decorator.js";
import { computePhraseBoundaries, snapScenes } from "./planner/snap.js";
import { generateAll } from "./planner/generativeDispatcher.js";
import { makeRealSubagentDispatcher } from "./planner/realDispatcher.js";
import type { Scene } from "./planner/types.js";

const [, , cmd, ...rest] = process.argv;

function usage(): never {
  console.error(
    "Usage: compositor <write-bundle|seam-plan|plan|generate|compose|render> --episode <path>",
  );
  process.exit(1);
}

function arg(flag: string): string | undefined {
  const i = rest.indexOf(flag);
  return i >= 0 ? rest[i + 1] : undefined;
}

const episodeDir = arg("--episode");
if (!episodeDir) usage();

const repoRoot = process.env.REPO_ROOT ?? path.resolve(episodeDir, "../..");
const REPO_ROOT = repoRoot;
const seamPlanPath = path.join(episodeDir, "stage-2-composite/seam-plan.md");
const masterPath = path.join(episodeDir, "stage-2-composite/assets/master.mp4");
const designMdPath = path.join(repoRoot, "DESIGN.md");

function countSeamsPerScene(scenes: Scene[], edl: any): Map<number, number> {
  const seamTimes: number[] = (edl.seams ?? []).map((x: any) => x.atMs);
  const out = new Map<number, number>();
  scenes.forEach((s, i) => {
    out.set(i, seamTimes.filter((t) => t > s.startMs && t < s.endMs).length);
  });
  return out;
}

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
  writeFileSync(seamPlanPath, writeLegacySeamPlan(plan));
  console.log(`Wrote ${seamPlanPath}`);
} else if (cmd === "plan") {
  const slug = path.basename(path.resolve(episodeDir));
  const bundle = JSON.parse(
    readFileSync(path.join(episodeDir, "master/bundle.json"), "utf-8"),
  );
  const script = readFileSync(path.join(episodeDir, "source/script.txt"), "utf-8");
  const designMd = readFileSync(path.join(REPO_ROOT, "DESIGN.md"), "utf-8");
  const catalogTable = readFileSync(
    path.join(REPO_ROOT, "standards/motion-graphics.md"),
    "utf-8",
  );
  const dispatcher = makeRealSubagentDispatcher({ repoRoot: REPO_ROOT });
  const scenes = await segment({
    script,
    words: bundle.transcript.words,
    masterDurationMs: bundle.master.durationMs,
    dispatcher,
  });
  const phraseBoundaries = computePhraseBoundaries(bundle.transcript.words, 150);
  const snapped = snapScenes(scenes, phraseBoundaries, 300);
  const edl = JSON.parse(
    readFileSync(path.join(episodeDir, "stage-1-cut/edl.json"), "utf-8"),
  );
  const seamsInsideByScene = countSeamsPerScene(snapped, edl);
  const enriched = await decorate({
    scenes: snapped,
    seamsInsideByScene,
    designMd,
    catalogTable,
    projectPrimaryTransition: "crossfade",
    dispatcher,
  });
  const planMd = writeEnrichedSeamPlan({
    slug,
    masterDurationMs: bundle.master.durationMs,
    scenes: enriched,
  });
  writeFileSync(seamPlanPath, planMd, "utf-8");
  console.log(`plan written: ${seamPlanPath}`);
} else if (cmd === "generate") {
  const planText = readFileSync(seamPlanPath, "utf-8");
  const plan = parseEnrichedSeamPlan(planText);
  const hfBin = path.join(
    REPO_ROOT,
    "tools/compositor/node_modules/.bin/hyperframes",
  );
  const results = await generateAll({
    episodeDir,
    scenes: plan.scenes,
    hfBin,
    dispatcherFor: () => makeRealSubagentDispatcher({ repoRoot: REPO_ROOT }),
  });
  const failed = results.filter((r) => !r.ok);
  if (failed.length > 0) {
    console.error("generative dispatch had failures:", failed);
    process.exit(1);
  }
  console.log(`generate: ${results.length} sub-compositions written`);
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

  const assetsDir = path.join(episodeDir, "stage-2-composite/assets");
  let musicRelPath: string | undefined;
  if (existsSync(assetsDir)) {
    const entries = readdirSync(assetsDir);
    const musicFile = entries.find((f) => /^music\.(mp3|wav|ogg|m4a)$/i.test(f));
    if (musicFile) {
      musicRelPath = `assets/${musicFile}`;
    }
  }

  const { indexPath, captionsPath, transitionsPath } = writeCompositionFiles({
    designMdPath,
    plan,
    bundle,
    masterRelPath: "assets/master.mp4",
    musicRelPath,
    existingSeamFiles,
    episodeDir,
  });
  console.log(`Wrote ${indexPath}`);
  console.log(`Wrote ${captionsPath}`);
  console.log(`Wrote ${transitionsPath}`);
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
