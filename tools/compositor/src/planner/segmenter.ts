// tools/compositor/src/planner/segmenter.ts
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { Beat, Scene, NarrativePosition, EnergyHint, MoodHint } from "./types.js";

export interface SubagentDispatcher {
  run(promptText: string): Promise<string>;
}

interface WordTiming { startMs: number; endMs: number; text: string; }

const SCENE_MS_CAP = 5000;
const PROMPTS_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "prompts");

export interface SegmenterInputs {
  script: string;
  words: WordTiming[];
  masterDurationMs: number;
  dispatcher: SubagentDispatcher;
  maxRetries?: number;
}

export async function segment(inputs: SegmenterInputs): Promise<Scene[]> {
  const beats = await runBeatPass(inputs);
  const scenes: Scene[] = [];
  for (const beat of beats) {
    const dur = beat.endMs - beat.startMs;
    if (dur <= SCENE_MS_CAP) {
      scenes.push({
        startMs: beat.startMs, endMs: beat.endMs,
        beatId: beat.beatId,
        narrativePosition: beat.narrativePosition,
        energyHint: beat.energyHint,
        moodHint: beat.moodHint,
        keyPhrase: beat.beatSummary.split(".")[0].trim().slice(0, 80),
        scriptChunk: beat.beatSummary,
      });
      continue;
    }
    const subs = await runScenePass(beat, inputs);
    scenes.push(...subs);
  }
  return scenes;
}

async function runBeatPass(inputs: SegmenterInputs): Promise<Beat[]> {
  const tpl = readFileSync(path.join(PROMPTS_DIR, "segmenter-beats.md"), "utf-8");
  const preview = inputs.words.slice(0, 100).map(w => w.text).join(" ");
  const basePrompt = tpl
    .replace("{{SCRIPT}}", inputs.script)
    .replace("{{MASTER_DURATION_MS}}", String(inputs.masterDurationMs))
    .replace("{{TRANSCRIPT_PREVIEW}}", preview);
  const maxRetries = inputs.maxRetries ?? 2;
  let lastErr: unknown = null;
  let prompt = basePrompt;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const raw = await inputs.dispatcher.run(prompt);
      const parsed = parseJsonArray(raw, "beat pass");
      const aligned = alignBeats(parsed, inputs.script, inputs.words);
      validateBeats(aligned);
      return aligned;
    } catch (err) {
      lastErr = err;
      prompt = basePrompt + `\n\n## Previous attempt failed\n${String(err)}\nFix the issue and return valid JSON.`;
    }
  }
  throw new Error(`segmenter beat pass failed after ${maxRetries + 1} attempts: ${lastErr}`);
}

async function runScenePass(beat: Beat, inputs: SegmenterInputs): Promise<Scene[]> {
  const tpl = readFileSync(path.join(PROMPTS_DIR, "segmenter-scenes.md"), "utf-8");
  const beatScript = inputs.script;   // Beat carries its full script chunk via summary; refine later if needed.
  const prompt = tpl
    .replace("{{BEAT_JSON}}", JSON.stringify({
      beat_id: beat.beatId, narrative_position: beat.narrativePosition,
      energy_hint: beat.energyHint, mood_hint: beat.moodHint ?? null,
    }))
    .replace("{{SCRIPT_CHUNK}}", beatScript)
    .replace("{{BEAT_DURATION_MS}}", String(beat.endMs - beat.startMs));
  const raw = await inputs.dispatcher.run(prompt);
  const subs = parseJsonArray(raw, "scene pass");
  return alignSubScenes(subs, beat, beatScript);
}

function parseJsonArray(raw: string, ctx: string): unknown[] {
  const m = raw.match(/```json\s*([\s\S]*?)```/);
  const text = (m ? m[1] : raw).trim();
  let arr: unknown;
  try { arr = JSON.parse(text); } catch (e) {
    throw new Error(`${ctx}: not valid JSON: ${(e as Error).message}`);
  }
  if (!Array.isArray(arr)) throw new Error(`${ctx}: output is not a JSON array`);
  return arr;
}

function alignBeats(beats: unknown[], script: string, words: WordTiming[]): Beat[] {
  return beats.map((b: any, i): Beat => {
    const np = String(b.narrative_position ?? "");
    const en = String(b.energy_hint ?? "");
    const mh = b.mood_hint ? String(b.mood_hint) : undefined;
    if (!isNarrative(np)) throw new Error(`beat ${i + 1}: invalid narrative_position '${np}'`);
    if (!isEnergy(en)) throw new Error(`beat ${i + 1}: invalid energy_hint '${en}'`);
    if (mh && !isMood(mh)) throw new Error(`beat ${i + 1}: invalid mood_hint '${mh}'`);
    const startOff = Number(b.script_start_offset ?? 0);
    const endOff = Number(b.script_end_offset ?? script.length);
    return {
      beatId: String(b.beat_id ?? `B${i + 1}`),
      beatSummary: String(b.beat_summary ?? ""),
      narrativePosition: np as NarrativePosition,
      energyHint: en as EnergyHint,
      moodHint: mh as MoodHint | undefined,
      startMs: wordTimeAt(script, words, startOff, "start"),
      endMs: wordTimeAt(script, words, endOff, "end"),
    };
  });
}

function alignSubScenes(subs: unknown[], beat: Beat, beatScript: string): Scene[] {
  const totalDur = beat.endMs - beat.startMs;
  return subs.map((s: any, i): Scene => {
    const localStart = Number(s.char_offset_start ?? 0);
    const localEnd = Number(s.char_offset_end ?? beatScript.length);
    const len = Math.max(1, beatScript.length);
    return {
      startMs: beat.startMs + Math.round((totalDur * localStart) / len),
      endMs: beat.startMs + Math.round((totalDur * localEnd) / len),
      beatId: beat.beatId,
      narrativePosition: beat.narrativePosition,
      energyHint: beat.energyHint,
      moodHint: beat.moodHint,
      keyPhrase: String(s.key_phrase ?? "").trim(),
      scriptChunk: String(s.script_chunk ?? "").trim(),
    };
  });
}

function validateBeats(beats: Beat[]): void {
  if (beats.length === 0) throw new Error("beat pass returned 0 beats");
  for (let i = 0; i < beats.length; i++) {
    if (beats[i].endMs <= beats[i].startMs) throw new Error(`beat ${beats[i].beatId}: end <= start`);
    if (i > 0 && beats[i].startMs < beats[i - 1].endMs) throw new Error(`beats overlap at ${i}`);
  }
}

function wordTimeAt(script: string, words: WordTiming[], charOff: number, side: "start" | "end"): number {
  if (script.length === 0 || words.length === 0) return 0;
  // Treat charOff as a split point: contiguous beats abut at the same word.startMs
  // so boundary offsets land cleanly without overlap. Special-case end-of-script
  // to extend the final beat to the actual end of audio.
  if (side === "end" && charOff >= script.length) return words[words.length - 1].endMs;
  const frac = Math.max(0, Math.min(1, charOff / script.length));
  const idx = Math.min(words.length - 1, Math.floor(frac * words.length));
  return words[idx].startMs;
}

function isNarrative(v: string): v is NarrativePosition {
  return ["opening", "setup", "main", "topic_change", "climax", "wind_down", "outro"].includes(v);
}
function isEnergy(v: string): v is EnergyHint { return ["calm", "medium", "high"].includes(v); }
function isMood(v: string): v is MoodHint {
  return ["warm", "cold", "editorial", "tech", "tense", "playful", "dramatic", "premium", "retro"].includes(v);
}
