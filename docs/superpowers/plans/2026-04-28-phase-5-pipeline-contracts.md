# Phase 5 — Pipeline Contracts Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Stage 1 emit a single typed master-aligned `bundle.json`, and refactor Stage 2 to read it via a typed loader. Rename the `full` scene mode to `broll` everywhere in code. Produce a Phase 6 brief for the agentic graphics planner.

**Architecture:** Bundle generated in TypeScript (reuses existing `remapWordsToMaster` + `loadEdl`), written as the last step of Stage 1. A new compositor subcommand `write-bundle` is invoked from `run-stage1.sh` after `_render_edl.py`. Stage 2 reads the bundle through a typed loader and stops reading `transcript.json` / `cut-list.md`. Scene-mode rename is locked behind a `parseSceneMode` parser that rejects the legacy `full`.

**Tech Stack:** TypeScript (Node 20+, vitest), bash scripts orchestrating Python EDL renderer + TS bundle writer, ffprobe (already available via ffmpeg).

**Prerequisite:** Phase 4 complete (`phase-4-first-episode` tag at `f9ccca4`). Spec at `docs/superpowers/specs/2026-04-28-phase-5-pipeline-contracts-design.md`. The pilot episode `2026-04-27-desktop-software-licensing-it-turns-out` is frozen and not migrated.

---

## File structure produced by this phase

```
docs/superpowers/specs/2026-04-28-agentic-graphics-planner-brief.md   (new — Task 1)

tools/compositor/src/sceneMode.ts                                     (new — Task 2)
tools/compositor/src/types.ts                                         (modified — Tasks 2, 4)
tools/compositor/src/seamPlanner.ts                                   (modified — Task 3)
tools/compositor/src/seamPlanWriter.ts                                (modified — Task 3)
tools/compositor/test/sceneMode.test.ts                               (new — Task 2)
tools/compositor/test/seamPlanner.test.ts                             (modified — Task 3)
tools/compositor/test/seamPlanWriter.test.ts                          (modified — Task 3)
tools/compositor/test/composer.test.ts                                (modified — Tasks 3, 8)

tools/compositor/src/stage1/writeBundle.ts                            (new — Task 5)
tools/compositor/test/writeBundle.test.ts                             (new — Task 5)
tools/compositor/test/fixtures/edl.sample.json                        (new — Task 5)

tools/compositor/src/stage2/loadBundle.ts                             (new — Task 6)
tools/compositor/test/loadBundle.test.ts                              (new — Task 6)
tools/compositor/test/fixtures/bundle.sample.json                     (new — Task 6)

tools/compositor/src/index.ts                                         (modified — Tasks 7, 8)
tools/compositor/src/composer.ts                                      (modified — Task 8)

tools/scripts/run-stage1.sh                                           (modified — Task 7)
tools/scripts/test/test-run-stage1.sh                                 (modified — Task 7)
tools/scripts/test/test-run-stage2.sh                                 (modified — Task 8)
```

---

## Task 1: Phase 6 brief — message-in-a-bottle for the agentic planner

**Files:**
- Create: `docs/superpowers/specs/2026-04-28-agentic-graphics-planner-brief.md`

This is documentation-only; no tests. Brief is input to a future brainstorming session, not a spec. Keep it under ~2 pages.

- [ ] **Step 1: Write the brief**

Create `docs/superpowers/specs/2026-04-28-agentic-graphics-planner-brief.md` with the content below (markdown):

> # Agentic Graphics Planner — Brief
>
> **Status:** brief, not a spec. Input to a future Phase 6 brainstorming session.
> **Date:** 2026-04-28
> **Source:** Phase 4 retro (macro-retro item 1) + Phase 5 design context.
>
> ## Motivation
>
> Without a planner, scene modes (`split` / `broll` / `overlay`) are silent decorative labels: `composer.ts` `renderSeamFragment` only emits visible content when a seam carries `{component, data}`. The pilot episode shipped with no graphics — talking-head + captions only — and was deliberately not published because of this. The compositor is a renderer; the system was designed around a planner that does not yet exist.
>
> ## Decision: agentic, not LLM API
>
> The planner will dispatch coding subagents in-pipeline (one per seam, or batched), not call an LLM API. Reasoning:
> - A coding subagent reads the standards, the seam transcript, the component catalog with data shapes, and writes the `graphic:` / `data:` lines directly into `seam-plan.md`. Same trust model as the existing EDL subagent at `run-stage1.sh:159`.
> - LLM API would require its own prompt scaffolding, validation, retry, and contract glue — code we already have for subagents.
> - Subagents already inherit the repo's standards files as context, which is exactly what the planner needs.
>
> ## Inputs (per-seam)
>
> - Spoken text in the seam window (from `master/bundle.json` words filtered to `[seam.atMs, seam.endsAtMs]`).
> - Scene mode (`head` / `split` / `broll` / `overlay`).
> - `standards/motion-graphics.md` excerpt — the WATCH catalog + transition matrix + "Graphic specs are mandatory" section.
> - Component catalog: `design-system/components/*.html` plus a manifest of data shapes per component (does not yet exist; component manifest is a Phase 6 task).
> - Adjacent seams' scene modes (to enforce transition matrix locally).
>
> ## Outputs
>
> - `graphic: <component-name>` and `data: <json>` lines patched into the seam's entry in `seam-plan.md`.
> - One subagent invocation produces output for one seam (or for a batch); the orchestrator merges all outputs back into a single `seam-plan.md`.
>
> ## Validation layer
>
> Enforced at write time, not runtime:
> - Transition matrix from `standards/motion-graphics.md`.
> - `scene_mode → allowed_components` from the WATCH catalog.
> - Per-component data-shape conformance (component manifest defines the expected fields; planner output must match).
> - A `head` seam is allowed to have no graphic; any other mode without a graphic is a planner error.
>
> If a subagent's output fails validation, the orchestrator can retry with the violation message in the prompt.
>
> ## Dispatch model — open question
>
> Two shapes plausible:
> - **Per-seam:** N subagents in parallel, one per seam. Simple, no coordination, every seam decided in isolation.
> - **Batched:** one subagent per N seams (e.g. 3-4). Less startup overhead, the subagent sees a wider context and can balance graphic variety across the batch.
>
> Phase 6 brainstorming should pick one based on observed seam counts (pilot had 8) and cost.
>
> ## Other open questions for Phase 6
>
> - Retry policy on validation failure: max retries, prompt format for the retry, fallback to manual editing.
> - Cost estimate: subagent invocations per episode, expected wall time.
> - Ambiguous-seam handling: when the spoken text doesn't suggest an obvious graphic (e.g. transition phrases), what's the fallback?
> - How does the planner integrate with the host's CP2.5 review? Today the host edits `seam-plan.md` by hand; with a planner, the host reviews and edits planner output. The CP protocol stays the same.
> - Component manifest format: where does it live (`design-system/components/manifest.json`?), who maintains it, how is it kept in sync with component HTML.
>
> ## Pointers
>
> - `standards/motion-graphics.md` — canonical scene-mode names, transition matrix, "Graphic specs are mandatory" section, WATCH catalog `scene_mode → allowed_components`.
> - `standards/pipeline-contracts.md` — master-aligned bundle (created in Phase 5); the planner consumes seam transcripts from `master/bundle.json`.
> - `episodes/2026-04-27-desktop-software-licensing-it-turns-out/retro.md` — Macro-retro section, "Phase 5 candidate scope" item 1, "Scene modes are label-only without graphic specs" CP2.5 PROMOTE.
> - `standards/retro-changelog.md` — entries dated 2026-04-27 and 2026-04-28.
> - `tools/scripts/run-stage1.sh:159` — reference for subagent dispatch shape (current EDL author).
>
> ## What this brief is NOT
>
> - Not a spec. The next brainstorming session will produce the spec.
> - Not a commitment to a specific dispatch model, validation depth, or retry policy — those are open questions above.
> - Not bound to Phase 5's tag. Phase 6 is its own brainstorm → spec → plan → execute cycle.

