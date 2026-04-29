# Phase 6b — Agentic Graphics Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the three-phase planner (segmenter → snap → decorator) that produces an enriched `seam-plan.md`, plus the parallel generative dispatcher that turns that plan into HF-compliant sub-compositions, plus the compositor extension that consumes the new format.

**Architecture:** Foundation-first. Phase A (deterministic, fully TDD-able): seam-plan format parser/writer, mode-validator, transition-picker, snap-pass. Phase B (LLM-driven, prompt + retry harness): segmenter, decorator. Phase C (integration): pipeline scripts, compositor extension, generative dispatcher. Phase D: end-to-end fixture exercising every rule branch. Each phase is independently committable; the foundation has value even before the LLM-driven phases land (a host could hand-author the enriched seam-plan and get a passing compose).

**Tech Stack:** TypeScript (vitest for tests, tsx for run), Bash (pipeline wrappers), Claude Agent SDK or equivalent subagent-dispatch primitive (the codebase already uses subagents at `tools/scripts/run-stage1.sh:159`; the planner reuses that pattern). Child-process invocations use `execFileSync` (no shell) per security guidance.

**Spec:** [`docs/superpowers/specs/2026-04-28-phase-6b-planner-design.md`](../specs/2026-04-28-phase-6b-planner-design.md)

**Depends on:** [`2026-04-28-hf-methodology-promotions.md`](2026-04-28-hf-methodology-promotions.md) — must land first; this plan assumes the standards updates are in place.

---

## Pre-flight context

Existing layout (already in place):
- `tools/compositor/src/seamPlanner.ts` — current mechanical seam planner (will be superseded but kept for fallback / smoke tests).
- `tools/compositor/src/seamPlanWriter.ts` — current flat-format seam-plan parser/writer (replaced by new format).
- `tools/compositor/src/sceneMode.ts` — `parseSceneMode()` enum guard; stays.
- `tools/compositor/src/composer.ts` — `renderSeamFragment` is where graphics get emitted; extended in Phase C.
- `tools/compositor/test/` — vitest, mirror layout (one `*.test.ts` per source file).
- `tools/compositor/package.json` — `"test": "vitest run"`.

New layout introduced by this plan:
- `tools/compositor/src/planner/` — all new TS code.
- `tools/compositor/test/planner/` — tests for the new code, mirroring source.
- `tools/scripts/run-stage2-plan.sh`, `tools/scripts/run-stage2-generate.sh` — new wrappers.

Existing seam-plan format (to be superseded): single line per seam, `SEAM N at_ms=X scene: <mode> ends_at_ms=Y`. The new format is markdown with ATX `## Scene N` headers and bullet fields per the spec.

---

## File Structure

**New files (TypeScript):**
- `tools/compositor/src/planner/types.ts` — `Scene`, `Beat`, `EnrichedScene`, `GraphicSpec`, `NarrativePosition`, `EnergyHint`, `MoodHint` types.
- `tools/compositor/src/planner/seamPlanFormat.ts` — markdown parser + writer for enriched seam-plan.
- `tools/compositor/src/planner/modeValidator.ts` — hard-rule enforcement.
- `tools/compositor/src/planner/transitionPicker.ts` — HF matrix lookup.
- `tools/compositor/src/planner/snap.ts` — phrase-boundary snap pass.
- `tools/compositor/src/planner/segmenter.ts` — LLM segmenter dispatch + retry harness.
- `tools/compositor/src/planner/decorator.ts` — rules + LLM decorator dispatch.
- `tools/compositor/src/planner/generativeDispatcher.ts` — parallel subagent dispatch.

**New files (Bash):**
- `tools/scripts/run-stage2-plan.sh`
- `tools/scripts/run-stage2-generate.sh`

**New files (tests):**
- `tools/compositor/test/planner/seamPlanFormat.test.ts`
- `tools/compositor/test/planner/modeValidator.test.ts`
- `tools/compositor/test/planner/transitionPicker.test.ts`
- `tools/compositor/test/planner/snap.test.ts`
- `tools/compositor/test/planner/segmenter.test.ts`
- `tools/compositor/test/planner/decorator.test.ts`
- `tools/compositor/test/planner/integration.test.ts`
- `tools/compositor/test/planner/fixtures/integration/script.txt`
- `tools/compositor/test/planner/fixtures/integration/expected-seam-plan.md`

**Modified files:**
- `tools/compositor/src/composer.ts` — `renderSeamFragment` reads `graphic.source` field and emits catalog references or generative-sub-composition references.
- `tools/compositor/src/index.ts` — register new `plan` and `generate` subcommands.

---

# Phase A — Foundation (deterministic, fully TDD-able)

### Task 1: Types — `planner/types.ts`

**Files:**
- Create: `tools/compositor/src/planner/types.ts`.

- [ ] **Step 1: Write the type module**

```typescript
// tools/compositor/src/planner/types.ts
import type { SceneMode } from "../sceneMode.js";

export type NarrativePosition =
  | "opening" | "setup" | "main" | "topic_change"
  | "climax" | "wind_down" | "outro";

export type EnergyHint = "calm" | "medium" | "high";

export type MoodHint =
  | "warm" | "cold" | "editorial" | "tech" | "tense"
  | "playful" | "dramatic" | "premium" | "retro";

export interface Beat {
  beatId: string;
  beatSummary: string;
  narrativePosition: NarrativePosition;
  energyHint: EnergyHint;
  moodHint?: MoodHint;
  startMs: number;
  endMs: number;
}

export interface Scene {
  startMs: number;
  endMs: number;
  beatId: string;
  narrativePosition: NarrativePosition;
  energyHint: EnergyHint;
  moodHint?: MoodHint;
  keyPhrase: string;
  scriptChunk: string;
}

export type GraphicSource =
  | { kind: "none" }
  | { kind: "catalog"; name: string; data?: unknown }
  | { kind: "generative"; brief: string; data?: unknown };

export interface EnrichedScene extends Scene {
  mode: SceneMode;
  transitionOut: string;
  graphic: GraphicSource;
}

export interface SeamPlan {
  slug: string;
  masterDurationMs: number;
  scenes: EnrichedScene[];
}
```

- [ ] **Step 2: Confirm it compiles**

Run: `cd tools/compositor && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add tools/compositor/src/planner/types.ts
git commit -m "feat(planner): add types for enriched seam-plan"
```

---

### Task 2: Seam-plan format parser/writer — `planner/seamPlanFormat.ts`

**Files:**
- Create: `tools/compositor/src/planner/seamPlanFormat.ts`.
- Create: `tools/compositor/test/planner/seamPlanFormat.test.ts`.

**Why:** The contract between every other component. Round-trip parser + writer.

- [ ] **Step 1: Write the failing test**

```typescript
// tools/compositor/test/planner/seamPlanFormat.test.ts
import { describe, it, expect } from "vitest";
import { parseSeamPlan, writeSeamPlan } from "../../src/planner/seamPlanFormat.js";

const SAMPLE = `# Seam plan: 2026-04-28-test (master_duration_ms=8800)

## Scene 1
- start_ms: 0
- end_ms: 4200
- beat_id: B1
- narrative_position: opening
- energy_hint: medium
- mode: head
- transition_out: crossfade
- key_phrase: "DRM is a moving target"
- graphic:
  - source: none

  script: |
    Hello, today we're talking about desktop software licensing
    and why every approach is wrong in a different way.

