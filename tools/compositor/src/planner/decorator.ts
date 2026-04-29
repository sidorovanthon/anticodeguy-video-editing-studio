// tools/compositor/src/planner/decorator.ts
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { Scene, EnrichedScene, GraphicSource } from "./types.js";
import type { SceneMode } from "../types.js";
import { pickTransition, type TransitionPickerState } from "./transitionPicker.js";
import type { SubagentDispatcher } from "./segmenter.js";

const PROMPTS_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "prompts");

export interface DecoratorInputs {
  scenes: Scene[];
  seamsInsideByScene: Map<number, number>;
  designMd: string;
  catalogTable: string;
  projectPrimaryTransition: string;
  dispatcher: SubagentDispatcher;
}

export async function decorate(inputs: DecoratorInputs): Promise<EnrichedScene[]> {
  const candidates: SceneMode[][] = inputs.scenes.map((s, i) =>
    narrowModeCandidates(s, i, inputs.seamsInsideByScene));

  const tpl = readFileSync(path.join(PROMPTS_DIR, "decorator.md"), "utf-8");
  const scenesPayload = inputs.scenes.map((s, i) => ({
    scene_index: i, mode_candidates: candidates[i],
    start_ms: s.startMs, end_ms: s.endMs,
    beat_id: s.beatId, narrative_position: s.narrativePosition,
    energy_hint: s.energyHint, mood_hint: s.moodHint,
    key_phrase: s.keyPhrase, script_chunk: s.scriptChunk,
  }));
  const seamsArr: number[] = inputs.scenes.map((_, i) => inputs.seamsInsideByScene.get(i) ?? 0);
  const prompt = tpl
    .replace("{{SCENES_JSON}}", JSON.stringify(scenesPayload, null, 2))
    .replace("{{SEAMS_INSIDE_JSON}}", JSON.stringify(seamsArr))
    .replace("{{DESIGN_PROMPT}}", inputs.designMd)
    .replace("{{CATALOG_TABLE}}", inputs.catalogTable);

  const raw = await inputs.dispatcher.run(prompt);
  const parsed = parseDecoratorOutput(raw);

  const state: TransitionPickerState = { totalScenes: inputs.scenes.length, accentsUsed: 0 };
  return inputs.scenes.map((s, i): EnrichedScene => {
    const dec = parsed.find(p => p.scene_index === i);
    if (!dec) throw new Error(`decorator missing output for scene ${i}`);
    if (!candidates[i].includes(dec.mode)) {
      throw new Error(`scene ${i + 1}: decorator chose '${dec.mode}', not in candidate set ${candidates[i].join(",")}`);
    }
    const transitionOut = pickTransition({
      energyHint: s.energyHint, narrativePosition: s.narrativePosition,
    }, inputs.projectPrimaryTransition, state);
    return { ...s, mode: dec.mode, transitionOut, graphic: dec.graphic };
  });
}

interface DecoratorOutput { scene_index: number; mode: SceneMode; graphic: GraphicSource; }

function parseDecoratorOutput(raw: string): DecoratorOutput[] {
  const m = raw.match(/```json\s*([\s\S]*?)```/);
  const text = (m ? m[1] : raw).trim();
  const arr = JSON.parse(text);
  if (!Array.isArray(arr)) throw new Error("decorator output is not a JSON array");
  return arr.map((o: any) => {
    const mode = o.mode as SceneMode;
    const g = o.graphic;
    let graphic: GraphicSource;
    if (g.source === "none") graphic = { kind: "none" };
    else if (typeof g.source === "string" && g.source.startsWith("catalog/")) {
      graphic = { kind: "catalog", name: g.source.slice("catalog/".length), data: g.data };
    } else if (g.source === "generative") {
      graphic = { kind: "generative", brief: String(g.brief ?? ""), data: g.data };
    } else throw new Error(`unknown graphic.source '${g.source}'`);
    return { scene_index: Number(o.scene_index), mode, graphic };
  });
}

function narrowModeCandidates(scene: Scene, idx: number, seamsByScene: Map<number, number>): SceneMode[] {
  if (scene.narrativePosition === "outro") return ["overlay"];
  let cs: SceneMode[] = ["head", "split", "broll", "overlay"];
  const seams = seamsByScene.get(idx) ?? 0;
  if (seams > 1) cs = cs.filter(m => m !== "head");
  if (scene.endMs - scene.startMs < 1500) cs = cs.filter(m => m === "overlay" || m === "head");
  return cs;
}