(Strip the leading `> ` blockquote markers when writing the actual file — the markers above are only for embedding the file content inside this plan.)

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-04-28-agentic-graphics-planner-brief.md
git commit -m "docs(phase-6): brief for agentic graphics planner"
```

---

## Task 2: `parseSceneMode` — typed parser that rejects legacy `full`

**Files:**
- Create: `tools/compositor/src/sceneMode.ts`
- Create: `tools/compositor/test/sceneMode.test.ts`
- Modify: `tools/compositor/src/types.ts:1` — change union from `"full"` to `"broll"`

The new `SceneMode` union includes `'broll'` instead of `'full'`. `parseSceneMode` is the only place a string becomes a `SceneMode` and it MUST reject the legacy `'full'` with a clear message — that's the rename guard.

- [ ] **Step 1: Write the failing test**

Create `tools/compositor/test/sceneMode.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { parseSceneMode, SCENE_MODES } from "../src/sceneMode.js";

describe("parseSceneMode", () => {
  it("accepts each canonical name", () => {
    expect(parseSceneMode("head")).toBe("head");
    expect(parseSceneMode("split")).toBe("split");
    expect(parseSceneMode("broll")).toBe("broll");
    expect(parseSceneMode("overlay")).toBe("overlay");
  });

  it("rejects the legacy 'full' name explicitly", () => {
    expect(() => parseSceneMode("full")).toThrow(
      /'full' was renamed to 'broll'/,
    );
  });

  it("rejects unknown values with the offending value in the message", () => {
    expect(() => parseSceneMode("unknown")).toThrow(/unknown/);
    expect(() => parseSceneMode("")).toThrow();
  });

  it("exposes SCENE_MODES as a readonly tuple of all four names", () => {
    expect(SCENE_MODES).toEqual(["head", "split", "broll", "overlay"]);
  });
});
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd tools/compositor && npx vitest run test/sceneMode.test.ts
```

Expected: FAIL with "Cannot find module" (file does not exist).

- [ ] **Step 3: Write minimal implementation**

First update `tools/compositor/src/types.ts:1`:

```typescript
export type SceneMode = "head" | "split" | "broll" | "overlay";
```

Then create `tools/compositor/src/sceneMode.ts`:

```typescript
import type { SceneMode } from "./types.js";

export const SCENE_MODES = ["head", "split", "broll", "overlay"] as const;

export function parseSceneMode(value: string): SceneMode {
  if (value === "full") {
    throw new Error(
      "Scene mode 'full' was renamed to 'broll'. Update the source emitting this value.",
    );
  }
  if ((SCENE_MODES as readonly string[]).includes(value)) {
    return value as SceneMode;
  }
  throw new Error(
    `Unknown scene mode: ${JSON.stringify(value)}. Expected one of: ${SCENE_MODES.join(", ")}.`,
  );
}
```

- [ ] **Step 4: Run test, verify it passes**

```bash
cd tools/compositor && npx vitest run test/sceneMode.test.ts
```

Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/sceneMode.ts tools/compositor/src/types.ts tools/compositor/test/sceneMode.test.ts
git commit -m "feat(compositor): SceneMode parser rejects legacy 'full'"
```

---

## Task 3: Apply `full` → `broll` rename across compositor source and tests

**Files:**
- Modify: `tools/compositor/src/seamPlanner.ts:3,11,20,25`
- Modify: `tools/compositor/src/seamPlanWriter.ts:5` — use `parseSceneMode`
- Modify: `tools/compositor/test/seamPlanner.test.ts` — every `"full"` literal → `"broll"`
- Modify: `tools/compositor/test/seamPlanWriter.test.ts` — every `"full"` literal → `"broll"`
- Modify: `tools/compositor/test/composer.test.ts:31` — `scene: "full"` → `scene: "broll"`

- [ ] **Step 1: Run baseline test count**

```bash
cd tools/compositor && npx vitest run
```

Note the count of passing tests; expected post-task count is the same.

- [ ] **Step 2: Replace `seamPlanner.ts`**

Write to `tools/compositor/src/seamPlanner.ts`:

```typescript
import type { Seam, SceneMode } from "./types.js";

const ORDER: SceneMode[] = ["broll", "split", "head", "split", "broll", "overlay"];

const FORBIDDEN: ReadonlySet<string> = new Set([
  "head>head",
  "head>overlay",
  "overlay>head",
  "overlay>overlay",
  "split>split",
  "broll>broll",
]);

export function isAllowed(prev: SceneMode | null, next: SceneMode): boolean {
  if (prev === null) return true;
  return !FORBIDDEN.has(`${prev}>${next}`);
}

export function pickScene(index: number, prev: SceneMode | null): SceneMode {
  if (prev === null) return "broll";
  for (let offset = 0; offset < ORDER.length; offset++) {
    const candidate = ORDER[(index + offset) % ORDER.length];
    if (isAllowed(prev, candidate)) return candidate;
  }
  return "broll";
}

export function planSeams(at_ms_list: number[], master_duration_ms: number): Seam[] {
  const seams: Seam[] = [];
  let prev: SceneMode | null = null;
  for (let i = 0; i < at_ms_list.length; i++) {
    const scene = pickScene(i, prev);
    const ends_at_ms =
      i + 1 < at_ms_list.length ? at_ms_list[i + 1] : master_duration_ms;
    seams.push({ index: i, at_ms: at_ms_list[i], scene, ends_at_ms });
    prev = scene;
  }
  return seams;
}
```