## Scene 2
- start_ms: 4200
- end_ms: 8800
- beat_id: B1
- narrative_position: setup
- energy_hint: medium
- mode: split
- transition_out: push-slide
- key_phrase: "three approaches"
- graphic:
  - source: generative
  - brief: |
      Right-side panel: three labelled vertical columns sliding in
      left-to-right with 120 ms staggers.

  script: |
    There are basically three approaches that actually ship in the wild...
`;

describe("seamPlanFormat", () => {
  it("parses the sample document", () => {
    const plan = parseSeamPlan(SAMPLE);
    expect(plan.slug).toBe("2026-04-28-test");
    expect(plan.masterDurationMs).toBe(8800);
    expect(plan.scenes).toHaveLength(2);
    expect(plan.scenes[0].mode).toBe("head");
    expect(plan.scenes[0].graphic.kind).toBe("none");
    expect(plan.scenes[1].mode).toBe("split");
    expect(plan.scenes[1].graphic.kind).toBe("generative");
    if (plan.scenes[1].graphic.kind === "generative") {
      expect(plan.scenes[1].graphic.brief).toContain("Right-side panel");
    }
    expect(plan.scenes[1].keyPhrase).toBe("three approaches");
  });

  it("round-trips: parse → write → parse yields the same plan", () => {
    const plan = parseSeamPlan(SAMPLE);
    const re = writeSeamPlan(plan);
    expect(parseSeamPlan(re)).toEqual(plan);
  });

  it("rejects scenes that exceed the 5s cap", () => {
    const broken = SAMPLE.replace("end_ms: 4200", "end_ms: 6500");
    expect(() => parseSeamPlan(broken)).toThrow(/exceeds 5s cap/i);
  });

  it("rejects an unknown narrative_position", () => {
    const broken = SAMPLE.replace("narrative_position: opening", "narrative_position: warmup");
    expect(() => parseSeamPlan(broken)).toThrow(/narrative_position/i);
  });

  it("rejects a generative scene without brief", () => {
    const broken = SAMPLE
      .replace(/  - source: generative\s*\n\s*- brief:[\s\S]*?\n\n/, "  - source: generative\n\n");
    expect(() => parseSeamPlan(broken)).toThrow(/generative.*brief/i);
  });
});
```

- [ ] **Step 2: Run, verify it fails**

Run: `cd tools/compositor && npx vitest run test/planner/seamPlanFormat.test.ts`
Expected: ENOENT.

- [ ] **Step 3: Implement the parser/writer**

```typescript
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
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd tools/compositor && npx vitest run test/planner/seamPlanFormat.test.ts`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/planner/seamPlanFormat.ts \
        tools/compositor/test/planner/seamPlanFormat.test.ts
git commit -m "feat(planner): seam-plan markdown format parser and writer"
```

---

### Task 3: Mode validator — `planner/modeValidator.ts`

**Files:**
- Create: `tools/compositor/src/planner/modeValidator.ts`.
- Create: `tools/compositor/test/planner/modeValidator.test.ts`.

Hard rules (1) `head↔head` (2) `head↔overlay`/`overlay↔head` (3) `overlay→overlay` (4) same-graphic `split→split` (5) same-graphic `broll→broll` (6) `seamsInside>1 ⇒ ¬head` (7) `outro ⇒ overlay+catalog/subscribe-cta` (8) `dur<1500 ⇒ {overlay, head}`.

- [ ] **Step 1: Write the failing test**

```typescript
// tools/compositor/test/planner/modeValidator.test.ts
import { describe, it, expect } from "vitest";
import { validateSeamPlan } from "../../src/planner/modeValidator.js";
import type { SeamPlan, EnrichedScene } from "../../src/planner/types.js";

function scene(o: Partial<EnrichedScene>): EnrichedScene {
  return {
    startMs: 0, endMs: 4000, beatId: "B1",
    narrativePosition: "main", energyHint: "medium",
    keyPhrase: "p", scriptChunk: "s",
    mode: "head", transitionOut: "crossfade",
    graphic: { kind: "none" },
    ...o,
  };
}

const noSeams = new Map<number, number>();

describe("modeValidator", () => {
  it("accepts a valid two-scene plan", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 8000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "head" }),
      scene({ startMs: 4000, endMs: 8000, mode: "split", graphic: { kind: "generative", brief: "x" } }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).not.toThrow();
  });

  it("rejects head→head", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 8000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "head" }),
      scene({ startMs: 4000, endMs: 8000, mode: "head" }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).toThrow(/head→head/);
  });

  it("rejects head→overlay", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 8000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "head" }),
      scene({ startMs: 4000, endMs: 8000, mode: "overlay",
              graphic: { kind: "catalog", name: "subscribe-cta" } }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).toThrow(/head→overlay|overlay→head/);
  });

  it("rejects overlay→overlay", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 8000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "overlay",
              graphic: { kind: "catalog", name: "lower-third" } }),
      scene({ startMs: 4000, endMs: 8000, mode: "overlay",
              graphic: { kind: "catalog", name: "subscribe-cta" } }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).toThrow(/overlay→overlay/);
  });

  it("rejects same-graphic split→split", () => {
    const g = { kind: "generative" as const, brief: "same brief" };
    const plan: SeamPlan = { slug: "t", masterDurationMs: 8000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "split", graphic: g }),
      scene({ startMs: 4000, endMs: 8000, mode: "split", graphic: g }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).toThrow(/same-graphic split/);
  });

  it("rejects head with seamsInside>1", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 4000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "head" }),
    ]};
    const seams = new Map([[0, 3]]);
    expect(() => validateSeamPlan(plan, seams)).toThrow(/seamsInside.*head/);
  });

  it("rejects outro that is not overlay+subscribe-cta", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 4000, scenes: [
      scene({ startMs: 0, endMs: 4000, mode: "head", narrativePosition: "outro" }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).toThrow(/outro/);
  });

  it("rejects short scene with non-{head,overlay} mode", () => {
    const plan: SeamPlan = { slug: "t", masterDurationMs: 4000, scenes: [
      scene({ startMs: 0, endMs: 1200, mode: "split",
              graphic: { kind: "generative", brief: "x" } }),
    ]};
    expect(() => validateSeamPlan(plan, noSeams)).toThrow(/short scene/);
  });
});
```

- [ ] **Step 2: Run, verify it fails**

Run: `cd tools/compositor && npx vitest run test/planner/modeValidator.test.ts`

- [ ] **Step 3: Implement**

```typescript
// tools/compositor/src/planner/modeValidator.ts
import type { SeamPlan, GraphicSource } from "./types.js";

