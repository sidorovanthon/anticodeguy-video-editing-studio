// tools/compositor/src/planner/seamPlanFormat.ts
import type {
  SeamPlan, EnrichedScene, GraphicSource,
  NarrativePosition, EnergyHint, MoodHint,
} from "./types.js";
import { parseSceneMode } from "../sceneMode.js";

const NARRATIVE_POSITIONS: ReadonlyArray<NarrativePosition> = [
  "opening", "setup", "main", "topic_change", "climax", "wind_down", "outro",
];
const ENERGY_HINTS: ReadonlyArray<EnergyHint> = ["calm", "medium", "high"];
const MOOD_HINTS: ReadonlyArray<MoodHint> = [
  "warm", "cold", "editorial", "tech", "tense",
  "playful", "dramatic", "premium", "retro",
];

const SCENE_MS_CAP = 5000;

export function parseSeamPlan(text: string): SeamPlan {
  const lines = text.split(/\r?\n/);
  const headerRe = /^# Seam plan:\s+(\S+)\s+\(master_duration_ms=(\d+)\)/;
  let slug = ""; let masterDurationMs = 0;
  for (const ln of lines.slice(0, 3)) {
    const m = ln.match(headerRe);
    if (m) { slug = m[1]; masterDurationMs = parseInt(m[2], 10); break; }
  }
  if (!slug) throw new Error("seam-plan: missing or malformed header");

  const sceneBlocks: string[][] = [];
  let current: string[] | null = null;
  for (const ln of lines) {
    if (/^## Scene\s+\d+/.test(ln)) {
      if (current) sceneBlocks.push(current);
      current = [ln];
    } else if (current) {
      current.push(ln);
    }
  }
  if (current) sceneBlocks.push(current);

  const scenes: EnrichedScene[] = sceneBlocks.map((b, i) => parseSceneBlock(b, i + 1));
  return { slug, masterDurationMs, scenes };
}

function parseSceneBlock(block: string[], sceneNum: number): EnrichedScene {
  const fields = parseFieldBullets(block);
  const startMs = numField(fields, "start_ms", sceneNum);
  const endMs = numField(fields, "end_ms", sceneNum);
  if (endMs - startMs > SCENE_MS_CAP) {
    throw new Error(`scene ${sceneNum} exceeds 5s cap (${endMs - startMs}ms)`);
  }
  const beatId = strField(fields, "beat_id", sceneNum);
  const narrativePosition = enumField(fields, "narrative_position", NARRATIVE_POSITIONS, sceneNum);
  const energyHint = enumField(fields, "energy_hint", ENERGY_HINTS, sceneNum);
  const moodRaw = fields.get("mood_hint");
  const moodHint = (moodRaw && moodRaw !== "(default)")
    ? validateEnum(moodRaw, MOOD_HINTS, `scene ${sceneNum} mood_hint`)
    : undefined;
  const mode = parseSceneMode(strField(fields, "mode", sceneNum));
  const transitionOut = strField(fields, "transition_out", sceneNum);
  const keyPhrase = unquote(strField(fields, "key_phrase", sceneNum));
  const scriptChunk = (fields.get("__script") ?? "").trim();
  if (!scriptChunk) throw new Error(`scene ${sceneNum}: missing script: block`);
  const graphic = parseGraphic(fields, sceneNum);

  return {
    startMs, endMs, beatId,
    narrativePosition, energyHint, moodHint,
    keyPhrase, scriptChunk, mode, transitionOut, graphic,
  };
}

