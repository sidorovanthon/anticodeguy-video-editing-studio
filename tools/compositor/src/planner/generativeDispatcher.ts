// tools/compositor/src/planner/generativeDispatcher.ts
import { readFileSync, existsSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import type { EnrichedScene } from "./types.js";
import type { SubagentDispatcher } from "./segmenter.js";
import { computePromptHash } from "../state/promptHash.js";
import { isSceneSatisfied, recordSceneCompleted } from "../state/episodeState.js";

const PROMPTS_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "prompts");

const DEFAULT_MODEL = "claude-opus-4-7";
const DEFAULT_ALLOWED_TOOLS = ["Read", "Write", "Bash"];

export interface GenerativeDispatcherInputs {
  episodeDir: string;
  scenes: EnrichedScene[];
  hfBin: string;
  dispatcherFor(scene: EnrichedScene): SubagentDispatcher;
  maxRetries?: number;
  /** Identifies the model used for the subagent invocation; included in the
   * resume-cache prompt hash so model swaps invalidate the cache. */
  model?: string;
  /** Allowed tool list passed to the subagent; included in the prompt hash. */
  allowedTools?: string[];
}

export interface GenerationResult {
  sceneIndex: number;
  outputPath: string;
  ok: boolean;
  attempts: number;
  error?: string;
}

export async function generateAll(inputs: GenerativeDispatcherInputs): Promise<GenerationResult[]> {
  const projectRoot = path.join(inputs.episodeDir, "stage-2-composite");
  const compositionsDir = path.join(projectRoot, "compositions");

  // Phase 0: install missing catalog blocks via `hyperframes add <name>`.
  // De-dupe names; skip names whose target file already exists. Resumable.
  const catalogNames = Array.from(new Set(
    inputs.scenes
      .filter(s => s.graphic.kind === "catalog")
      .map(s => (s.graphic as any).name as string),
  ));
  for (const name of catalogNames) {
    const target = path.join(compositionsDir, `${name}.html`);
    if (existsSync(target)) continue;
    try {
      // `hyperframes add` runs against the project root; it writes the registry
      // block under compositions/. Run synchronously (cheap, network only).
      // shell:true so Windows can resolve the .cmd wrapper for the npm-bin
      // shell script (.bin/hyperframes); on POSIX shell:true is harmless here
      // since args are array-typed.
      execFileSync(inputs.hfBin, ["add", name], { cwd: projectRoot, stdio: "pipe", shell: true });
    } catch (err: any) {
      const stderrText = err?.stderr?.toString?.() ?? err?.message ?? String(err);
      throw new Error(`hyperframes add ${name} failed: ${stderrText}`);
    }
  }

  // Phase 1: write all generative scenes in parallel. Resumable — generateOne
  // skips scenes whose output file already exists and is non-trivial. No gates
  // yet — running gates on projectRoot while siblings are still writing races
  // on in-progress files and triggers spurious retries.
  const targets = inputs.scenes
    .map((s, i) => ({ s, i }))
    .filter(x => x.s.graphic.kind === "generative");
  const model = inputs.model ?? DEFAULT_MODEL;
  const allowedTools = inputs.allowedTools ?? DEFAULT_ALLOWED_TOOLS;
  const tasks = targets.map(({ s, i }) => generateOne(
    s, i, inputs.scenes, inputs.episodeDir,
    inputs.dispatcherFor(s), inputs.maxRetries ?? 2,
    model, allowedTools,
  ));
  const writeResults = await Promise.all(tasks);

  // Phase 2: single batch gate over the stable project state.
  try {
    execFileSync(inputs.hfBin, ["lint", projectRoot, "--strict-all"], { stdio: "pipe", shell: true });
    execFileSync(inputs.hfBin, ["validate", projectRoot, "--strict-all"], { stdio: "pipe", shell: true });
    execFileSync(inputs.hfBin, ["inspect", projectRoot, "--strict", "--json"], { stdio: "pipe", shell: true });
  } catch (gateErr: any) {
    const stderrText = gateErr?.stderr?.toString?.() ?? gateErr?.message ?? String(gateErr);
    // Mark every scene that was written successfully as gate-failed; callers
    // can decide whether to bail or retry the whole project.
    return writeResults.map(r => r.ok
      ? { ...r, ok: false, error: `HF batch gate failed: ${stderrText}` }
      : r);
  }
  return writeResults;
}