export function validateSeamPlan(plan: SeamPlan, seamsInsideByScene: Map<number, number>): void {
  for (let i = 0; i < plan.scenes.length; i++) {
    const s = plan.scenes[i];
    const dur = s.endMs - s.startMs;
    const seams = seamsInsideByScene.get(i) ?? 0;

    if (seams > 1 && s.mode === "head") {
      throw new Error(`scene ${i + 1}: seamsInside=${seams} but mode=head; head requires ≤1 seam`);
    }
    if (s.narrativePosition === "outro") {
      const ok = s.graphic.kind === "catalog" && s.graphic.name === "subscribe-cta";
      if (s.mode !== "overlay" || !ok) {
        throw new Error(`scene ${i + 1}: outro must be mode=overlay + graphic=catalog/subscribe-cta`);
      }
    }
    if (dur < 1500 && s.mode !== "head" && s.mode !== "overlay") {
      throw new Error(`scene ${i + 1}: short scene (${dur}ms) must be head or overlay`);
    }
    if (i === 0) continue;
    const prev = plan.scenes[i - 1];

    if (prev.mode === "head" && s.mode === "head") {
      throw new Error(`scenes ${i}-${i + 1}: head→head transition forbidden`);
    }
    if ((prev.mode === "head" && s.mode === "overlay") ||
        (prev.mode === "overlay" && s.mode === "head")) {
      throw new Error(`scenes ${i}-${i + 1}: head→overlay/overlay→head forbidden`);
    }
    if (prev.mode === "overlay" && s.mode === "overlay") {
      throw new Error(`scenes ${i}-${i + 1}: overlay→overlay forbidden`);
    }
    if (prev.mode === "split" && s.mode === "split" && graphicEqual(prev.graphic, s.graphic)) {
      throw new Error(`scenes ${i}-${i + 1}: same-graphic split→split forbidden`);
    }
    if (prev.mode === "broll" && s.mode === "broll" && graphicEqual(prev.graphic, s.graphic)) {
      throw new Error(`scenes ${i}-${i + 1}: same-graphic broll→broll forbidden`);
    }
  }
}

function graphicEqual(a: GraphicSource, b: GraphicSource): boolean {
  if (a.kind !== b.kind) return false;
  if (a.kind === "none") return true;
  if (a.kind === "catalog" && b.kind === "catalog") return a.name === b.name;
  if (a.kind === "generative" && b.kind === "generative") return a.brief.trim() === b.brief.trim();
  return false;
}
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd tools/compositor && npx vitest run test/planner/modeValidator.test.ts`
Expected: 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/planner/modeValidator.ts \
        tools/compositor/test/planner/modeValidator.test.ts
git commit -m "feat(planner): mode validator enforcing transition matrix + outro + duration rules"
```

---

### Task 4: Transition picker — `planner/transitionPicker.ts`

**Files:**
- Create: `tools/compositor/src/planner/transitionPicker.ts`.
- Create: `tools/compositor/test/planner/transitionPicker.test.ts`.

- [ ] **Step 1: Write the failing test**

```typescript
// tools/compositor/test/planner/transitionPicker.test.ts
import { describe, it, expect } from "vitest";
import { pickTransition, type TransitionPickerState } from "../../src/planner/transitionPicker.js";

describe("transitionPicker", () => {
  it("calm + main → primary crossfade", () => {
    const st: TransitionPickerState = { totalScenes: 8, accentsUsed: 0 };
    expect(pickTransition({ energyHint: "calm", narrativePosition: "main" }, "crossfade", st)).toBe("crossfade");
  });

  it("high + topic_change → an accent, increments counter", () => {
    const st: TransitionPickerState = { totalScenes: 10, accentsUsed: 0 };
    const t = pickTransition({ energyHint: "high", narrativePosition: "topic_change" }, "crossfade", st);
    expect(t).not.toBe("crossfade");
    expect(st.accentsUsed).toBe(1);
  });

  it("reverts to primary once accent budget is spent", () => {
    const st: TransitionPickerState = { totalScenes: 10, accentsUsed: 3 };
    expect(pickTransition({ energyHint: "high", narrativePosition: "topic_change" }, "crossfade", st)).toBe("crossfade");
    expect(st.accentsUsed).toBe(3);
  });

  it("outro returns primary even at high energy", () => {
    const st: TransitionPickerState = { totalScenes: 5, accentsUsed: 0 };
    expect(pickTransition({ energyHint: "high", narrativePosition: "outro" }, "crossfade", st)).toBe("crossfade");
  });
});
```

- [ ] **Step 2: Run, verify it fails**

Run: `cd tools/compositor && npx vitest run test/planner/transitionPicker.test.ts`

- [ ] **Step 3: Implement**

```typescript
// tools/compositor/src/planner/transitionPicker.ts
import type { EnergyHint, NarrativePosition } from "./types.js";

export interface TransitionPickerState {
  totalScenes: number;
  accentsUsed: number;
}

interface Input {
  energyHint: EnergyHint;
  narrativePosition: NarrativePosition;
}

const ACCENT_BUDGET_RATIO = 0.3;

export function pickTransition(input: Input, projectPrimary: string, state: TransitionPickerState): string {
  if (input.narrativePosition === "outro") return projectPrimary;
  const wantsAccent =
    (input.narrativePosition === "topic_change" && input.energyHint === "high") ||
    (input.narrativePosition === "climax" && input.energyHint === "high");
  if (!wantsAccent) return projectPrimary;
  const budget = Math.floor(state.totalScenes * ACCENT_BUDGET_RATIO);
  if (state.accentsUsed >= budget) return projectPrimary;
  state.accentsUsed += 1;
  return accentTransitionFor(input.energyHint);
}

function accentTransitionFor(energy: EnergyHint): string {
  if (energy === "high") return "push-slide";
  if (energy === "medium") return "staggered-blocks";
  return "blur-crossfade";
}
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd tools/compositor && npx vitest run test/planner/transitionPicker.test.ts`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/planner/transitionPicker.ts \
        tools/compositor/test/planner/transitionPicker.test.ts
git commit -m "feat(planner): deterministic transition picker (HF matrix + accent budget)"
```

---

### Task 5: Snap pass — `planner/snap.ts`

**Files:**
- Create: `tools/compositor/src/planner/snap.ts`.
- Create: `tools/compositor/test/planner/snap.test.ts`.

- [ ] **Step 1: Write the failing test**

```typescript
// tools/compositor/test/planner/snap.test.ts
import { describe, it, expect } from "vitest";
import { snapScenes, computePhraseBoundaries } from "../../src/planner/snap.js";
import type { Scene } from "../../src/planner/types.js";

const WORDS = [
  { startMs: 0,    endMs: 350,  text: "Hello" },
  { startMs: 380,  endMs: 720,  text: "today" },
  { startMs: 1100, endMs: 1480, text: "the" },     // gap 380 before → boundary at 910
  { startMs: 1500, endMs: 1900, text: "topic" },
  { startMs: 2100, endMs: 2400, text: "is" },
  { startMs: 2700, endMs: 3300, text: "DRM" },     // gap 300 before → boundary at 2550
  { startMs: 4400, endMs: 4900, text: "fin" },     // gap 1100 → boundary at 3850
];