- [ ] **Step 3: Replace `seamPlanWriter.ts` to use `parseSceneMode`**

Write to `tools/compositor/src/seamPlanWriter.ts`:

```typescript
import type { Seam, SeamPlan } from "./types.js";
import { parseSceneMode } from "./sceneMode.js";

const HEADER_RE = /^#\s*Seam plan:\s*(\S+)\s*\(duration=(\d+)ms\)\s*$/;
const SEAM_RE =
  /^SEAM\s+(\d+)\s+at_ms=(\d+)\s+scene:\s*(\S+)\s+ends_at_ms=(\d+)\s*$/;
const GRAPHIC_RE = /^\s+graphic:\s*(\S+)\s*$/;
const DATA_RE = /^\s+data:\s*(.+)$/;

export function writeSeamPlan(plan: SeamPlan): string {
  const lines: string[] = [];
  lines.push(`# Seam plan: ${plan.episode_slug} (duration=${plan.master_duration_ms}ms)`);
  lines.push("");
  for (const seam of plan.seams) {
    lines.push(
      `SEAM ${seam.index} at_ms=${seam.at_ms} scene: ${seam.scene} ends_at_ms=${seam.ends_at_ms}`,
    );
    if (seam.graphic) {
      lines.push(`  graphic: ${seam.graphic.component}`);
      lines.push(`  data: ${JSON.stringify(seam.graphic.data)}`);
    }
  }
  lines.push("");
  return lines.join("\n");
}

export function readSeamPlan(md: string): SeamPlan {
  const lines = md.split(/\r?\n/);
  let episode_slug = "";
  let master_duration_ms = 0;
  const seams: Seam[] = [];
  let current: Seam | null = null;

  for (const line of lines) {
    const headerMatch = HEADER_RE.exec(line);
    if (headerMatch) {
      episode_slug = headerMatch[1];
      master_duration_ms = Number(headerMatch[2]);
      continue;
    }
    const seamMatch = SEAM_RE.exec(line);
    if (seamMatch) {
      if (current) seams.push(current);
      current = {
        index: Number(seamMatch[1]),
        at_ms: Number(seamMatch[2]),
        scene: parseSceneMode(seamMatch[3]),
        ends_at_ms: Number(seamMatch[4]),
      };
      continue;
    }
    const graphicMatch = GRAPHIC_RE.exec(line);
    if (graphicMatch && current) {
      current.graphic = {
        component: graphicMatch[1],
        data: current.graphic?.data ?? {},
      };
      continue;
    }
    const dataMatch = DATA_RE.exec(line);
    if (dataMatch && current) {
      const parsed = JSON.parse(dataMatch[1]) as Record<string, unknown>;
      if (current.graphic) {
        current.graphic.data = parsed;
      } else {
        current.graphic = { component: "", data: parsed };
      }
      continue;
    }
  }
  if (current) seams.push(current);
  return { episode_slug, master_duration_ms, seams };
}
```

- [ ] **Step 4: Update test files**

In `tools/compositor/test/seamPlanner.test.ts`, replace every literal `"full"` with `"broll"` and adjust test names that say "full scene" to "broll scene", and `"full>full"` → `"broll>broll"`.

In `tools/compositor/test/seamPlanWriter.test.ts`, replace every literal `"full"` with `"broll"` and update `expect(md).toContain("scene: full")` to `expect(md).toContain("scene: broll")`.

In `tools/compositor/test/composer.test.ts:31`, change `scene: "full"` to `scene: "broll"`.

- [ ] **Step 5: Run all compositor tests, verify pass**

```bash
cd tools/compositor && npx vitest run
```

Expected: same number of tests as Step 1 baseline, all PASS.

- [ ] **Step 6: Verify no `"full"` literal remains**

```bash
grep -nE '"full"' tools/compositor/src tools/compositor/test
```

Expected: zero matches.

- [ ] **Step 7: Commit**

```bash
git add tools/compositor/src/seamPlanner.ts tools/compositor/src/seamPlanWriter.ts tools/compositor/test/seamPlanner.test.ts tools/compositor/test/seamPlanWriter.test.ts tools/compositor/test/composer.test.ts
git commit -m "refactor(compositor): rename scene-mode 'full' to 'broll'"
```

---

## Task 4: `MasterBundle` types

**Files:**
- Modify: `tools/compositor/src/types.ts` — append `MasterBundle` and supporting types

- [ ] **Step 1: Append types to `tools/compositor/src/types.ts`**

```typescript
export interface BundleMaster {
  durationMs: number;
  width: number;
  height: number;
  fps: number;
}

export type BoundaryKind = "start" | "seam" | "end";

export interface BundleBoundary {
  atMs: number;
  kind: BoundaryKind;
}

export interface BundleWord {
  text: string;
  startMs: number;
  endMs: number;
}

export interface BundleTranscript {
  language: string;
  words: BundleWord[];
}

export interface MasterBundle {
  schemaVersion: 1;
  slug: string;
  master: BundleMaster;
  boundaries: BundleBoundary[];
  transcript: BundleTranscript;
}
```

- [ ] **Step 2: Verify the project type-checks**

```bash
cd tools/compositor && npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 3: Commit**

```bash
git add tools/compositor/src/types.ts
git commit -m "feat(compositor): MasterBundle types"
```

---

## Task 5: Bundle writer — TDD

**Files:**
- Create: `tools/compositor/src/stage1/writeBundle.ts`
- Create: `tools/compositor/test/writeBundle.test.ts`
- Create: `tools/compositor/test/fixtures/edl.sample.json`

The writer takes paths to existing artifacts (raw transcript, EDL, master video) plus a slug, runs ffprobe for master metadata (or accepts an injected probe function for testability), runs `remapWordsToMaster` from `edl.ts`, computes boundaries from EDL cumulative offsets, and returns a `MasterBundle`. A separate `writeBundleFile()` writes the bundle to disk.

Boundaries derivation:
- Boundary 0: `{ atMs: 0, kind: "start" }`
- For each EDL range index `i` in `1..N-1`: `{ atMs: cumulativeMsThrough(i-1), kind: "seam" }`
- Final boundary: `{ atMs: master.durationMs, kind: "end" }`

(So an EDL with N ranges produces N+1 boundaries: 1 start, N-1 seams, 1 end.)

- [ ] **Step 1: Write the EDL fixture**

Create `tools/compositor/test/fixtures/edl.sample.json`:

