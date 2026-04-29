// tools/compositor/src/planner/generativeDispatcher.ts
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import type { EnrichedScene } from "./types.js";
import type { SubagentDispatcher } from "./segmenter.js";

const PROMPTS_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "prompts");

export interface GenerativeDispatcherInputs {
  episodeDir: string;
  scenes: EnrichedScene[];
  hfBin: string;
  dispatcherFor(scene: EnrichedScene): SubagentDispatcher;
  maxRetries?: number;
}

export interface GenerationResult {
  sceneIndex: number;
  outputPath: string;
  ok: boolean;
  attempts: number;
  error?: string;
}

export async function generateAll(inputs: GenerativeDispatcherInputs): Promise<GenerationResult[]> {
  const targets = inputs.scenes
    .map((s, i) => ({ s, i }))
    .filter(x => x.s.graphic.kind === "generative");
  const tasks = targets.map(({ s, i }) => generateOne(
    s, i, inputs.scenes, inputs.episodeDir, inputs.hfBin,
    inputs.dispatcherFor(s), inputs.maxRetries ?? 2,
  ));
  return Promise.all(tasks);
}

async function generateOne(
  scene: EnrichedScene, idx: number, all: EnrichedScene[],
  episodeDir: string, hfBin: string,
  dispatcher: SubagentDispatcher, maxRetries: number,
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

  let lastErr: string | undefined;
  let prompt = basePrompt;
  for (let attempt = 1; attempt <= maxRetries + 1; attempt++) {
    try {
      await dispatcher.run(prompt);
      if (!existsSync(outputPath)) {
        lastErr = `subagent did not write ${outputPath}`;
        prompt = basePrompt + `\n\n## Previous attempt failed\n${lastErr}`;
        continue;
      }
      try {
        // HF v0.4.x: lint/validate accept --strict-all as a no-op (forward-compat);
        // inspect uses --strict (the actually-supported strict mode). Mirror run-stage2-compose.sh.
        // KNOWN RACE: gates scan projectRoot while sibling scenes may still be writing to
        // compositions/ concurrently — a sibling's in-progress file could trip this scene's gate.
        // Accepted for now: HF lint typically finishes in <1s, T16 integration will surface any
        // real-episode failures, and a full fix would require post-write serialised gating.
        execFileSync(hfBin, ["lint", projectRoot, "--strict-all"], { stdio: "pipe" });
        execFileSync(hfBin, ["validate", projectRoot, "--strict-all"], { stdio: "pipe" });
        execFileSync(hfBin, ["inspect", projectRoot, "--strict", "--json"], { stdio: "pipe" });
      } catch (gateErr: any) {
        const stderrText = gateErr?.stderr?.toString?.() ?? gateErr?.message ?? String(gateErr);
        lastErr = `HF gate failed: ${stderrText}`;
        prompt = basePrompt + `\n\n## Previous attempt failed\n${lastErr}\nFix and rewrite the file.`;
        continue;
      }
      return { sceneIndex: idx, outputPath, ok: true, attempts: attempt };
    } catch (err: any) {
      lastErr = String(err?.message ?? err);
      prompt = basePrompt + `\n\n## Previous attempt failed\n${lastErr}`;
    }
  }
  return { sceneIndex: idx, outputPath, ok: false, attempts: maxRetries + 1, error: lastErr };
}