describe("snap pass", () => {
  it("computes phrase boundaries from gaps > 150ms", () => {
    const bs = computePhraseBoundaries(WORDS, 150);
    expect(bs).toEqual([910, 2550, 3850]);
  });

  it("snaps a boundary within ±300ms tolerance", () => {
    const scenes: Scene[] = [
      { startMs: 0, endMs: 1000, beatId: "B1", narrativePosition: "opening",
        energyHint: "medium", keyPhrase: "p", scriptChunk: "x" },
      { startMs: 1000, endMs: 5000, beatId: "B1", narrativePosition: "main",
        energyHint: "medium", keyPhrase: "p2", scriptChunk: "y" },
    ];
    const snapped = snapScenes(scenes, [910, 2550, 3850], 300);
    expect(snapped[0].endMs).toBe(910);
    expect(snapped[1].startMs).toBe(910);
  });

  it("leaves boundary unchanged when no phrase boundary is within tolerance", () => {
    const scenes: Scene[] = [
      { startMs: 0, endMs: 5000, beatId: "B1", narrativePosition: "opening",
        energyHint: "medium", keyPhrase: "p", scriptChunk: "x" },
      { startMs: 5000, endMs: 10000, beatId: "B1", narrativePosition: "main",
        energyHint: "medium", keyPhrase: "p2", scriptChunk: "y" },
    ];
    const snapped = snapScenes(scenes, [910, 2550, 3850], 300);
    expect(snapped[0].endMs).toBe(5000);
  });

  it("preserves monotonic ordering", () => {
    const scenes: Scene[] = [
      { startMs: 0, endMs: 800, beatId: "B1", narrativePosition: "opening",
        energyHint: "medium", keyPhrase: "p", scriptChunk: "x" },
      { startMs: 800, endMs: 4000, beatId: "B1", narrativePosition: "main",
        energyHint: "medium", keyPhrase: "p2", scriptChunk: "y" },
    ];
    const snapped = snapScenes(scenes, [910], 300);
    expect(snapped[0].endMs).toBeLessThan(snapped[1].endMs);
  });
});
```

- [ ] **Step 2: Run, verify it fails**

Run: `cd tools/compositor && npx vitest run test/planner/snap.test.ts`

- [ ] **Step 3: Implement**

```typescript
// tools/compositor/src/planner/snap.ts
import type { Scene } from "./types.js";

interface WordTiming { startMs: number; endMs: number; }

export function computePhraseBoundaries(words: WordTiming[], minGapMs: number): number[] {
  const out: number[] = [];
  for (let i = 0; i < words.length - 1; i++) {
    const gap = words[i + 1].startMs - words[i].endMs;
    if (gap > minGapMs) out.push(Math.round(words[i].endMs + gap / 2));
  }
  return out;
}

export function snapScenes(scenes: Scene[], phraseBoundaries: number[], toleranceMs: number): Scene[] {
  if (scenes.length === 0) return [];
  const sorted = [...phraseBoundaries].sort((a, b) => a - b);
  const out = scenes.map((s) => ({ ...s }));
  for (let i = 0; i < out.length - 1; i++) {
    const target = out[i].endMs;
    const nearest = nearestBoundary(target, sorted);
    if (nearest !== null && Math.abs(nearest - target) <= toleranceMs &&
        nearest > out[i].startMs && nearest < out[i + 1].endMs) {
      out[i].endMs = nearest;
      out[i + 1].startMs = nearest;
    }
  }
  return out;
}

function nearestBoundary(target: number, sorted: number[]): number | null {
  if (sorted.length === 0) return null;
  let best = sorted[0]; let bestDist = Math.abs(target - best);
  for (let i = 1; i < sorted.length; i++) {
    const d = Math.abs(target - sorted[i]);
    if (d < bestDist) { best = sorted[i]; bestDist = d; }
  }
  return best;
}
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd tools/compositor && npx vitest run test/planner/snap.test.ts`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/planner/snap.ts \
        tools/compositor/test/planner/snap.test.ts
git commit -m "feat(planner): deterministic phrase-boundary snap pass"
```

---

# Phase B — LLM-driven (segmenter, decorator)

LLM-driven tasks reuse the subagent-dispatch primitive from `tools/scripts/run-stage1.sh:159` (EDL author). Tests use a recorded-fixture stub to keep them deterministic and free of network dependencies.

### Task 6: Segmenter prompts

**Files:**
- Create: `tools/compositor/src/planner/prompts/segmenter-beats.md`.
- Create: `tools/compositor/src/planner/prompts/segmenter-scenes.md`.

- [ ] **Step 1: Write `segmenter-beats.md`**

```markdown
# Segmenter — Beat Pass

You are a video editor's planning assistant. Read the script and identify **narrative beats** — typically 4 to 8 for a 60-second episode. Each beat is one coherent thought.

## Inputs

### Script
{{SCRIPT}}

### Master timeline metadata
- Total duration: {{MASTER_DURATION_MS}} ms

### Transcript preview (first 100 words for context)
{{TRANSCRIPT_PREVIEW}}

### Vocabulary
- `narrative_position`: opening, setup, main, topic_change, climax, wind_down, outro
- `energy_hint`: calm, medium, high
- `mood_hint` (optional): warm, cold, editorial, tech, tense, playful, dramatic, premium, retro

## Output

Return a JSON array, no prose. Each object:
```json
{
  "beat_id": "B1",
  "beat_summary": "Host introduces the topic",
  "narrative_position": "opening",
  "energy_hint": "medium",
  "mood_hint": null,
  "script_start_offset": 0,
  "script_end_offset": 124
}
```

`script_start_offset` and `script_end_offset` are character offsets into the script string. Beats are non-overlapping, cover the full script, sequential IDs `B1`, `B2`, ...

If the script is short (one minute), 4–6 beats is right. Don't pad with redundant beats.
```

- [ ] **Step 2: Write `segmenter-scenes.md`**

```markdown
# Segmenter — Scene Pass

The beat below is longer than the 5-second hard cap. Subdivide it into N sub-scenes ≤ 5 s each.

## Inputs

### Beat metadata
{{BEAT_JSON}}

### Beat script chunk
{{SCRIPT_CHUNK}}

### Beat duration
{{BEAT_DURATION_MS}} ms (target ceil(duration/5000) sub-scenes)

## Output

Return a JSON array, no prose. Each object:
```json
{
  "key_phrase": "DRM is a moving target",
  "script_chunk": "...verbatim slice...",
  "char_offset_start": 0,
  "char_offset_end": 47
}
```

`key_phrase`: 5–8 words, the visual hook. Not a summary — the most quotable line.

`char_offset_start` / `char_offset_end`: offsets into the parent beat's script chunk. Sub-scenes are sequential, cover the full beat.

Inherit `narrative_position`, `energy_hint`, `mood_hint`, `beat_id` from the parent beat.
```

- [ ] **Step 3: Commit**

```bash
git add tools/compositor/src/planner/prompts/segmenter-beats.md \
        tools/compositor/src/planner/prompts/segmenter-scenes.md
git commit -m "feat(planner): segmenter prompts (beat pass + scene pass)"
```

---

### Task 7: Segmenter dispatcher — `planner/segmenter.ts`

**Files:**
- Create: `tools/compositor/src/planner/segmenter.ts`.
- Create: `tools/compositor/test/planner/segmenter.test.ts`.

- [ ] **Step 1: Implement**