```json
{
  "version": 1,
  "sources": { "raw": "raw.mp4" },
  "ranges": [
    { "source": "raw", "start": 0.0, "end": 1.5 },
    { "source": "raw", "start": 2.0, "end": 3.0 }
  ]
}
```

(Total master duration: 1.5 + 1.0 = 2.5s = 2500ms. Boundaries: 0, 1500, 2500.)

- [ ] **Step 2: Write the failing test**

Create `tools/compositor/test/writeBundle.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildBundle } from "../src/stage1/writeBundle.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixtures = path.resolve(__dirname, "fixtures");

const fakeProbe = () => ({ durationMs: 2500, width: 1440, height: 2560, fps: 60 });

describe("buildBundle", () => {
  it("produces a master-aligned bundle from transcript + EDL + injected probe", () => {
    const bundle = buildBundle({
      slug: "demo",
      transcriptPath: path.join(fixtures, "transcript.sample.json"),
      edlPath: path.join(fixtures, "edl.sample.json"),
      masterPath: "/unused/master.mp4",
      probeMaster: fakeProbe,
    });
    expect(bundle.schemaVersion).toBe(1);
    expect(bundle.slug).toBe("demo");
    expect(bundle.master).toEqual({ durationMs: 2500, width: 1440, height: 2560, fps: 60 });
  });

  it("derives N+1 boundaries from N EDL ranges (start + N-1 seams + end)", () => {
    const bundle = buildBundle({
      slug: "demo",
      transcriptPath: path.join(fixtures, "transcript.sample.json"),
      edlPath: path.join(fixtures, "edl.sample.json"),
      masterPath: "/unused/master.mp4",
      probeMaster: fakeProbe,
    });
    expect(bundle.boundaries).toEqual([
      { atMs: 0, kind: "start" },
      { atMs: 1500, kind: "seam" },
      { atMs: 2500, kind: "end" },
    ]);
  });

  it("emits master-aligned word timings (raw -> master via EDL)", () => {
    const bundle = buildBundle({
      slug: "demo",
      transcriptPath: path.join(fixtures, "transcript.sample.json"),
      edlPath: path.join(fixtures, "edl.sample.json"),
      masterPath: "/unused/master.mp4",
      probeMaster: fakeProbe,
    });
    expect(bundle.transcript.words).toEqual([
      { text: "Hello", startMs: 0,    endMs: 350 },
      { text: "world", startMs: 380,  endMs: 720 },
      { text: "today", startMs: 1100, endMs: 1480 },
    ]);
  });

  it("uses 'en' as the default transcript language", () => {
    const bundle = buildBundle({
      slug: "demo",
      transcriptPath: path.join(fixtures, "transcript.sample.json"),
      edlPath: path.join(fixtures, "edl.sample.json"),
      masterPath: "/unused/master.mp4",
      probeMaster: fakeProbe,
    });
    expect(bundle.transcript.language).toBe("en");
  });
});
```

- [ ] **Step 3: Run, verify failure**