async function generateOne(
  scene: EnrichedScene, idx: number, all: EnrichedScene[],
  episodeDir: string,
  dispatcher: SubagentDispatcher, maxRetries: number,
  model: string, allowedTools: string[],
): Promise<GenerationResult> {
  if (!/^[A-Za-z0-9_-]+$/.test(scene.beatId)) {
    return { sceneIndex: idx, outputPath: "", ok: false, attempts: 0,
      error: `beatId "${scene.beatId}" contains characters other than [A-Za-z0-9_-]` };
  }
  const fileStem = `scene-${scene.beatId}-${idx}`;
  const projectRoot = path.join(episodeDir, "stage-2-composite");
  const outputPath = path.join(projectRoot, "compositions", `${fileStem}.html`);

  const tpl = readFileSync(path.join(PROMPTS_DIR, "generative.md"), "utf-8");
  const isFinal = idx === all.length - 1;
  const repoRoot = path.join(episodeDir, "..", "..");
  const neighbour = {
    prev: idx > 0 ? {
      mode: all[idx - 1].mode, beat_id: all[idx - 1].beatId,
      graphic_brief: all[idx - 1].graphic.kind === "generative"
        ? (all[idx - 1].graphic as any).brief : null,
    } : null,
    next: !isFinal ? {
      mode: all[idx + 1].mode, beat_id: all[idx + 1].beatId,
      graphic_brief: all[idx + 1].graphic.kind === "generative"
        ? (all[idx + 1].graphic as any).brief : null,
    } : null,
    is_final: isFinal,
  };
  const basePrompt = tpl
    .replace("{{SCENE_JSON}}", JSON.stringify(scene, null, 2))
    .replace("{{NEIGHBOUR_JSON}}", JSON.stringify(neighbour, null, 2))
    .replace("{{DESIGN_MD_PATH}}", path.join(repoRoot, "DESIGN.md"))
    .replace("{{MOTION_GRAPHICS_PATH}}", path.join(repoRoot, "standards", "motion-graphics.md"))
    .replace("{{BESPOKE_SEAMS_PATH}}", path.join(repoRoot, "standards", "bespoke-seams.md"))
    .replace("{{OUTPUT_PATH}}", outputPath);

  // Resumability via manifest: same prompt hash + recorded file still on disk
  // → skip. Replaces the prior file-existence-only check, so a re-run after a
  // prompt template change correctly invalidates and regenerates.
  const promptHash = computePromptHash({
    prompt: basePrompt,
    model,
    allowedTools,
  });
  if (isSceneSatisfied(episodeDir, fileStem, promptHash)) {
    return { sceneIndex: idx, outputPath, ok: true, attempts: 0 };
  }

  // Per-scene retry covers only "subagent failed to produce a file at all"
  // (timeout, error, missing write). HF gate failures are handled by the
  // single batch gate in generateAll after every scene has finished writing.
  let lastErr: string | undefined;
  let prompt = basePrompt;
  for (let attempt = 1; attempt <= maxRetries + 1; attempt++) {
    const startedAt = Date.now();
    try {
      await dispatcher.run(prompt);
      const wallclockMs = Date.now() - startedAt;
      if (!existsSync(outputPath)) {
        lastErr = `subagent did not write ${outputPath}`;
        prompt = basePrompt + `\n\n## Previous attempt failed\n${lastErr}`;
        continue;
      }
      const outputBytes = statSync(outputPath).size;
      const relativeOutputPath = path
        .relative(projectRoot, outputPath)
        .split(path.sep).join("/");
      recordSceneCompleted(episodeDir, fileStem, {
        kind: "generative",
        outputPath: relativeOutputPath,
        promptHash,
        outputBytes,
        wallclockMs,
      });
      return { sceneIndex: idx, outputPath, ok: true, attempts: attempt };
    } catch (err: any) {
      lastErr = String(err?.message ?? err);
      prompt = basePrompt + `\n\n## Previous attempt failed\n${lastErr}`;
    }
  }
  return { sceneIndex: idx, outputPath, ok: false, attempts: maxRetries + 1, error: lastErr };
}