```typescript
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
    if (beats[i].endMs <= beats[i].startMs) throw new Error(`beat ${beats[i].beatId}: end ≤ start`);
    if (i > 0 && beats[i].startMs < beats[i - 1].endMs) throw new Error(`beats overlap at ${i}`);
  }
}

function wordTimeAt(script: string, words: WordTiming[], charOff: number, side: "start" | "end"): number {
  if (script.length === 0 || words.length === 0) return 0;
  const frac = Math.max(0, Math.min(1, charOff / script.length));
  const idx = Math.min(words.length - 1, Math.floor(frac * words.length));
  return side === "start" ? words[idx].startMs : words[idx].endMs;
}

function isNarrative(v: string): v is NarrativePosition {
  return ["opening", "setup", "main", "topic_change", "climax", "wind_down", "outro"].includes(v);
}
function isEnergy(v: string): v is EnergyHint { return ["calm", "medium", "high"].includes(v); }
function isMood(v: string): v is MoodHint {
  return ["warm", "cold", "editorial", "tech", "tense", "playful", "dramatic", "premium", "retro"].includes(v);
}
```

- [ ] **Step 2: Write recorded-fixture test**

```typescript
// tools/compositor/test/planner/segmenter.test.ts
import { describe, it, expect } from "vitest";
import { segment, type SubagentDispatcher } from "../../src/planner/segmenter.js";

const SCRIPT = `Hello today the topic is DRM. There are three approaches that ship in the wild. Each one breaks differently. Let me show you why.`;
const WORDS = SCRIPT.split(/\s+/).map((text, i) => ({
  startMs: i * 250, endMs: i * 250 + 200, text,
}));

const RESPONSE = JSON.stringify([
  { beat_id: "B1", beat_summary: "Intro", narrative_position: "opening",
    energy_hint: "medium", mood_hint: null, script_start_offset: 0, script_end_offset: 30 },
  { beat_id: "B2", beat_summary: "Three approaches", narrative_position: "main",
    energy_hint: "medium", mood_hint: null, script_start_offset: 30, script_end_offset: SCRIPT.length },
]);

class StubDispatcher implements SubagentDispatcher {
  constructor(private responses: string[]) {}
  async run(_p: string): Promise<string> {
    const r = this.responses.shift();
    if (!r) throw new Error("stub exhausted");
    return r;
  }
}

describe("segmenter", () => {
  it("produces scenes from a recorded beat-pass response", async () => {
    const d = new StubDispatcher([RESPONSE]);
    const scenes = await segment({
      script: SCRIPT, words: WORDS, masterDurationMs: WORDS.at(-1)!.endMs, dispatcher: d,
    });
    expect(scenes.length).toBeGreaterThanOrEqual(2);
    expect(scenes[0].beatId).toBe("B1");
    expect(scenes[0].narrativePosition).toBe("opening");
  });

  it("retries on invalid JSON, then succeeds", async () => {
    const d = new StubDispatcher(["not json", RESPONSE]);
    const scenes = await segment({
      script: SCRIPT, words: WORDS, masterDurationMs: WORDS.at(-1)!.endMs,
      dispatcher: d, maxRetries: 2,
    });
    expect(scenes.length).toBeGreaterThanOrEqual(2);
  });

  it("aborts after maxRetries with all-invalid responses", async () => {
    const d = new StubDispatcher(["not json", "bad", "[]"]);
    await expect(segment({
      script: SCRIPT, words: WORDS, masterDurationMs: WORDS.at(-1)!.endMs,
      dispatcher: d, maxRetries: 2,
    })).rejects.toThrow();
  });
});
```

- [ ] **Step 3: Run tests, verify pass**

Run: `cd tools/compositor && npx vitest run test/planner/segmenter.test.ts`
Expected: 3 tests pass.

- [ ] **Step 4: Commit**

```bash
git add tools/compositor/src/planner/segmenter.ts \
        tools/compositor/test/planner/segmenter.test.ts
git commit -m "feat(planner): segmenter dispatcher with retry + recorded-fixture tests"
```

---

### Task 8: Decorator prompt — `planner/prompts/decorator.md`

**Files:**
- Create: `tools/compositor/src/planner/prompts/decorator.md`.

- [ ] **Step 1: Write the prompt**

```markdown
# Decorator — Mode + Graphic

You receive a list of scenes (already segmented and snapped) plus the project's visual direction. Decide, for each scene, the `scene_mode` (when rules don't pin it) and the `graphic` (when the scene is not pure talking head).

## Inputs

### Scenes
{{SCENES_JSON}}

### `seamsInsideScene` per scene index
{{SEAMS_INSIDE_JSON}}

### Project DESIGN.md (Style Prompt + What NOT to Do)
{{DESIGN_PROMPT}}

### `standards/motion-graphics.md` Catalog
{{CATALOG_TABLE}}

### Hard rules pre-applied
The dispatcher pre-narrowed `mode` candidates per scene to those allowed by hard rules. Where pre-narrow yielded one candidate, you must use it; only choose when multiple candidates remain.

## Output

Return a JSON array, no prose:

```json
{
  "scene_index": 0,
  "mode": "split",
  "graphic": {
    "source": "generative",
    "brief": "1–2 paragraph brief...",
    "data": { "items": ["A", "B", "C"] }
  }
}
```

`graphic.source`: `"none"` | `"catalog/<name>"` | `"generative"`. `<name>` must be from the catalog table. For `mode == "head"`, `graphic.source` must be `"none"`.

For `generative`, the brief names: layout (split-frame? overlay-plate? full broll?), entrance choreography (stagger, eases, durations), decorative elements (frosted glass surface? hairline rules? glow?), and data anchor (numbers, list items, quote).

**Same-graphic prohibition.** If the previous scene had the same mode (split→split or broll→broll), your `brief` must be visibly distinct from the previous scene's brief.
```

- [ ] **Step 2: Commit**

```bash
git add tools/compositor/src/planner/prompts/decorator.md
git commit -m "feat(planner): decorator prompt template"
```

---

### Task 9: Decorator dispatcher — `planner/decorator.ts`

**Files:**
- Create: `tools/compositor/src/planner/decorator.ts`.
- Create: `tools/compositor/test/planner/decorator.test.ts`.

- [ ] **Step 1: Implement**

```typescript
// tools/compositor/src/planner/decorator.ts
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { Scene, EnrichedScene, GraphicSource } from "./types.js";
import type { SceneMode } from "../sceneMode.js";
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
```

- [ ] **Step 2: Write integration test**