```bash
cd tools/compositor && npx vitest run test/writeBundle.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 4: Implement `writeBundle.ts`**

Create `tools/compositor/src/stage1/writeBundle.ts`. Use `spawnSync` (not `exec`) to invoke ffprobe so the call is shell-injection-free.

```typescript
import { writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { loadTranscript } from "../transcript.js";
import { loadEdl, remapWordsToMaster } from "../edl.js";
import type {
  BundleBoundary,
  BundleMaster,
  BundleWord,
  MasterBundle,
} from "../types.js";

export interface BuildBundleArgs {
  slug: string;
  transcriptPath: string;
  edlPath: string;
  masterPath: string;
  /** Injectable for tests; in production omit and ffprobe is invoked. */
  probeMaster?: (masterPath: string) => BundleMaster;
}

export function buildBundle(args: BuildBundleArgs): MasterBundle {
  const transcript = loadTranscript(args.transcriptPath);
  const edl = loadEdl(args.edlPath);
  const master = (args.probeMaster ?? probeMasterWithFfprobe)(args.masterPath);

  const boundaries: BundleBoundary[] = [{ atMs: 0, kind: "start" }];
  let acc = 0;
  for (let i = 0; i < edl.ranges.length - 1; i++) {
    acc += (edl.ranges[i].end - edl.ranges[i].start) * 1000;
    boundaries.push({ atMs: Math.round(acc), kind: "seam" });
  }
  boundaries.push({ atMs: master.durationMs, kind: "end" });

  const remapped = remapWordsToMaster(transcript.words, edl);
  const words: BundleWord[] = remapped.map((w) => ({
    text: w.text,
    startMs: w.start_ms,
    endMs: w.end_ms,
  }));

  return {
    schemaVersion: 1,
    slug: args.slug,
    master,
    boundaries,
    transcript: { language: "en", words },
  };
}

export function writeBundleFile(bundle: MasterBundle, outPath: string): void {
  writeFileSync(outPath, JSON.stringify(bundle, null, 2));
}

function probeMasterWithFfprobe(masterPath: string): BundleMaster {
  const res = spawnSync(
    "ffprobe",
    [
      "-v", "error",
      "-select_streams", "v:0",
      "-show_entries", "stream=width,height,r_frame_rate:format=duration",
      "-of", "json",
      masterPath,
    ],
    { encoding: "utf8" },
  );
  if (res.status !== 0) {
    throw new Error(`ffprobe failed for ${masterPath}: ${res.stderr}`);
  }
  const probed = JSON.parse(res.stdout) as {
    streams?: Array<{ width?: number; height?: number; r_frame_rate?: string }>;
    format?: { duration?: string };
  };
  const stream = probed.streams?.[0];
  if (!stream || stream.width === undefined || stream.height === undefined) {
    throw new Error(`ffprobe did not return width/height for ${masterPath}`);
  }
  const fpsParts = (stream.r_frame_rate ?? "60/1").split("/");
  const fps = Math.round(Number(fpsParts[0]) / Number(fpsParts[1] ?? "1"));
  const durationSec = Number(probed.format?.duration ?? "0");
  if (!durationSec) {
    throw new Error(`ffprobe did not return duration for ${masterPath}`);
  }
  return {
    durationMs: Math.round(durationSec * 1000),
    width: stream.width,
    height: stream.height,
    fps,
  };
}
```

- [ ] **Step 5: Run, verify pass**

```bash
cd tools/compositor && npx vitest run test/writeBundle.test.ts
```

Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add tools/compositor/src/stage1/writeBundle.ts tools/compositor/test/writeBundle.test.ts tools/compositor/test/fixtures/edl.sample.json
git commit -m "feat(compositor): Stage 1 bundle writer"
```

---

## Task 6: Bundle loader — TDD

**Files:**
- Create: `tools/compositor/src/stage2/loadBundle.ts`
- Create: `tools/compositor/test/loadBundle.test.ts`
- Create: `tools/compositor/test/fixtures/bundle.sample.json`

Hand-rolled discriminated-union parser. Tests cover the five drift classes.

- [ ] **Step 1: Write the bundle fixture**

Create `tools/compositor/test/fixtures/bundle.sample.json`:

```json
{
  "schemaVersion": 1,
  "slug": "demo",
  "master": { "durationMs": 2500, "width": 1440, "height": 2560, "fps": 60 },
  "boundaries": [
    { "atMs": 0, "kind": "start" },
    { "atMs": 1500, "kind": "seam" },
    { "atMs": 2500, "kind": "end" }
  ],
  "transcript": {
    "language": "en",
    "words": [
      { "text": "Hello", "startMs": 0, "endMs": 350 }
    ]
  }
}
```

- [ ] **Step 2: Write the failing test**

Create `tools/compositor/test/loadBundle.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { writeFileSync, mkdtempSync, mkdirSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadBundle, BundleSchemaError } from "../src/stage2/loadBundle.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixtures = path.resolve(__dirname, "fixtures");

function withBundleObject(obj: unknown): string {
  const dir = mkdtempSync(path.join(tmpdir(), "bundle-test-"));
  const masterDir = path.join(dir, "master");
  mkdirSync(masterDir, { recursive: true });
  writeFileSync(path.join(masterDir, "bundle.json"), JSON.stringify(obj));
  return dir;
}

describe("loadBundle", () => {
  it("loads a valid bundle from <episode>/master/bundle.json", () => {
    const validBundle = JSON.parse(
      readFileSync(path.join(fixtures, "bundle.sample.json"), "utf8"),
    );
    const dir = withBundleObject(validBundle);
    const bundle = loadBundle(dir);
    expect(bundle.slug).toBe("demo");
    expect(bundle.master.durationMs).toBe(2500);
    expect(bundle.transcript.words).toHaveLength(1);
  });

  it("rejects missing schemaVersion (drift class: schema versioning)", () => {
    const dir = withBundleObject({ slug: "x" });
    expect(() => loadBundle(dir)).toThrow(BundleSchemaError);
    expect(() => loadBundle(dir)).toThrow(/schemaVersion/);
  });

  it("rejects raw-timeline duration field (drift #1: audio_duration_secs)", () => {
    const bad = {
      schemaVersion: 1,
      slug: "x",
      master: { audio_duration_secs: 2.5, width: 1440, height: 2560, fps: 60 },
      boundaries: [],
      transcript: { language: "en", words: [] },
    };
    const dir = withBundleObject(bad);
    expect(() => loadBundle(dir)).toThrow(/master\.durationMs/);
  });

  it("rejects words with snake_case timings (drift #4: start/end vs startMs/endMs)", () => {
    const bad = {
      schemaVersion: 1,
      slug: "x",
      master: { durationMs: 2500, width: 1440, height: 2560, fps: 60 },
      boundaries: [
        { atMs: 0, kind: "start" },
        { atMs: 2500, kind: "end" },
      ],
      transcript: {
        language: "en",
        words: [{ text: "x", start_ms: 0, end_ms: 100 }],
      },
    };
    const dir = withBundleObject(bad);
    expect(() => loadBundle(dir)).toThrow(/transcript\.words\[0\]\.startMs/);
  });

  it("rejects boundary kind outside {start,seam,end}", () => {
    const bad = {
      schemaVersion: 1,
      slug: "x",
      master: { durationMs: 2500, width: 1440, height: 2560, fps: 60 },
      boundaries: [{ atMs: 0, kind: "begin" }, { atMs: 2500, kind: "end" }],
      transcript: { language: "en", words: [] },
    };
    const dir = withBundleObject(bad);
    expect(() => loadBundle(dir)).toThrow(/boundaries\[0\]\.kind/);
  });

  it("rejects last boundary not aligned to master.durationMs (drift #3)", () => {
    const bad = {
      schemaVersion: 1,
      slug: "x",
      master: { durationMs: 2500, width: 1440, height: 2560, fps: 60 },
      boundaries: [
        { atMs: 0, kind: "start" },
        { atMs: 9999, kind: "end" },
      ],
      transcript: { language: "en", words: [] },
    };
    const dir = withBundleObject(bad);
    expect(() => loadBundle(dir)).toThrow(/master\.durationMs/);
  });

  it("throws BundleSchemaError when the file is missing entirely", () => {
    const dir = mkdtempSync(path.join(tmpdir(), "bundle-test-empty-"));
    expect(() => loadBundle(dir)).toThrow(BundleSchemaError);
  });
});
```

- [ ] **Step 3: Run, verify failure**

```bash
cd tools/compositor && npx vitest run test/loadBundle.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 4: Implement `loadBundle.ts`**

Create `tools/compositor/src/stage2/loadBundle.ts`:

```typescript
import { readFileSync } from "node:fs";
import path from "node:path";
import type {
  BundleBoundary,
  BundleMaster,
  BundleWord,
  MasterBundle,
} from "../types.js";

export class BundleSchemaError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "BundleSchemaError";
  }
}

function fail(field: string, detail: string): never {
  throw new BundleSchemaError(`bundle.${field}: ${detail}`);
}

function ensureNumber(field: string, value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    fail(field, `expected finite number, got ${JSON.stringify(value)}`);
  }
  return value;
}

function ensureString(field: string, value: unknown): string {
  if (typeof value !== "string") {
    fail(field, `expected string, got ${JSON.stringify(value)}`);
  }
  return value;
}

function parseMaster(field: string, raw: unknown): BundleMaster {
  if (!raw || typeof raw !== "object") fail(field, "expected object");
  const obj = raw as Record<string, unknown>;
  return {
    durationMs: ensureNumber(`${field}.durationMs`, obj.durationMs),
    width: ensureNumber(`${field}.width`, obj.width),
    height: ensureNumber(`${field}.height`, obj.height),
    fps: ensureNumber(`${field}.fps`, obj.fps),
  };
}

function parseBoundary(field: string, raw: unknown): BundleBoundary {
  if (!raw || typeof raw !== "object") fail(field, "expected object");
  const obj = raw as Record<string, unknown>;
  const atMs = ensureNumber(`${field}.atMs`, obj.atMs);
  const kind = ensureString(`${field}.kind`, obj.kind);
  if (kind !== "start" && kind !== "seam" && kind !== "end") {
    fail(`${field}.kind`, `expected one of start|seam|end, got ${JSON.stringify(kind)}`);
  }
  return { atMs, kind };
}