function parseFieldBullets(block: string[]): Map<string, string> {
  const out = new Map<string, string>();
  let inGraphic = false;
  let scriptLines: string[] | null = null;
  let briefLines: string[] | null = null;

  for (const raw of block) {
    if (/^## Scene\s+\d+/.test(raw)) continue;

    if (/^\s*script:\s*\|?\s*$/.test(raw)) {
      scriptLines = []; briefLines = null; continue;
    }
    if (scriptLines !== null) {
      // Continuation of script: indented lines until end of block.
      scriptLines.push(raw.replace(/^\s{0,4}/, ""));
      out.set("__script", scriptLines.join("\n"));
      continue;
    }

    const bullet = raw.match(/^(\s*)-\s+([\w_]+):\s*(.*)$/);
    if (bullet) {
      const [, , key, valueRaw] = bullet;
      if (key === "graphic") { inGraphic = true; briefLines = null; continue; }
      if (inGraphic && key === "brief") {
        if (valueRaw === "|" || valueRaw === "") { briefLines = []; continue; }
        out.set("graphic.brief", valueRaw); continue;
      }
      if (inGraphic && key === "data") { out.set("graphic.data", valueRaw); briefLines = null; continue; }
      if (inGraphic && key === "source") { out.set("graphic.source", valueRaw); briefLines = null; continue; }
      if (inGraphic && key === "name") { out.set("graphic.name", valueRaw); briefLines = null; continue; }
      out.set(key, valueRaw);
      briefLines = null;
      continue;
    }

    if (briefLines !== null && /\S/.test(raw)) {
      briefLines.push(raw.replace(/^\s{0,6}/, ""));
      out.set("graphic.brief", briefLines.join("\n").trimEnd());
    }
  }
  return out;
}

function numField(f: Map<string, string>, name: string, n: number): number {
  const v = f.get(name);
  if (v === undefined) throw new Error(`scene ${n}: missing ${name}`);
  const x = parseInt(v, 10);
  if (Number.isNaN(x)) throw new Error(`scene ${n}: ${name} not int (${v})`);
  return x;
}
function strField(f: Map<string, string>, name: string, n: number): string {
  const v = f.get(name);
  if (!v) throw new Error(`scene ${n}: missing ${name}`);
  return v;
}
function enumField<T extends string>(f: Map<string, string>, name: string, allowed: ReadonlyArray<T>, n: number): T {
  return validateEnum(strField(f, name, n), allowed, `scene ${n} ${name}`);
}
function validateEnum<T extends string>(v: string, allowed: ReadonlyArray<T>, ctx: string): T {
  if (!(allowed as ReadonlyArray<string>).includes(v)) {
    throw new Error(`${ctx}: invalid '${v}'; expected one of ${allowed.join(", ")}`);
  }
  return v as T;
}
function unquote(s: string): string { return s.replace(/^"(.*)"$/, "$1"); }

function parseGraphic(f: Map<string, string>, n: number): GraphicSource {
  const source = f.get("graphic.source");
  if (!source) throw new Error(`scene ${n}: missing graphic.source`);
  if (source === "none") return { kind: "none" };
  if (source.startsWith("catalog/")) {
    const name = source.slice("catalog/".length);
    const data = f.get("graphic.data");
    return { kind: "catalog", name, data: data ? parseDataPayload(data) : undefined };
  }
  if (source === "generative") {
    const brief = f.get("graphic.brief");
    if (!brief) throw new Error(`scene ${n}: generative graphic missing brief`);
    const data = f.get("graphic.data");
    return { kind: "generative", brief, data: data ? parseDataPayload(data) : undefined };
  }
  throw new Error(`scene ${n}: unknown graphic.source '${source}'`);
}
function parseDataPayload(raw: string): unknown {
  const t = raw.trim();
  if (t.startsWith("{") || t.startsWith("[")) {
    try { return JSON.parse(t); } catch { /* fall through */ }
  }
  return t;
}

export function writeSeamPlan(plan: SeamPlan): string {
  const out: string[] = [];
  out.push(`# Seam plan: ${plan.slug} (master_duration_ms=${plan.masterDurationMs})`);
  out.push("");
  plan.scenes.forEach((s, i) => {
    out.push(`## Scene ${i + 1}`);
    out.push(`- start_ms: ${s.startMs}`);
    out.push(`- end_ms: ${s.endMs}`);
    out.push(`- beat_id: ${s.beatId}`);
    out.push(`- narrative_position: ${s.narrativePosition}`);
    out.push(`- energy_hint: ${s.energyHint}`);
    out.push(`- mood_hint: ${s.moodHint ?? "(default)"}`);
    out.push(`- mode: ${s.mode}`);
    out.push(`- transition_out: ${s.transitionOut}`);
    out.push(`- key_phrase: "${s.keyPhrase}"`);
    out.push(`- graphic:`);
    if (s.graphic.kind === "none") {
      out.push(`  - source: none`);
    } else if (s.graphic.kind === "catalog") {
      out.push(`  - source: catalog/${s.graphic.name}`);
      if (s.graphic.data !== undefined) out.push(`  - data: ${JSON.stringify(s.graphic.data)}`);
    } else {
      out.push(`  - source: generative`);
      out.push(`  - brief: |`);
      for (const ln of s.graphic.brief.split("\n")) out.push(`      ${ln}`);
      if (s.graphic.data !== undefined) out.push(`  - data: ${JSON.stringify(s.graphic.data)}`);
    }
    out.push("");
    out.push(`  script: |`);
    for (const ln of s.scriptChunk.split("\n")) out.push(`    ${ln}`);
    out.push("");
  });
  return out.join("\n");
}