```typescript
// tools/compositor/test/planner/decorator.test.ts
import { describe, it, expect } from "vitest";
import { decorate } from "../../src/planner/decorator.js";
import type { Scene } from "../../src/planner/types.js";
import type { SubagentDispatcher } from "../../src/planner/segmenter.js";

class Stub implements SubagentDispatcher {
  constructor(private r: string) {}
  async run(_p: string): Promise<string> { return this.r; }
}

const SCENES: Scene[] = [
  { startMs: 0, endMs: 4000, beatId: "B1", narrativePosition: "opening", energyHint: "medium",
    keyPhrase: "intro", scriptChunk: "Hello, today..." },
  { startMs: 4000, endMs: 8000, beatId: "B2", narrativePosition: "main", energyHint: "medium",
    keyPhrase: "three approaches", scriptChunk: "Three ways..." },
];

const RESPONSE = JSON.stringify([
  { scene_index: 0, mode: "head", graphic: { source: "none" } },
  { scene_index: 1, mode: "split", graphic: { source: "generative", brief: "side panel" } },
]);

describe("decorator", () => {
  it("returns enriched scenes with mode + transition + graphic", async () => {
    const d = new Stub(RESPONSE);
    const enriched = await decorate({
      scenes: SCENES, seamsInsideByScene: new Map(),
      designMd: "calm frosted-glass", catalogTable: "(test)",
      projectPrimaryTransition: "crossfade", dispatcher: d,
    });
    expect(enriched).toHaveLength(2);
    expect(enriched[0].mode).toBe("head");
    expect(enriched[1].mode).toBe("split");
    expect(enriched[0].transitionOut).toBe("crossfade");
  });

  it("rejects decorator output outside the candidate set", async () => {
    const scenes: Scene[] = [{
      startMs: 0, endMs: 4000, beatId: "B1", narrativePosition: "outro", energyHint: "calm",
      keyPhrase: "thanks", scriptChunk: "Thanks for watching",
    }];
    const d = new Stub(JSON.stringify([
      { scene_index: 0, mode: "head", graphic: { source: "none" } },
    ]));
    await expect(decorate({
      scenes, seamsInsideByScene: new Map(),
      designMd: "x", catalogTable: "x", projectPrimaryTransition: "crossfade", dispatcher: d,
    })).rejects.toThrow(/not in candidate set/);
  });
});
```

- [ ] **Step 3: Run tests, verify pass**

Run: `cd tools/compositor && npx vitest run test/planner/decorator.test.ts`
Expected: 2 tests pass.

- [ ] **Step 4: Commit**

```bash
git add tools/compositor/src/planner/decorator.ts \
        tools/compositor/test/planner/decorator.test.ts
git commit -m "feat(planner): decorator dispatcher with hard-rule pre-narrow + transition picker"
```

---

# Phase C — Integration

### Task 10: Generative dispatcher prompt

**Files:**
- Create: `tools/compositor/src/planner/prompts/generative.md`.

- [ ] **Step 1: Write the prompt**

```markdown
# Generative Sub-Composition

Write one HyperFrames-compliant sub-composition for the scene below.

## Inputs

### Scene
{{SCENE_JSON}}

### Neighbour context
{{NEIGHBOUR_JSON}}

### Project DESIGN.md
{{DESIGN_MD_PATH}}

### Project standards/motion-graphics.md
{{MOTION_GRAPHICS_PATH}}

### standards/bespoke-seams.md (canonical layout pattern)
{{BESPOKE_SEAMS_PATH}}

### HF skill
Use the `hyperframes` skill via the Skill tool. Read SKILL.md, then references/transitions.md and references/motion-principles.md.

### Output path
{{OUTPUT_PATH}}

## Contract

1. `<template>` wrapper with `id` matching the file stem.
2. `data-composition-id` matching the file stem.
3. Scoped styles, no `var(--…)` on captured elements (use literal hex/RGBA from project tokens).
4. GSAP timeline registered: `window.__timelines["<composition-id>"] = tl`.
5. Build / breathe / resolve scene phases (~0–30%, 30–70%, 70–100%).
6. Entrance animations on every visible element.
7. **No exit animations** unless this is the final scene (the dispatcher tells you via `is_final`).
8. All visual tokens from `hyperframes-tokens` JSON in DESIGN.md. No hardcoded colours.
9. Pass `npx hyperframes lint --strict-all`, `validate --strict-all`, `inspect --strict-all`.

If the scene mode is `split`, fill the right-side panel only. If `broll`, fill the full frame. If `overlay`, place in lower third unless brief says otherwise.

Same-graphic prohibition: if the previous scene's mode equalled this scene's mode and was non-`head`, the hero frame must be visibly distinct.

Write the file to `{{OUTPUT_PATH}}`. Output only "OK" on stdout.
```

- [ ] **Step 2: Commit**

```bash
git add tools/compositor/src/planner/prompts/generative.md
git commit -m "feat(planner): generative sub-composition prompt template"
```

---

### Task 11: Generative dispatcher — `planner/generativeDispatcher.ts`

**Files:**
- Create: `tools/compositor/src/planner/generativeDispatcher.ts`.

- [ ] **Step 1: Implement using `execFileSync` (no shell)**

```typescript
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
        execFileSync(hfBin, ["lint", projectRoot, "--strict-all"], { stdio: "pipe" });
        execFileSync(hfBin, ["validate", projectRoot, "--strict-all"], { stdio: "pipe" });
        execFileSync(hfBin, ["inspect", projectRoot, "--strict-all", "--json"], { stdio: "pipe" });
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
```

- [ ] **Step 2: Commit**

```bash
git add tools/compositor/src/planner/generativeDispatcher.ts
git commit -m "feat(planner): parallel generative sub-composition dispatcher with HF gate per scene"
```

---

### Task 12: Compositor extension — read enriched seam-plan

**Files:**
- Modify: `tools/compositor/src/composer.ts`.
- Modify: `tools/compositor/test/composer.test.ts` (extend).

**Why:** Spec Component 5. Compositor must (a) consume enriched seam-plan via `seamPlanFormat.parseSeamPlan`, (b) emit `data-composition-src` for catalog and generative graphics on every non-`head` scene.

- [ ] **Step 1: Identify the change point in `composer.ts`**

```bash
grep -n "renderSeamFragment\|seamPlanWriter\|seam-plan.md" tools/compositor/src/composer.ts | head -20
```

- [ ] **Step 2: Add a branch for the enriched parser**

In `tools/compositor/src/composer.ts`, replace the seam-plan loading section. The current code uses the legacy `seamPlanWriter.parseSeamPlan` (or similar). Add a try/fallback: try `parseSeamPlan` from `planner/seamPlanFormat.ts` first; if it throws, fall back to the legacy parser for the smoke fixture.

```typescript
import { parseSeamPlan as parseEnrichedPlan } from "./planner/seamPlanFormat.js";
import { readFileSync } from "node:fs";

function loadSeamPlan(seamPlanPath: string) {
  const text = readFileSync(seamPlanPath, "utf-8");
  try {
    return { kind: "enriched" as const, plan: parseEnrichedPlan(text) };
  } catch {
    return { kind: "legacy" as const, plan: legacyParse(text) };
  }
}
```

- [ ] **Step 3: Update `renderSeamFragment` for enriched scenes**

When `kind === "enriched"`, iterate `plan.scenes` and per scene:
- `graphic.kind === "none"` (head): emit no clip beyond what the existing pipeline already emits (talking-head + captions only).
- `graphic.kind === "catalog"`: emit
  ```html
  <div data-composition-id="{{name}}"
       data-composition-src="compositions/{{name}}.html"
       data-start="{{startMs / 1000}}"
       data-duration="{{(endMs - startMs) / 1000}}"
       data-track-index="3"></div>
  ```
- `graphic.kind === "generative"`: emit the same shape with `composition-id="scene-{{beatId}}-{{idx}}"` and `composition-src="compositions/scene-{{beatId}}-{{idx}}.html"`.

Match the existing template-string conventions in `composer.ts`; do not introduce new helpers.

- [ ] **Step 4: Add tests**

In `tools/compositor/test/composer.test.ts`, add three new test cases — emit-catalog-reference, emit-generative-reference, no-clip-for-head — using a small synthetic enriched `SeamPlan` and asserting on the output HTML string.