function parseWord(field: string, raw: unknown): BundleWord {
  if (!raw || typeof raw !== "object") fail(field, "expected object");
  const obj = raw as Record<string, unknown>;
  return {
    text: ensureString(`${field}.text`, obj.text),
    startMs: ensureNumber(`${field}.startMs`, obj.startMs),
    endMs: ensureNumber(`${field}.endMs`, obj.endMs),
  };
}

export function loadBundle(episodeDir: string): MasterBundle {
  const bundlePath = path.join(episodeDir, "master", "bundle.json");
  let raw: string;
  try {
    raw = readFileSync(bundlePath, "utf8");
  } catch (e) {
    throw new BundleSchemaError(
      `bundle file missing at ${bundlePath}: ${(e as Error).message}`,
    );
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    throw new BundleSchemaError(
      `bundle JSON parse failed at ${bundlePath}: ${(e as Error).message}`,
    );
  }
  if (!parsed || typeof parsed !== "object") {
    throw new BundleSchemaError(`bundle: expected object, got ${typeof parsed}`);
  }
  const obj = parsed as Record<string, unknown>;
  if (obj.schemaVersion !== 1) {
    fail("schemaVersion", `expected 1, got ${JSON.stringify(obj.schemaVersion)}`);
  }
  const slug = ensureString("slug", obj.slug);
  const master = parseMaster("master", obj.master);

  if (!Array.isArray(obj.boundaries)) {
    fail("boundaries", "expected array");
  }
  const boundaries = (obj.boundaries as unknown[]).map((b, i) =>
    parseBoundary(`boundaries[${i}]`, b),
  );
  if (boundaries.length < 2) {
    fail("boundaries", `expected at least 2 (start + end), got ${boundaries.length}`);
  }
  if (boundaries[0].kind !== "start" || boundaries[0].atMs !== 0) {
    fail("boundaries[0]", "first boundary must be { atMs: 0, kind: 'start' }");
  }
  const last = boundaries[boundaries.length - 1];
  if (last.kind !== "end" || last.atMs !== master.durationMs) {
    fail(
      `boundaries[${boundaries.length - 1}]`,
      `last boundary must be 'end' at master.durationMs (${master.durationMs}), got kind=${last.kind} atMs=${last.atMs}`,
    );
  }

  const transcriptRaw = obj.transcript;
  if (!transcriptRaw || typeof transcriptRaw !== "object") {
    fail("transcript", "expected object");
  }
  const tObj = transcriptRaw as Record<string, unknown>;
  const language = ensureString("transcript.language", tObj.language);
  if (!Array.isArray(tObj.words)) {
    fail("transcript.words", "expected array");
  }
  const words = (tObj.words as unknown[]).map((w, i) =>
    parseWord(`transcript.words[${i}]`, w),
  );

  return {
    schemaVersion: 1,
    slug,
    master,
    boundaries,
    transcript: { language, words },
  };
}
```

- [ ] **Step 5: Run, verify pass**

```bash
cd tools/compositor && npx vitest run test/loadBundle.test.ts
```

Expected: PASS (7 tests).

- [ ] **Step 6: Commit**

```bash
git add tools/compositor/src/stage2/loadBundle.ts tools/compositor/test/loadBundle.test.ts tools/compositor/test/fixtures/bundle.sample.json
git commit -m "feat(compositor): Stage 2 bundle loader"
```

---

## Task 7: Wire bundle writer into Stage 1

**Files:**
- Modify: `tools/compositor/src/index.ts` — add `write-bundle` subcommand
- Modify: `tools/scripts/run-stage1.sh` — invoke `write-bundle` after `_render_edl.py` in render mode
- Modify: `tools/scripts/test/test-run-stage1.sh` — assert `master/bundle.json` exists

- [ ] **Step 1: Add `write-bundle` to `index.ts`**

In `tools/compositor/src/index.ts`, before the `if (cmd === "seam-plan") {` branch, add:

```typescript
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
  // ... existing branch (will be replaced in Task 8)
```

Update `usage()` to include `write-bundle`:

```typescript
function usage(): never {
  console.error("Usage: compositor <write-bundle|seam-plan|compose|render> --episode <path> [...]");
  process.exit(1);
}
```

Note: `index.ts` uses top-level await today (the existing branches are already inside `if/else` chain at the top level of the module). Since the file's `package.json` likely doesn't use ESM top-level await across all branches, ensure the branches stay structured as the existing `if / else if / else if / else` chain. The `await import(...)` inside is allowed in ESM.

- [ ] **Step 2: Wire into `run-stage1.sh` render mode**

In `tools/scripts/run-stage1.sh`, locate the render-mode block. Find these lines (around line 53-60):

```bash
  python "$SCRIPT_DIR/_render_edl.py" \
    --edl "$EDL" \
    --grade "$GRADE_JSON" \
    --output "$MASTER"

  echo
  echo "CP2 ready: $MASTER. Awaiting review."
```

Insert the bundle-write step BEFORE `echo "CP2 ready..."`:

```bash
  python "$SCRIPT_DIR/_render_edl.py" \
    --edl "$EDL" \
    --grade "$GRADE_JSON" \
    --output "$MASTER"

  # Generate the master-aligned bundle that Stage 2 consumes.
  ( cd "$REPO_ROOT/tools/compositor" && \
    REPO_ROOT="$REPO_ROOT" npx tsx src/index.ts write-bundle --episode "$EPISODE" )

  echo
  echo "CP2 ready: $MASTER. Awaiting review."
```

- [ ] **Step 3: Update `test-run-stage1.sh` to assert bundle exists**

Open `tools/scripts/test/test-run-stage1.sh` and find the assertions that check for `master.mp4`. Add immediately after them:

```bash
[ -f "$EP/master/bundle.json" ] || { echo "FAIL: master/bundle.json missing"; exit 1; }
node -e "
const b = JSON.parse(require('fs').readFileSync('$EP/master/bundle.json','utf8'));
if (b.schemaVersion !== 1) throw new Error('schemaVersion');
if (typeof b.master.durationMs !== 'number') throw new Error('master.durationMs');
if (!Array.isArray(b.boundaries) || b.boundaries.length < 2) throw new Error('boundaries');
if (!Array.isArray(b.transcript.words)) throw new Error('transcript.words');
" || { echo "FAIL: bundle.json shape invalid"; exit 1; }
```

- [ ] **Step 4: Run `test-run-stage1.sh`, verify pass**

```bash
tools/scripts/test/test-run-stage1.sh
```

Expected: PASS.

Then run the compositor unit tests:

```bash
cd tools/compositor && npx vitest run
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/index.ts tools/scripts/run-stage1.sh tools/scripts/test/test-run-stage1.sh
git commit -m "feat(stage1): write master/bundle.json at end of render"
```

---

## Task 8: Refactor Stage 2 to read bundle (rip out raw-transcript and cut-list parsing)

**Files:**
- Modify: `tools/compositor/src/index.ts` — `seam-plan` and `compose` branches read bundle
- Modify: `tools/compositor/src/composer.ts` — accept bundle, drop EDL/transcript params
- Modify: `tools/compositor/test/composer.test.ts` — pass bundle, not transcript+edl
- Modify: `tools/scripts/test/test-run-stage2.sh` — fixture writes `master/bundle.json` only

After this task, Stage 2 has zero reads of raw `transcript.json` and zero reads of `cut-list.md` for timing.

- [ ] **Step 1: Replace `composer.ts`**

Write to `tools/compositor/src/composer.ts`:

```typescript
import { writeFileSync } from "node:fs";
import path from "node:path";
import type { SeamPlan, Seam, MasterBundle } from "./types.js";
import { loadTokensCss } from "./tokens.js";
import { loadBaseCss, loadComponentTemplate, fillTemplate } from "./components.js";

export interface ComposeArgs {
  repoRoot: string;
  episodeDir: string;
  plan: SeamPlan;
  bundle: MasterBundle;
  masterRelPath: string;
}

const ROOT_WIDTH = 1440;
const ROOT_HEIGHT = 2560;
const CAPTION_TRACK_INDEX = 9;

function msToSeconds(ms: number): string {
  return (Math.round(ms) / 1000).toFixed(3);
}

function defaultTokensPath(repoRoot: string): string {
  return path.join(repoRoot, "design-system", "tokens", "tokens.json");
}

export function buildCompositionHtml(args: ComposeArgs): string {
  const css = loadTokensCss(defaultTokensPath(args.repoRoot));
  const base = loadBaseCss();

  const seamsWithGraphics = args.plan.seams.filter((s) => s.graphic);
  const seamFragments = seamsWithGraphics.map((seam, i) =>
    renderSeamFragment(seam, i + 1),
  );

  const captionTpl = loadComponentTemplate("caption-karaoke");
  // Words are already master-aligned in the bundle. Caption components
  // consume start_ms/end_ms (snake_case); convert from camelCase here at
  // the component boundary.
  const wordsForComponent = args.bundle.transcript.words.map((w) => ({
    text: w.text,
    start_ms: w.startMs,
    end_ms: w.endMs,
  }));
  const captionInner = fillTemplate(captionTpl, {
    words_json: JSON.stringify(wordsForComponent),
  });

  const masterDurationSec = msToSeconds(args.bundle.master.durationMs);

  const captionLayer = `<div class="clip" data-start="0" data-duration="${masterDurationSec}" data-track-index="${CAPTION_TRACK_INDEX}">
${captionInner}
</div>`;

  const timelineScript = `<script>
(function () {
  if (typeof gsap === "undefined") return;
  var tl = gsap.timeline({ paused: true, onUpdate: function () {
    if (window.__seekTo) window.__seekTo(tl.time() * 1000);
  }});
  tl.to({}, { duration: ${masterDurationSec} });
  window.__timelines = window.__timelines || {};
  window.__timelines["main"] = tl;
})();
</script>`;

  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
${css}
${base}
</style>
<script src="https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js"></script>
</head>
<body>
<div id="root"
     data-composition-id="main"
     data-start="0"
     data-duration="${masterDurationSec}"
     data-width="${ROOT_WIDTH}"
     data-height="${ROOT_HEIGHT}">
<video id="master-video"
       class="clip"
       data-start="0"
       data-duration="${masterDurationSec}"
       data-track-index="0"
       data-has-audio="true"
       muted
       src="${args.masterRelPath}"></video>
${seamFragments.join("\n")}
${captionLayer}
${timelineScript}
</div>
</body>
</html>`;
}

function renderSeamFragment(seam: Seam, trackIndex: number): string {
  if (!seam.graphic) return "";
  const tpl = loadComponentTemplate(seam.graphic.component);
  const filled = fillTemplate(tpl, seam.graphic.data);
  const startSec = msToSeconds(seam.at_ms);
  const durationSec = msToSeconds(seam.ends_at_ms - seam.at_ms);
  return `<div class="clip"
     data-seam="${seam.index}"
     data-start="${startSec}"
     data-duration="${durationSec}"
     data-track-index="${trackIndex}">
${filled}
</div>`;
}

export function writeCompositionHtml(args: ComposeArgs, outPath: string): void {
  writeFileSync(outPath, buildCompositionHtml(args));
}
```

- [ ] **Step 2: Replace `index.ts`**

Write to `tools/compositor/src/index.ts`:

```typescript
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
```

- [ ] **Step 3: Update `composer.test.ts`**

Replace contents of `tools/compositor/test/composer.test.ts` with:

```typescript
import { describe, it, expect } from "vitest";
import { buildCompositionHtml } from "../src/composer.js";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { SeamPlan, MasterBundle } from "../src/types.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function makeBundle(words: MasterBundle["transcript"]["words"], durationMs: number): MasterBundle {
  return {
    schemaVersion: 1,
    slug: "demo",
    master: { durationMs, width: 1440, height: 2560, fps: 60 },
    boundaries: [
      { atMs: 0, kind: "start" },
      { atMs: durationMs, kind: "end" },
    ],
    transcript: { language: "en", words },
  };
}

describe("buildCompositionHtml", () => {
  it("includes master video src, caption layer, seam fragment, and HyperFrames root attributes", () => {
    const plan: SeamPlan = {
      episode_slug: "demo",
      master_duration_ms: 1500,
      seams: [
        {
          index: 0,
          at_ms: 0,
          ends_at_ms: 1500,
          scene: "broll",
          graphic: { component: "title-card", data: { title: "Demo", subtitle: "Test" } },
        },
      ],
    };
    const html = buildCompositionHtml({
      repoRoot: path.resolve(__dirname, "../../.."),
      episodeDir: path.resolve(__dirname, "fixtures"),
      plan,
      bundle: makeBundle(
        [
          { text: "Hello", startMs: 0,    endMs: 350 },
          { text: "world", startMs: 380,  endMs: 720 },
          { text: "today", startMs: 1100, endMs: 1480 },
        ],
        1500,
      ),
      masterRelPath: "../master.mp4",
    });

    expect(html).toContain('src="../master.mp4"');
    expect(html).toContain('data-component="title-card"');
    expect(html).toContain('data-component="caption-karaoke"');
    expect(html).toContain("--video-width: 1440");
    expect(html).toContain('data-composition-id="main"');
    expect(html).toContain('data-width="1440"');
    expect(html).toContain('data-height="2560"');
    expect(html).toContain("muted");
    expect(html).toContain('data-has-audio="true"');
  });

  it("emits caption words as start_ms/end_ms (component boundary conversion)", () => {
    const plan: SeamPlan = { episode_slug: "demo", master_duration_ms: 5000, seams: [] };
    const html = buildCompositionHtml({
      repoRoot: path.resolve(__dirname, "../../.."),
      episodeDir: path.resolve(__dirname, "fixtures"),
      plan,
      bundle: makeBundle(
        [
          { text: "alpha",   startMs: 0,    endMs: 500 },
          { text: "charlie", startMs: 3000, endMs: 3500 },
        ],
        5000,
      ),
      masterRelPath: "../master.mp4",
    });
    expect(html).toContain('"text":"alpha","start_ms":0,"end_ms":500');
    expect(html).toContain('"text":"charlie","start_ms":3000,"end_ms":3500');
  });
});
```

- [ ] **Step 4: Run all compositor tests**

```bash
cd tools/compositor && npx vitest run
```

Expected: all PASS.

- [ ] **Step 5: Replace `test-run-stage2.sh`**

Write to `tools/scripts/test/test-run-stage2.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cp -r "$REPO_ROOT" "$WORK/repo"
cd "$WORK/repo"
EP="$WORK/repo/episodes/2026-04-27-demo"
mkdir -p "$EP/stage-1-cut" "$EP/stage-2-composite" "$EP/master"

# Stage 2 must read ONLY the bundle. Deliberately do NOT write transcript.json
# or cut-list.md — if Stage 2 still reads them, run-stage2 will fail.
cat > "$EP/master/bundle.json" <<'JSON'
{
  "schemaVersion": 1,
  "slug": "2026-04-27-demo",
  "master": { "durationMs": 2000, "width": 1440, "height": 2560, "fps": 60 },
  "boundaries": [
    { "atMs": 0, "kind": "start" },
    { "atMs": 1000, "kind": "seam" },
    { "atMs": 2000, "kind": "end" }
  ],
  "transcript": {
    "language": "en",
    "words": [
      { "text": "Hello", "startMs": 0,    "endMs": 350 },
      { "text": "world", "startMs": 380,  "endMs": 720 },
      { "text": "today", "startMs": 1100, "endMs": 1480 }
    ]
  }
}
JSON

ffmpeg -y -f lavfi -i "color=c=red:s=1440x2560:r=60:d=2" -c:v libx264 -pix_fmt yuv420p \
  "$EP/stage-1-cut/master.mp4" >/dev/null 2>&1

./tools/scripts/run-stage2.sh 2026-04-27-demo \
  || { echo "FAIL: run-stage2 exited non-zero"; exit 1; }

[ -f "$EP/stage-2-composite/seam-plan.md" ]      || { echo "FAIL: seam-plan.md missing"; exit 1; }
[ -f "$EP/stage-2-composite/composition.html" ]  || { echo "FAIL: composition.html missing"; exit 1; }
[ -f "$EP/stage-2-composite/preview.mp4" ]       || { echo "FAIL: preview.mp4 missing"; exit 1; }

echo "OK"
```

- [ ] **Step 6: Run `test-run-stage2.sh`, verify pass**

```bash
chmod +x tools/scripts/test/test-run-stage2.sh
tools/scripts/test/test-run-stage2.sh
```

Expected: PASS.

- [ ] **Step 7: Verify Stage 2 has no remaining reads of `transcript.json` / `cut-list.md`**

```bash
grep -nE 'transcript\.json|cut-list\.md' tools/compositor/src/index.ts tools/compositor/src/composer.ts
```

Expected: zero matches in those two files. Matches in `src/transcript.ts` (loader, called by `writeBundle`) and `src/stage1/writeBundle.ts` (Stage 1 input) are correct.

- [ ] **Step 8: Commit**

```bash
git add tools/compositor/src/composer.ts tools/compositor/src/index.ts tools/compositor/test/composer.test.ts tools/scripts/test/test-run-stage2.sh
git commit -m "refactor(stage2): read master/bundle.json instead of transcript+cut-list"
```

---

## Task 9: Final verification + tag + retro close

- [ ] **Step 1: Run the full test suite**

```bash
tools/scripts/test/test-check-deps.sh
tools/scripts/test/test-new-episode.sh
tools/scripts/test/test-run-stage1.sh
tools/scripts/test/test-run-stage2.sh
tools/scripts/test/test-render-final.sh
tools/scripts/test/test-retro-promote.sh
( cd tools/compositor && npx vitest run )
```

Expected: all PASS.

- [ ] **Step 2: Confirm working tree is clean**

```bash
git status
```

Expected: clean.

- [ ] **Step 3: Tag**

```bash
git tag phase-5-pipeline-contracts
```

- [ ] **Step 4: Append Phase 5 close entry to `standards/retro-changelog.md`**

Append to `standards/retro-changelog.md`:

```markdown
## 2026-04-28 — Phase 5 close: pipeline contracts hardened
- Scene mode `full` renamed to `broll` in compositor source, fixtures, and tests. parseSceneMode() rejects the legacy name explicitly.
- New master/bundle.json contract enforced at the Stage 1 -> Stage 2 boundary; Stage 2 reads it through a typed loader; raw-timeline reads of transcript.json and cut-list.md removed from Stage 2.
- Phase 6 brief written at docs/superpowers/specs/2026-04-28-agentic-graphics-planner-brief.md.
- Source: docs/superpowers/plans/2026-04-28-phase-5-pipeline-contracts.md.
- Reason: pilot of Phase 4 surfaced 5 Stage 1 -> Stage 2 contract drifts; this phase closes the class of bugs at the source.
```

- [ ] **Step 5: Update `standards/motion-graphics.md` if needed**

Check `standards/motion-graphics.md` — the canonical scene-mode listing was updated in commit `b763f8b` of the prep phase. Verify both `(c) full` (alias-form documentation) AND `broll` (canonical name) are mentioned correctly. If the doc still treats `full` as canonical, update the canonical column to `broll` and leave `full` only in the alias parenthetical.

- [ ] **Step 6: Commit retro entry**

```bash
git add standards/
git commit -m "retro(phase-5): close pipeline-contracts phase"
```

---

## Phase 5 done.

After this phase, the next real episode runs through Stage 1 → bundle → Stage 2 with the contract enforced by types. Phase 6 brainstorming starts from `docs/superpowers/specs/2026-04-28-agentic-graphics-planner-brief.md`.