- [ ] **Step 5: Run all compositor tests**

Run: `cd tools/compositor && npx vitest run`
Expected: existing 76 tests still pass + 3 new tests pass.

- [ ] **Step 6: Commit**

```bash
git add tools/compositor/src/composer.ts tools/compositor/test/composer.test.ts
git commit -m "feat(compositor): emit catalog/generative graphic references from enriched seam-plan"
```

---

### Task 13: New `plan` and `generate` subcommands in `index.ts`

**Files:**
- Modify: `tools/compositor/src/index.ts`.

- [ ] **Step 1: Add `plan` subcommand**

In `tools/compositor/src/index.ts`, find the existing dispatch block (`if (cmd === "compose") { ... } else if (cmd === "seam-plan") { ... }`). Add:

```typescript
} else if (cmd === "plan") {
  const slug = path.basename(episodeDir);
  const bundle = JSON.parse(readFileSync(path.join(episodeDir, "master/bundle.json"), "utf-8"));
  const script = readFileSync(path.join(episodeDir, "source/script.txt"), "utf-8");
  const designMd = readFileSync(path.join(REPO_ROOT, "DESIGN.md"), "utf-8");
  const catalogTable = readFileSync(path.join(REPO_ROOT, "standards/motion-graphics.md"), "utf-8");
  const dispatcher = makeRealSubagentDispatcher();
  const scenes = await segment({
    script, words: bundle.transcript.words,
    masterDurationMs: bundle.master.durationMs, dispatcher,
  });
  const phraseBoundaries = computePhraseBoundaries(bundle.transcript.words, 150);
  const snapped = snapScenes(scenes, phraseBoundaries, 300);
  const edl = JSON.parse(readFileSync(path.join(episodeDir, "stage-1-cut/edl.json"), "utf-8"));
  const seamsInsideByScene = countSeamsPerScene(snapped, edl);
  const enriched = await decorate({
    scenes: snapped, seamsInsideByScene, designMd, catalogTable,
    projectPrimaryTransition: "crossfade", dispatcher,
  });
  const planMd = writeSeamPlan({ slug, masterDurationMs: bundle.master.durationMs, scenes: enriched });
  writeFileSync(seamPlanPath, planMd, "utf-8");
  console.log(`plan written: ${seamPlanPath}`);
}
```

The `countSeamsPerScene` helper:

```typescript
function countSeamsPerScene(scenes: Scene[], edl: any): Map<number, number> {
  const seamTimes: number[] = (edl.seams ?? []).map((x: any) => x.atMs);
  const out = new Map<number, number>();
  scenes.forEach((s, i) => {
    out.set(i, seamTimes.filter(t => t > s.startMs && t < s.endMs).length);
  });
  return out;
}
```

`makeRealSubagentDispatcher()` is repo-specific — it must reuse the same primitive `tools/scripts/run-stage1.sh` consumes for the EDL author. If that primitive isn't already exposed as a Node module, extract it into `tools/compositor/src/planner/realDispatcher.ts` as a thin wrapper before continuing this task.

- [ ] **Step 2: Add `generate` subcommand**

```typescript
} else if (cmd === "generate") {
  const planText = readFileSync(seamPlanPath, "utf-8");
  const plan = parseEnrichedSeamPlan(planText);
  const hfBin = path.join(REPO_ROOT, "tools/compositor/node_modules/.bin/hyperframes");
  const results = await generateAll({
    episodeDir, scenes: plan.scenes, hfBin,
    dispatcherFor: () => makeRealSubagentDispatcher(),
  });
  const failed = results.filter(r => !r.ok);
  if (failed.length > 0) {
    console.error("generative dispatch had failures:", failed);
    process.exit(1);
  }
  console.log(`generate: ${results.length} sub-compositions written`);
}
```

Add the imports: `parseSeamPlan as parseEnrichedSeamPlan, writeSeamPlan` from `./planner/seamPlanFormat.js`; `segment` from `./planner/segmenter.js`; `decorate` from `./planner/decorator.js`; `computePhraseBoundaries, snapScenes` from `./planner/snap.js`; `generateAll` from `./planner/generativeDispatcher.js`; `Scene` from `./planner/types.js`.

- [ ] **Step 3: Compile**

Run: `cd tools/compositor && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add tools/compositor/src/index.ts
git commit -m "feat(compositor): add plan and generate subcommands"
```

---

### Task 14: Pipeline wrapper — `run-stage2-plan.sh`

**Files:**
- Create: `tools/scripts/run-stage2-plan.sh`.

- [ ] **Step 1: Write the wrapper**

```bash
#!/usr/bin/env bash
# Stage 2a: produce enriched seam-plan.md from script.txt + transcript bundle + EDL.
# Output: episodes/<slug>/stage-2-composite/seam-plan.md
# Stops at CP2.5 implicitly — host reviews / edits before run-stage2-generate.
set -euo pipefail

if [ "$#" -ne 1 ]; then echo "Usage: $0 <slug>"; exit 1; fi
SLUG="$1"
REPO_ROOT="$(pwd)"
EP="$REPO_ROOT/episodes/$SLUG"
[ -d "$EP" ] || { echo "ERROR: episode dir missing: $EP"; exit 1; }
[ -f "$EP/master/bundle.json" ] || { echo "ERROR: master/bundle.json missing"; exit 1; }
[ -f "$EP/source/script.txt" ] || { echo "ERROR: source/script.txt required for planner"; exit 1; }
[ -f "$EP/stage-1-cut/edl.json" ] || { echo "ERROR: stage-1-cut/edl.json missing"; exit 1; }

# shellcheck source=tools/scripts/lib/preflight.sh
. "$(dirname "$0")/lib/preflight.sh"
hf_preflight || { echo "ERROR: doctor preflight failed; aborting plan"; exit 1; }

TSX_BIN="$REPO_ROOT/tools/compositor/node_modules/.bin/tsx"
[ -x "$TSX_BIN" ] || { echo "ERROR: tsx not found — run 'cd tools/compositor && npm install'"; exit 1; }

REPO_ROOT="$REPO_ROOT" "$TSX_BIN" "$REPO_ROOT/tools/compositor/src/index.ts" plan --episode "$EP"

echo "CP2.5 ready: $EP/stage-2-composite/seam-plan.md. Awaiting review."
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x tools/scripts/run-stage2-plan.sh
```

- [ ] **Step 3: Commit**

```bash
git add tools/scripts/run-stage2-plan.sh
git commit -m "feat(scripts): run-stage2-plan.sh produces enriched seam-plan.md (CP2.5)"
```

---

### Task 15: Pipeline wrapper — `run-stage2-generate.sh`

**Files:**
- Create: `tools/scripts/run-stage2-generate.sh`.

- [ ] **Step 1: Write the wrapper**

```bash
#!/usr/bin/env bash
# Stage 2b: read enriched seam-plan.md and dispatch parallel generative subagents.
set -euo pipefail

if [ "$#" -ne 1 ]; then echo "Usage: $0 <slug>"; exit 1; fi
SLUG="$1"
REPO_ROOT="$(pwd)"
EP="$REPO_ROOT/episodes/$SLUG"
PLAN="$EP/stage-2-composite/seam-plan.md"
[ -f "$PLAN" ] || { echo "ERROR: $PLAN missing — run run-stage2-plan.sh first"; exit 1; }

grep -q "^## Scene " "$PLAN" || { echo "ERROR: $PLAN is not in enriched format"; exit 1; }

# shellcheck source=tools/scripts/lib/preflight.sh
. "$(dirname "$0")/lib/preflight.sh"
hf_preflight || { echo "ERROR: doctor preflight failed"; exit 1; }

TSX_BIN="$REPO_ROOT/tools/compositor/node_modules/.bin/tsx"
[ -x "$TSX_BIN" ] || { echo "ERROR: tsx not found — run 'cd tools/compositor && npm install'"; exit 1; }

REPO_ROOT="$REPO_ROOT" "$TSX_BIN" "$REPO_ROOT/tools/compositor/src/index.ts" generate --episode "$EP"

echo "Generated sub-compositions in $EP/stage-2-composite/compositions/. Run run-stage2-compose.sh next."
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x tools/scripts/run-stage2-generate.sh
```

- [ ] **Step 3: Commit**

```bash
git add tools/scripts/run-stage2-generate.sh
git commit -m "feat(scripts): run-stage2-generate.sh dispatches parallel generative subagents"
```

---

# Phase D — End-to-end fixture

### Task 16: Integration fixture exercising every rule branch

**Files:**
- Create: `tools/compositor/test/planner/fixtures/integration/script.txt`.
- Create: `tools/compositor/test/planner/fixtures/integration/expected-seam-plan.md`.
- Create: `tools/compositor/test/planner/integration.test.ts`.

- [ ] **Step 1: Author the fixture script**

Create `tools/compositor/test/planner/fixtures/integration/script.txt`:

```
Hello today the topic is desktop software licensing. There are three approaches that ship in the wild. First approach: online check. Second approach: hardware key. Third approach: time-based expiry. Each one breaks differently. Like this. And like this. And finally this. Thanks for watching, please subscribe.
```

- [ ] **Step 2: Author the expected enriched seam-plan**

Create `tools/compositor/test/planner/fixtures/integration/expected-seam-plan.md` with at least 8 scenes covering: opening (head), setup (split), three main scenes (broll with three different briefs to exercise different-brief constraint on rule 5), climax (overlay), wind-down (head), outro (overlay+subscribe-cta). Use the format from Task 2.

The fixture is hand-authored because we want it to read like a finished editorial plan — the test asserts the deterministic foundation can verify it. (LLM-generated fixtures would couple this test to LLM determinism.)

- [ ] **Step 3: Write the integration test**

```typescript
// tools/compositor/test/planner/integration.test.ts
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseSeamPlan, writeSeamPlan } from "../../src/planner/seamPlanFormat.js";
import { validateSeamPlan } from "../../src/planner/modeValidator.js";

const FIXTURE_DIR = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "fixtures/integration",
);

function readPlan() {
  return parseSeamPlan(readFileSync(path.join(FIXTURE_DIR, "expected-seam-plan.md"), "utf-8"));
}

describe("planner integration fixture", () => {
  it("the expected seam-plan parses and passes the validator", () => {
    const plan = readPlan();
    expect(plan.scenes.length).toBeGreaterThanOrEqual(8);
    expect(() => validateSeamPlan(plan, new Map())).not.toThrow();
  });

  it("round-trips parse → write → parse identically", () => {
    const plan = readPlan();
    expect(parseSeamPlan(writeSeamPlan(plan))).toEqual(plan);
  });

  it("contains at least three same-mode scenes with distinct briefs", () => {
    const plan = readPlan();
    const broll = plan.scenes.filter(s => s.mode === "broll" && s.graphic.kind === "generative");
    expect(broll.length).toBeGreaterThanOrEqual(3);
    const briefs = new Set(broll.map(s => (s.graphic as any).brief.trim()));
    expect(briefs.size).toBe(broll.length);
  });

  it("ends with outro = overlay + catalog/subscribe-cta", () => {
    const plan = readPlan();
    const last = plan.scenes.at(-1)!;
    expect(last.narrativePosition).toBe("outro");
    expect(last.mode).toBe("overlay");
    expect(last.graphic.kind).toBe("catalog");
    if (last.graphic.kind === "catalog") expect(last.graphic.name).toBe("subscribe-cta");
  });
});
```

- [ ] **Step 4: Iterate the fixture until tests pass**

Run: `cd tools/compositor && npx vitest run test/planner/integration.test.ts`

Adjust `expected-seam-plan.md` until all four tests pass. Common failures: scene durations exceeding 5 s; missing `script:` block; wrong `narrative_position`; outro not having `subscribe-cta`.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/test/planner/fixtures \
        tools/compositor/test/planner/integration.test.ts
git commit -m "test(planner): integration fixture covering every rule branch"
```

---

## Self-review

**Spec coverage:**
- Component 1 (Segmenter, hierarchical) → Tasks 6, 7 ✓
- Component 2 (Snap pass) → Task 5 ✓
- Component 3 (Decorator) → Tasks 8, 9 ✓
- Component 4 (Generative dispatcher) → Tasks 10, 11 ✓
- Component 5 (Compositor extension) → Task 12 ✓
- Enriched seam-plan schema → Task 2 ✓
- Mode validator (hard rules) → Task 3 ✓
- Transition picker → Task 4 ✓
- Pipeline scripts → Tasks 14, 15 ✓
- New `plan` and `generate` subcommands → Task 13 ✓
- Integration fixture exercising every rule branch → Task 16 ✓
- Types module → Task 1 ✓

**Placeholders:** Task 12 step 2 says "adapt to the actual surrounding code" because `composer.ts` internals are not fully reproduced here; the engineer will read the file in step 1 and apply the patch in the existing style. Task 16 step 2 explicitly leaves the fixture hand-authored as a deliverable. Both are deliberate; not unfinished plan steps.

**Type/name consistency:**
- `SceneMode`, `NarrativePosition`, `EnergyHint`, `MoodHint` defined in Task 1, used in Tasks 2, 3, 4, 5, 7, 9, 11.
- `parseSeamPlan` / `writeSeamPlan` exported from Task 2; consumed by Tasks 12, 13, 16.
- `SubagentDispatcher` defined in Task 7; consumed by Tasks 9, 11.
- `pickTransition` / `TransitionPickerState` exported from Task 4; consumed by Task 9.
- `validateSeamPlan` exported from Task 3; consumed by Task 16.
- `execFileSync` (no shell, array args) used in Task 11 per security guidance.

**Open notes for the executing engineer:**
- `makeRealSubagentDispatcher()` (Task 13) is repo-specific. Reuse the primitive `tools/scripts/run-stage1.sh:159` consumes; if that primitive isn't a Node module already, extract it into `tools/compositor/src/planner/realDispatcher.ts` first.
- The character-offset → word-time alignment in Task 7's `wordTimeAt` is a linear approximation. If integration testing on real episodes shows scene boundaries drifting by > 200 ms from intended, replace with `tools/scripts/script_diff/align.py` proper alignment.
- The legacy seam-plan parser fallback in Task 12 keeps the smoke fixture working during the transition; once the smoke fixture is upgraded to the enriched format, the fallback can be deleted.
