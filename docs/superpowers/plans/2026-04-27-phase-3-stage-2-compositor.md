# Phase 3 — Stage 2 Compositor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Stage 2 compositor: from `transcript.json` + `cut-list.md` + `master.mp4` produce `seam-plan.md` (CP2.5 artifact), `composition.html` driven by HyperFrames, `preview.mp4` (CP3 artifact), and finally `final.mp4` with music mixed in. Plus the six starter design-system components used by the compositor.

**Architecture:** A Node + TypeScript package at `tools/compositor/` reads `transcript.json` and `cut-list.md`, derives the list of seams, picks scene modes per seam under the 4-scene transition matrix, emits `seam-plan.md` for human review, then assembles `composition.html` referencing components from `design-system/components/`. HyperFrames renders that HTML to a video, and a final ffmpeg step overlays the rendered composition on `master.mp4` and mixes in the music track from `library/music/`.

**Tech Stack:** Node 20+, TypeScript, HyperFrames (`npx hyperframes`), ffmpeg, plain HTML/CSS for components (no React — HyperFrames is HTML-native).

**Prerequisite:** Phase 2 complete. `phase-2-stage-1` git tag exists. A real or smoke episode exists with valid `transcript.json` and `master.mp4`.

---

## File structure produced by this phase

```
tools/compositor/
├── package.json
├── tsconfig.json
├── src/
│   ├── index.ts                  # CLI entry: subcommands seam-plan, compose, render
│   ├── transcript.ts             # parsers for transcript.json + cut-list.md
│   ├── seamPlanner.ts            # scene-picking with transition matrix
│   ├── seamPlanWriter.ts         # serialize/deserialize seam-plan.md
│   ├── composer.ts               # build composition.html from seam-plan + components
│   ├── components.ts             # registry mapping scene-mode + component name to template
│   ├── tokens.ts                 # load tokens.json → CSS-variable string
│   └── types.ts
└── test/
    ├── transcript.test.ts
    ├── seamPlanner.test.ts
    ├── seamPlanWriter.test.ts
    ├── composer.test.ts
    └── fixtures/
        ├── transcript.sample.json
        └── cut-list.sample.md

design-system/components/
├── _base.css
├── caption-karaoke.html
├── glass-card.html
├── split-frame.html
├── fullscreen-broll.html
├── overlay-plate.html
└── title-card.html

tools/scripts/run-stage2.sh
tools/scripts/render-final.sh
tools/scripts/test/test-run-stage2.sh
tools/scripts/test/test-render-final.sh
docs/notes/hyperframes-cli.md
```

---

### Task 1: HyperFrames smoke test

Before writing our compositor, prove HyperFrames runs and renders deterministically on this machine.

- [ ] **Step 1: Run HyperFrames init in a sandbox**

```bash
mkdir -p /tmp/hf-smoke && cd /tmp/hf-smoke
npx -y hyperframes init demo
cd "$OLDPWD"
```

Expected: a `demo/` folder created with starter HTML and a config file.

- [ ] **Step 2: Render the demo**

```bash
cd /tmp/hf-smoke/demo
npx hyperframes render
cd "$OLDPWD"
```

Expected: an MP4 produced (note its exact path). If this fails due to Puppeteer / Chrome needing additional setup, capture the error and resolve before continuing — HyperFrames is mandatory for this phase.

- [ ] **Step 3: Capture CLI usage**

Create `docs/notes/hyperframes-cli.md` documenting:

- exact `npx hyperframes` subcommands available (run `npx hyperframes --help`)
- where the config file lives (`hyperframes.config.json` or similar) and its schema
- the format of HTML composition files that HyperFrames consumes
- how to control output resolution, fps, and codec
- how `npx hyperframes add <component>` works — what files it writes and where
- any limitations observed (browser version requirements, GPU usage, render time per second of output)

- [ ] **Step 4: Commit**

```bash
git add docs/notes/hyperframes-cli.md
git commit -m "docs(hyperframes): capture CLI reference and smoke test"
```

---

### Task 2: Initialize `tools/compositor/` Node package

**Files:**
- Create: `tools/compositor/package.json`, `tools/compositor/tsconfig.json`

- [ ] **Step 1: Initialize package**

```bash
cd tools/compositor
npm init -y
npm i -D typescript @types/node tsx vitest
npm i hyperframes
cd -
```

- [ ] **Step 2: Edit `tools/compositor/package.json` to add scripts**

Replace generated `scripts` block with:

```json
"scripts": {
  "build": "tsc",
  "dev":   "tsx src/index.ts",
  "test":  "vitest run",
  "compose": "tsx src/index.ts compose",
  "seam-plan": "tsx src/index.ts seam-plan",
  "render": "tsx src/index.ts render"
}
```

- [ ] **Step 3: Write `tools/compositor/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "outDir": "dist",
    "rootDir": "src",
    "types": ["node"],
    "resolveJsonModule": true
  },
  "include": ["src/**/*", "test/**/*"]
}
```

- [ ] **Step 4: Verify**

```bash
cd tools/compositor && npx tsx --eval "console.log('ok')" && cd -
```

Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/package.json tools/compositor/package-lock.json tools/compositor/tsconfig.json
git commit -m "feat(compositor): initialize Node TypeScript package"
```

---

### Task 3: Define types

**Files:**
- Create: `tools/compositor/src/types.ts`

- [ ] **Step 1: Write the file**

```typescript
export type SceneMode = "head" | "split" | "full" | "overlay";

export interface TranscriptWord {
  text: string;
  start_ms: number;
  end_ms: number;
}

export interface Transcript {
  words: TranscriptWord[];
  duration_ms: number;
}

export interface CutSpan {
  start_ms: number;
  end_ms: number;
  reason: "silence" | "filler" | "stumble" | "manual" | "other";
}

export interface Seam {
  index: number;
  at_ms: number;
  scene: SceneMode;
  graphic?: {
    component: string;
    data: Record<string, unknown>;
  };
  ends_at_ms: number;
}

export interface SeamPlan {
  episode_slug: string;
  master_duration_ms: number;
  seams: Seam[];
}
```

- [ ] **Step 2: Commit**

```bash
git add tools/compositor/src/types.ts
git commit -m "feat(compositor): define core types"
```

---

### Task 4: Transcript parser — failing test then impl

**Files:**
- Create: `tools/compositor/test/fixtures/transcript.sample.json`
- Create: `tools/compositor/test/transcript.test.ts`
- Create: `tools/compositor/src/transcript.ts`

- [ ] **Step 1: Write the fixture**

`tools/compositor/test/fixtures/transcript.sample.json`:

```json
{
  "words": [
    { "text": "Hello",  "start_ms": 0,    "end_ms": 350 },
    { "text": "world",  "start_ms": 380,  "end_ms": 720 },
    { "text": "today",  "start_ms": 1100, "end_ms": 1480 }
  ],
  "duration_ms": 1500
}
```

- [ ] **Step 2: Write failing test**

`tools/compositor/test/transcript.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { loadTranscript } from "../src/transcript.js";
import path from "node:path";

describe("loadTranscript", () => {
  it("parses sample transcript", () => {
    const t = loadTranscript(path.resolve(__dirname, "fixtures/transcript.sample.json"));
    expect(t.words).toHaveLength(3);
    expect(t.words[0].text).toBe("Hello");
    expect(t.duration_ms).toBe(1500);
  });
  it("rejects empty words array", () => {
    expect(() => loadTranscript("")).toThrow();
  });
});
```

- [ ] **Step 3: Run, expect failure**

```bash
cd tools/compositor && npx vitest run transcript.test.ts && cd -
```

Expected: failure (`loadTranscript` not defined).

- [ ] **Step 4: Implement**

`tools/compositor/src/transcript.ts`:

```typescript
import { readFileSync } from "node:fs";
import type { Transcript } from "./types.js";

export function loadTranscript(filePath: string): Transcript {
  const raw = readFileSync(filePath, "utf8");
  const data = JSON.parse(raw) as Transcript;
  if (!Array.isArray(data.words) || data.words.length === 0) {
    throw new Error(`Transcript has no words: ${filePath}`);
  }
  if (typeof data.duration_ms !== "number" || data.duration_ms <= 0) {
    throw new Error(`Transcript missing duration_ms: ${filePath}`);
  }
  return data;
}
```

- [ ] **Step 5: Run, expect pass**

```bash
cd tools/compositor && npx vitest run transcript.test.ts && cd -
```

Expected: 2 passing.

- [ ] **Step 6: Commit**

```bash
git add tools/compositor/src/transcript.ts tools/compositor/test/transcript.test.ts tools/compositor/test/fixtures/transcript.sample.json
git commit -m "feat(compositor): transcript loader"
```

---

### Task 5: Seam planner — pick scene per seam under transition matrix

**Files:**
- Create: `tools/compositor/test/seamPlanner.test.ts`
- Create: `tools/compositor/src/seamPlanner.ts`

The planner takes seam timestamps (derived from cut decisions in `cut-list.md`) and produces a list of `Seam` entries, choosing scene modes that satisfy the transition matrix:

- Forbidden: `head→head`, `head→overlay`, `overlay→head`, `overlay→overlay`, same-graphic `split→split`, same-graphic `full→full`.
- Default starting scene at seam 0 (start of video) is `full` (title card).

- [ ] **Step 1: Write failing tests**

```typescript
import { describe, it, expect } from "vitest";
import { planSeams } from "../src/seamPlanner.js";

describe("planSeams", () => {
  it("starts with full-screen scene at seam 0", () => {
    const plan = planSeams({
      episode_slug: "test",
      master_duration_ms: 10000,
      seam_timestamps_ms: [0, 2000, 5000, 8000],
    });
    expect(plan.seams[0].scene).toBe("full");
  });

  it("never produces forbidden head↔head transition", () => {
    const plan = planSeams({
      episode_slug: "test",
      master_duration_ms: 30000,
      seam_timestamps_ms: [0, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000],
    });
    for (let i = 1; i < plan.seams.length; i++) {
      const a = plan.seams[i - 1].scene, b = plan.seams[i].scene;
      const forbidden =
        (a === "head" && b === "head") ||
        (a === "head" && b === "overlay") ||
        (a === "overlay" && b === "head") ||
        (a === "overlay" && b === "overlay");
      expect(forbidden, `Forbidden ${a}->${b} at seam ${i}`).toBe(false);
    }
  });

  it("computes ends_at_ms for each seam from the next seam", () => {
    const plan = planSeams({
      episode_slug: "test",
      master_duration_ms: 10000,
      seam_timestamps_ms: [0, 3000, 7000],
    });
    expect(plan.seams[0].ends_at_ms).toBe(3000);
    expect(plan.seams[1].ends_at_ms).toBe(7000);
    expect(plan.seams[2].ends_at_ms).toBe(10000);
  });
});
```

- [ ] **Step 2: Run, expect failure**

```bash
cd tools/compositor && npx vitest run seamPlanner.test.ts && cd -
```

Expected: failure (`planSeams` not defined).

- [ ] **Step 3: Implement**

`tools/compositor/src/seamPlanner.ts`:

```typescript
import type { SceneMode, Seam, SeamPlan } from "./types.js";

interface PlanInput {
  episode_slug: string;
  master_duration_ms: number;
  seam_timestamps_ms: number[];
}

const ORDER: SceneMode[] = ["full", "split", "head", "split", "full", "overlay"];

export function planSeams(input: PlanInput): SeamPlan {
  const { episode_slug, master_duration_ms, seam_timestamps_ms } = input;
  if (seam_timestamps_ms.length === 0) {
    throw new Error("Need at least one seam timestamp");
  }
  const sorted = [...seam_timestamps_ms].sort((a, b) => a - b);
  const seams: Seam[] = [];
  let prev: SceneMode | null = null;
  for (let i = 0; i < sorted.length; i++) {
    const at = sorted[i];
    const next = sorted[i + 1] ?? master_duration_ms;
    const scene = pickScene(prev, i);
    seams.push({ index: i, at_ms: at, scene, ends_at_ms: next });
    prev = scene;
  }
  return { episode_slug, master_duration_ms, seams };
}

function pickScene(prev: SceneMode | null, index: number): SceneMode {
  if (prev === null) return "full";
  for (let offset = 0; offset < ORDER.length; offset++) {
    const candidate = ORDER[(index + offset) % ORDER.length];
    if (isAllowed(prev, candidate)) return candidate;
  }
  throw new Error(`No allowed transition from ${prev}`);
}

function isAllowed(from: SceneMode, to: SceneMode): boolean {
  if (from === "head"    && (to === "head"    || to === "overlay")) return false;
  if (from === "overlay" && (to === "head"    || to === "overlay")) return false;
  if (from === "split" && to === "split") return false;
  if (from === "full"  && to === "full")  return false;
  return true;
}
```

- [ ] **Step 4: Run, expect pass**

```bash
cd tools/compositor && npx vitest run seamPlanner.test.ts && cd -
```

Expected: 3 passing.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/seamPlanner.ts tools/compositor/test/seamPlanner.test.ts
git commit -m "feat(compositor): seam planner with transition matrix"
```

---

### Task 6: Seam plan markdown writer/reader

**Files:**
- Create: `tools/compositor/test/seamPlanWriter.test.ts`
- Create: `tools/compositor/src/seamPlanWriter.ts`

The writer produces a human-readable `seam-plan.md` (the CP2.5 review artifact). The reader parses it back so we can re-load after the user edits it.

- [ ] **Step 1: Write failing tests**

```typescript
import { describe, it, expect } from "vitest";
import { writeSeamPlan, readSeamPlan } from "../src/seamPlanWriter.js";
import type { SeamPlan } from "../src/types.js";

const sample: SeamPlan = {
  episode_slug: "demo",
  master_duration_ms: 10000,
  seams: [
    { index: 0, at_ms: 0,    scene: "full",  ends_at_ms: 3000,
      graphic: { component: "title-card", data: { title: "Hello" } } },
    { index: 1, at_ms: 3000, scene: "head",  ends_at_ms: 7000 },
    { index: 2, at_ms: 7000, scene: "split", ends_at_ms: 10000,
      graphic: { component: "glass-card", data: { items: ["A","B"] } } }
  ],
};

describe("seamPlanWriter", () => {
  it("round-trips through markdown", () => {
    const md = writeSeamPlan(sample);
    const back = readSeamPlan(md);
    expect(back).toEqual(sample);
  });

  it("includes scene-mode label per seam", () => {
    const md = writeSeamPlan(sample);
    expect(md).toMatch(/SEAM 0.*scene:\s*full/);
    expect(md).toMatch(/SEAM 1.*scene:\s*head/);
  });
});
```

- [ ] **Step 2: Run, expect failure**

```bash
cd tools/compositor && npx vitest run seamPlanWriter.test.ts && cd -
```

Expected: failure.

- [ ] **Step 3: Implement**

`tools/compositor/src/seamPlanWriter.ts`:

```typescript
import type { SeamPlan, Seam, SceneMode } from "./types.js";

const HEADER_RE = /^# Seam plan: (?<slug>[a-z0-9-]+) \(duration=(?<dur>\d+)ms\)$/;
const SEAM_RE   = /^SEAM (?<i>\d+) at_ms=(?<at>\d+) scene: (?<scene>head|split|full|overlay) ends_at_ms=(?<ends>\d+)$/;

export function writeSeamPlan(plan: SeamPlan): string {
  const lines: string[] = [];
  lines.push(`# Seam plan: ${plan.episode_slug} (duration=${plan.master_duration_ms}ms)`);
  lines.push("");
  lines.push("Edit this file to change scene choice or graphic for any seam, then re-run.");
  lines.push("");
  for (const s of plan.seams) {
    lines.push(`SEAM ${s.index} at_ms=${s.at_ms} scene: ${s.scene} ends_at_ms=${s.ends_at_ms}`);
    if (s.graphic) {
      lines.push(`  graphic: ${s.graphic.component}`);
      lines.push(`  data: ${JSON.stringify(s.graphic.data)}`);
    }
    lines.push("");
  }
  return lines.join("\n");
}

export function readSeamPlan(md: string): SeamPlan {
  const lines = md.split(/\r?\n/);
  const header = lines.find(l => l.startsWith("# Seam plan:"));
  if (!header) throw new Error("Seam plan missing header");
  const m = HEADER_RE.exec(header);
  if (!m?.groups) throw new Error(`Bad header: ${header}`);
  const plan: SeamPlan = {
    episode_slug: m.groups.slug,
    master_duration_ms: Number(m.groups.dur),
    seams: [],
  };
  let current: Seam | null = null;
  for (const line of lines) {
    const sm = SEAM_RE.exec(line);
    if (sm?.groups) {
      if (current) plan.seams.push(current);
      current = {
        index: Number(sm.groups.i),
        at_ms: Number(sm.groups.at),
        scene: sm.groups.scene as SceneMode,
        ends_at_ms: Number(sm.groups.ends),
      };
      continue;
    }
    if (current && line.trim().startsWith("graphic:")) {
      current.graphic = { component: line.split("graphic:")[1].trim(), data: {} };
    }
    if (current && current.graphic && line.trim().startsWith("data:")) {
      current.graphic.data = JSON.parse(line.split("data:")[1].trim());
    }
  }
  if (current) plan.seams.push(current);
  return plan;
}
```

- [ ] **Step 4: Run, expect pass**

```bash
cd tools/compositor && npx vitest run seamPlanWriter.test.ts && cd -
```

Expected: 2 passing.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/seamPlanWriter.ts tools/compositor/test/seamPlanWriter.test.ts
git commit -m "feat(compositor): seam plan markdown round-trip"
```

---

### Task 7: Tokens to CSS variables

**Files:**
- Create: `tools/compositor/src/tokens.ts`

- [ ] **Step 1: Write the file**

```typescript
import { readFileSync } from "node:fs";
import path from "node:path";

export function tokensToCssVars(tokensPath: string): string {
  const raw = readFileSync(tokensPath, "utf8");
  const tokens = JSON.parse(raw);
  const vars: string[] = [];
  walk(tokens, "", vars);
  return `:root {\n${vars.join("\n")}\n}`;
}

function walk(node: unknown, prefix: string, out: string[]) {
  if (typeof node === "string" || typeof node === "number") {
    out.push(`  --${prefix}: ${node};`);
    return;
  }
  if (node && typeof node === "object") {
    for (const [k, v] of Object.entries(node as Record<string, unknown>)) {
      walk(v, prefix ? `${prefix}-${k}` : k, out);
    }
  }
}

export function defaultTokensPath(repoRoot: string): string {
  return path.resolve(repoRoot, "design-system/tokens/tokens.json");
}
```

- [ ] **Step 2: Add a small test**

`tools/compositor/test/tokens.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { tokensToCssVars } from "../src/tokens.js";
import path from "node:path";

describe("tokensToCssVars", () => {
  it("emits CSS variables flattened from tokens.json", () => {
    const css = tokensToCssVars(path.resolve(__dirname, "../../../design-system/tokens/tokens.json"));
    expect(css).toContain("--video-width: 1440");
    expect(css).toContain("--video-height: 2560");
    expect(css).toContain("--safezone-bottom: 22%");
    expect(css).toContain("--blur-glass-md: 24px");
  });
});
```

- [ ] **Step 3: Run**

```bash
cd tools/compositor && npx vitest run tokens.test.ts && cd -
```

Expected: 1 passing.

- [ ] **Step 4: Commit**

```bash
git add tools/compositor/src/tokens.ts tools/compositor/test/tokens.test.ts
git commit -m "feat(compositor): flatten tokens.json into CSS variables"
```

---

### Task 8: Write the six starter HTML components

Each component is a self-contained HTML template with `{{PLACEHOLDER}}` slots the compositor fills in. All sizing and colors use CSS variables defined by `tokens.ts`. No hardcoded values.

**Files:**
- Create: `design-system/components/_base.css`
- Create: `design-system/components/caption-karaoke.html`
- Create: `design-system/components/glass-card.html`
- Create: `design-system/components/split-frame.html`
- Create: `design-system/components/fullscreen-broll.html`
- Create: `design-system/components/overlay-plate.html`
- Create: `design-system/components/title-card.html`

- [ ] **Step 1: Write `_base.css`**

```css
/* Imported by every component. CSS variables come from tokens.json via tokens.ts. */
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
  width:  var(--video-width);
  height: var(--video-height);
  background: var(--color-bg-transparent);
  font-family: var(--type-family-caption);
  color: var(--color-text-primary);
  overflow: hidden;
}
.glass {
  background: var(--color-glass-fill);
  border: 1px solid var(--color-glass-stroke);
  box-shadow: 0 8px 32px var(--color-glass-shadow);
  backdrop-filter: blur(var(--blur-glass-md));
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
}
.safe-bottom { bottom: var(--safezone-bottom); }
.safe-top    { top: var(--safezone-top); }
```

- [ ] **Step 2: Write `caption-karaoke.html`**

```html
<!-- caption-karaoke: per-word karaoke captions, max 3 visible, baseline raised. -->
<!-- data: words: [{ text, start_ms, end_ms }] -->
<div class="caption-layer" data-component="caption-karaoke">
  <style>
    .caption-layer {
      position: absolute;
      left: 0; right: 0;
      bottom: var(--safezone-bottom);
      display: flex;
      justify-content: center;
      gap: var(--spacing-sm);
      font-family: var(--type-family-caption);
      font-size: var(--type-size-caption);
      font-weight: var(--type-weight-bold);
      text-align: center;
      pointer-events: none;
    }
    .caption-word { color: var(--color-caption-inactive); transition: color 80ms linear; }
    .caption-word.active { color: var(--color-caption-active); }
  </style>
  <div class="caption-window"></div>
  <script type="application/json" id="caption-data">{{WORDS_JSON}}</script>
  <script>
    (function () {
      const data = JSON.parse(document.getElementById('caption-data').textContent);
      const win = document.querySelector('.caption-window');
      function render(t) {
        const i = data.findIndex(w => t >= w.start_ms && t < w.end_ms);
        if (i < 0) { win.innerHTML = ''; return; }
        const start = Math.max(0, i - 1);
        const slice = data.slice(start, start + 3);
        win.innerHTML = slice.map((w, k) =>
          `<span class="caption-word${start + k === i ? ' active' : ''}">${w.text}</span>`
        ).join('');
      }
      window.__seekTo = render;
      render(0);
    })();
  </script>
</div>
```

- [ ] **Step 3: Write `glass-card.html`**

```html
<!-- glass-card: frosted-glass plate with title + bullet items. -->
<!-- data: title: string, items_html: string -->
<div class="glass glass-card" data-component="glass-card">
  <style>
    .glass-card {
      width: 90%; max-width: 1200px;
      margin: var(--spacing-lg) auto;
    }
    .glass-card h2 {
      font-family: var(--type-family-display);
      font-size: var(--type-size-title);
      font-weight: var(--type-weight-black);
      margin-bottom: var(--spacing-md);
    }
    .glass-card li {
      font-size: var(--type-size-body);
      line-height: 1.4;
      list-style: none;
      margin-bottom: var(--spacing-sm);
    }
  </style>
  <h2>{{TITLE}}</h2>
  <ul>{{ITEMS_HTML}}</ul>
</div>
```

- [ ] **Step 4: Write `split-frame.html`**

```html
<!-- split-frame: places talking-head video on one side and a glass plate on the other. -->
<!-- data: side: 'left'|'right', child_html: string -->
<div class="split-frame" data-component="split-frame" data-side="{{SIDE}}">
  <style>
    .split-frame { position: absolute; inset: 0; display: grid; grid-template-columns: 1fr 1fr; }
    .split-head { background: transparent; }
    .split-graphic { display: flex; align-items: center; justify-content: center; padding: var(--spacing-lg); }
  </style>
  <div class="split-head"></div>
  <div class="split-graphic">{{CHILD_HTML}}</div>
</div>
```

- [ ] **Step 5: Write `fullscreen-broll.html`**

```html
<!-- fullscreen-broll: full-frame motion-graphic backdrop. -->
<!-- data: child_html: string -->
<div class="fullscreen-broll" data-component="fullscreen-broll">
  <style>
    .fullscreen-broll {
      position: absolute; inset: 0;
      background: linear-gradient(180deg, #0a1024 0%, #2a164d 100%);
      display: flex; align-items: center; justify-content: center;
    }
  </style>
  {{CHILD_HTML}}
</div>
```

- [ ] **Step 6: Write `overlay-plate.html`**

```html
<!-- overlay-plate: floating glass plate over talking-head, top-right by default. -->
<!-- data: title: string, value: string, position: 'top-right'|'top-left'|'bottom-right' -->
<div class="overlay-plate glass" data-component="overlay-plate" data-position="{{POSITION}}">
  <style>
    .overlay-plate {
      position: absolute;
      width: 38%;
      padding: var(--spacing-md);
    }
    .overlay-plate[data-position="top-right"]    { top: var(--safezone-top);    right: var(--safezone-side); }
    .overlay-plate[data-position="top-left"]     { top: var(--safezone-top);    left:  var(--safezone-side); }
    .overlay-plate[data-position="bottom-right"] { bottom: 30%; right: var(--safezone-side); }
    .overlay-plate .title { font-size: var(--type-size-body); color: var(--color-text-secondary); }
    .overlay-plate .value { font-size: var(--type-size-title); font-weight: var(--type-weight-black); }
  </style>
  <div class="title">{{TITLE}}</div>
  <div class="value">{{VALUE}}</div>
</div>
```

- [ ] **Step 7: Write `title-card.html`**

```html
<!-- title-card: opening seam-0 full-screen title. -->
<!-- data: title: string, subtitle?: string -->
<div class="title-card" data-component="title-card">
  <style>
    .title-card {
      position: absolute; inset: 0;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      background: radial-gradient(circle at 50% 40%, #1a2548 0%, #050a1f 100%);
      padding: var(--spacing-xl);
      text-align: center;
    }
    .title-card h1 {
      font-family: var(--type-family-display);
      font-size: 160px;
      font-weight: var(--type-weight-black);
      letter-spacing: -0.02em;
      line-height: 1.0;
    }
    .title-card .subtitle {
      margin-top: var(--spacing-md);
      font-size: var(--type-size-body);
      color: var(--color-text-secondary);
    }
  </style>
  <h1>{{TITLE}}</h1>
  <div class="subtitle">{{SUBTITLE}}</div>
</div>
```

- [ ] **Step 8: Visual smoke test — render each component standalone**

Build a tiny sandbox HTML per component, open in HyperFrames preview, confirm tokens render (no `var(--…)` text leaks visible). Append observations to `docs/notes/components-smoke.md`.

- [ ] **Step 9: Commit**

```bash
git add design-system/components/
git commit -m "feat(design-system): six starter HTML components reading tokens"
```

---

### Task 9: Composer — assemble `composition.html` from seam plan + components

**Files:**
- Create: `tools/compositor/src/components.ts`
- Create: `tools/compositor/src/composer.ts`
- Create: `tools/compositor/test/composer.test.ts`

The composer produces a single `composition.html` that:
- Starts with `<style>` containing CSS variables flattened from `tokens.json`.
- Has a video element holding `master.mp4` (for preview rendering with the talking-head visible at the right times).
- Schedules each seam's component to appear/disappear at `[at_ms, ends_at_ms]` using a small JS timeline.
- Layers a single caption-karaoke component over everything for the entire duration.

- [ ] **Step 1: Write `components.ts`**

```typescript
import { readFileSync } from "node:fs";
import path from "node:path";

const COMPONENTS_DIR = path.resolve(__dirname, "../../../design-system/components");

export function loadComponentTemplate(name: string): string {
  return readFileSync(path.join(COMPONENTS_DIR, `${name}.html`), "utf8");
}

export function loadBaseCss(): string {
  return readFileSync(path.join(COMPONENTS_DIR, "_base.css"), "utf8");
}

export function fillTemplate(template: string, data: Record<string, unknown>): string {
  return template.replace(/\{\{([A-Z_]+)\}\}/g, (_, key) => {
    const v = data[key.toLowerCase()];
    if (v === undefined) return "";
    if (typeof v === "string" || typeof v === "number") return String(v);
    return JSON.stringify(v);
  });
}
```

- [ ] **Step 2: Write composer**

`tools/compositor/src/composer.ts`:

```typescript
import { writeFileSync } from "node:fs";
import path from "node:path";
import type { SeamPlan, Seam, Transcript } from "./types.js";
import { tokensToCssVars, defaultTokensPath } from "./tokens.js";
import { loadBaseCss, loadComponentTemplate, fillTemplate } from "./components.js";

interface ComposeArgs {
  repoRoot: string;
  episodeDir: string;
  plan: SeamPlan;
  transcript: Transcript;
  masterRelPath: string;
}

export function buildCompositionHtml(args: ComposeArgs): string {
  const css = tokensToCssVars(defaultTokensPath(args.repoRoot));
  const base = loadBaseCss();

  const seamFragments = args.plan.seams
    .filter(s => s.graphic)
    .map(s => renderSeamFragment(s));

  const captionTpl = loadComponentTemplate("caption-karaoke");
  const captionLayer = fillTemplate(captionTpl, { words_json: JSON.stringify(args.transcript.words) });

  return `<!doctype html><html><head><meta charset="utf-8"><style>${css}\n${base}</style></head><body>
<video id="master" src="${args.masterRelPath}" autoplay muted></video>
<div id="seam-layer">${seamFragments.join("\n")}</div>
${captionLayer}
<script>
  const master = document.getElementById('master');
  const seams = ${JSON.stringify(args.plan.seams)};
  function update() {
    const t = master.currentTime * 1000;
    for (const s of seams) {
      const el = document.querySelector('[data-seam="' + s.index + '"]');
      if (!el) continue;
      el.style.display = (t >= s.at_ms && t < s.ends_at_ms) ? '' : 'none';
    }
    if (window.__seekTo) window.__seekTo(t);
    requestAnimationFrame(update);
  }
  master.addEventListener('play', update);
  master.addEventListener('seeked', update);
</script>
</body></html>`;
}

function renderSeamFragment(seam: Seam): string {
  if (!seam.graphic) return "";
  const tpl = loadComponentTemplate(seam.graphic.component);
  const filled = fillTemplate(tpl, seam.graphic.data);
  return `<div data-seam="${seam.index}" style="display:none">${filled}</div>`;
}

export function writeCompositionHtml(args: ComposeArgs, outPath: string): void {
  writeFileSync(outPath, buildCompositionHtml(args));
}
```

- [ ] **Step 3: Write a composer test**

`tools/compositor/test/composer.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { buildCompositionHtml } from "../src/composer.js";
import { loadTranscript } from "../src/transcript.js";
import path from "node:path";
import type { SeamPlan } from "../src/types.js";

describe("buildCompositionHtml", () => {
  it("includes master video src, caption layer, and one seam fragment", () => {
    const transcript = loadTranscript(
      path.resolve(__dirname, "fixtures/transcript.sample.json")
    );
    const plan: SeamPlan = {
      episode_slug: "demo",
      master_duration_ms: 1500,
      seams: [
        { index: 0, at_ms: 0, ends_at_ms: 1500, scene: "full",
          graphic: { component: "title-card", data: { title: "Demo", subtitle: "Test" } } }
      ],
    };
    const html = buildCompositionHtml({
      repoRoot: path.resolve(__dirname, "../../.."),
      episodeDir: path.resolve(__dirname, "fixtures"),
      plan, transcript,
      masterRelPath: "../master.mp4",
    });
    expect(html).toContain('src="../master.mp4"');
    expect(html).toContain('data-component="title-card"');
    expect(html).toContain('data-component="caption-karaoke"');
    expect(html).toContain("--video-width: 1440");
  });
});
```

- [ ] **Step 4: Run**

```bash
cd tools/compositor && npx vitest run composer.test.ts && cd -
```

Expected: 1 passing.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/components.ts tools/compositor/src/composer.ts tools/compositor/test/composer.test.ts
git commit -m "feat(compositor): assemble composition.html from seam plan + components"
```

---

### Task 10: CLI entry — seam-plan, compose, render subcommands

**Files:**
- Create: `tools/compositor/src/index.ts`

- [ ] **Step 1: Write the CLI**

```typescript
#!/usr/bin/env node
import { writeFileSync, readFileSync } from "node:fs";
import path from "node:path";
import { loadTranscript } from "./transcript.js";
import { planSeams } from "./seamPlanner.js";
import { writeSeamPlan, readSeamPlan } from "./seamPlanWriter.js";
import { writeCompositionHtml } from "./composer.js";

const [, , cmd, ...rest] = process.argv;

function usage(): never {
  console.error("Usage: compositor <seam-plan|compose|render> --episode <path> [...]");
  process.exit(1);
}

function arg(flag: string): string | undefined {
  const i = rest.indexOf(flag);
  return i >= 0 ? rest[i + 1] : undefined;
}

const episodeDir = arg("--episode");
if (!episodeDir) usage();

const repoRoot = process.env.REPO_ROOT ?? path.resolve(episodeDir, "../..");
const transcriptPath  = path.join(episodeDir, "stage-1-cut/transcript.json");
const cutListPath     = path.join(episodeDir, "stage-1-cut/cut-list.md");
const seamPlanPath    = path.join(episodeDir, "stage-2-composite/seam-plan.md");
const compositionPath = path.join(episodeDir, "stage-2-composite/composition.html");
const masterPath      = path.join(episodeDir, "stage-1-cut/master.mp4");

function deriveSeamTimestamps(cutListMd: string): number[] {
  const out: number[] = [0];
  for (const m of cutListMd.matchAll(/at_ms=(\d+)/g)) out.push(Number(m[1]));
  return [...new Set(out)].sort((a, b) => a - b);
}

if (cmd === "seam-plan") {
  const transcript = loadTranscript(transcriptPath);
  const cutList = readFileSync(cutListPath, "utf8");
  const seamTimestamps = deriveSeamTimestamps(cutList);
  const slug = path.basename(episodeDir);
  const plan = planSeams({
    episode_slug: slug,
    master_duration_ms: transcript.duration_ms,
    seam_timestamps_ms: seamTimestamps,
  });
  writeFileSync(seamPlanPath, writeSeamPlan(plan));
  console.log(`Wrote ${seamPlanPath}`);
} else if (cmd === "compose") {
  const transcript = loadTranscript(transcriptPath);
  const plan = readSeamPlan(readFileSync(seamPlanPath, "utf8"));
  writeCompositionHtml(
    {
      repoRoot, episodeDir, plan, transcript,
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

- [ ] **Step 2: Smoke run on fixture**

```bash
mkdir -p /tmp/comp-smoke/episodes/2026-04-27-demo/stage-1-cut /tmp/comp-smoke/episodes/2026-04-27-demo/stage-2-composite
cp tools/compositor/test/fixtures/transcript.sample.json \
   /tmp/comp-smoke/episodes/2026-04-27-demo/stage-1-cut/transcript.json
printf "at_ms=0\nat_ms=500\nat_ms=1000\n" > /tmp/comp-smoke/episodes/2026-04-27-demo/stage-1-cut/cut-list.md
ffmpeg -y -f lavfi -i "color=c=red:s=1440x2560:r=60:d=2" -c:v libx264 -pix_fmt yuv420p \
  /tmp/comp-smoke/episodes/2026-04-27-demo/stage-1-cut/master.mp4 >/dev/null 2>&1

REPO_ROOT="$(pwd)" npx tsx tools/compositor/src/index.ts seam-plan \
  --episode /tmp/comp-smoke/episodes/2026-04-27-demo
REPO_ROOT="$(pwd)" npx tsx tools/compositor/src/index.ts compose \
  --episode /tmp/comp-smoke/episodes/2026-04-27-demo

test -f /tmp/comp-smoke/episodes/2026-04-27-demo/stage-2-composite/seam-plan.md && \
test -f /tmp/comp-smoke/episodes/2026-04-27-demo/stage-2-composite/composition.html && \
echo OK
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add tools/compositor/src/index.ts
git commit -m "feat(compositor): CLI with seam-plan and compose subcommands"
```

---

### Task 11: `run-stage2.sh` wrapper

**Files:**
- Create: `tools/scripts/run-stage2.sh`
- Create: `tools/scripts/test/test-run-stage2.sh`

The wrapper produces both the seam-plan (CP2.5) and the preview render (CP3). User reviews both files between substages.

- [ ] **Step 1: Write failing test**

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
mkdir -p "$EP/stage-1-cut" "$EP/stage-2-composite"
cp tools/compositor/test/fixtures/transcript.sample.json "$EP/stage-1-cut/transcript.json"
printf "at_ms=0\nat_ms=500\nat_ms=1000\n" > "$EP/stage-1-cut/cut-list.md"
ffmpeg -y -f lavfi -i "color=c=red:s=1440x2560:r=60:d=2" -c:v libx264 -pix_fmt yuv420p \
  "$EP/stage-1-cut/master.mp4" >/dev/null 2>&1

./tools/scripts/run-stage2.sh 2026-04-27-demo \
  || { echo "FAIL: run-stage2 exited non-zero"; exit 1; }

[ -f "$EP/stage-2-composite/seam-plan.md" ] || { echo "FAIL: seam-plan.md missing"; exit 1; }
[ -f "$EP/stage-2-composite/composition.html" ] || { echo "FAIL: composition.html missing"; exit 1; }
[ -f "$EP/stage-2-composite/preview.mp4" ] || { echo "FAIL: preview.mp4 missing"; exit 1; }
echo "OK"
```

- [ ] **Step 2: Run, expect failure**

```bash
chmod +x tools/scripts/test/test-run-stage2.sh
tools/scripts/test/test-run-stage2.sh
```

Expected: failure.

- [ ] **Step 3: Implement `run-stage2.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then echo "Usage: $0 <slug>"; exit 1; fi
SLUG="$1"
REPO_ROOT="$(pwd)"
EPISODE="$REPO_ROOT/episodes/$SLUG"

[ -d "$EPISODE" ] || { echo "ERROR: $EPISODE not found"; exit 1; }
[ -f "$EPISODE/stage-1-cut/master.mp4" ]      || { echo "ERROR: master.mp4 missing"; exit 1; }
[ -f "$EPISODE/stage-1-cut/transcript.json" ] || { echo "ERROR: transcript.json missing"; exit 1; }
[ -f "$EPISODE/stage-1-cut/cut-list.md" ]     || { echo "ERROR: cut-list.md missing"; exit 1; }

REPO_ROOT="$REPO_ROOT" npx -y tsx tools/compositor/src/index.ts seam-plan --episode "$EPISODE"
echo "CP2.5 ready: $EPISODE/stage-2-composite/seam-plan.md. Awaiting review."

REPO_ROOT="$REPO_ROOT" npx tsx tools/compositor/src/index.ts compose --episode "$EPISODE"

HF_OUT="$EPISODE/stage-2-composite/preview.mp4"
( cd "$EPISODE/stage-2-composite" && npx -y hyperframes render --input composition.html --output preview.mp4 \
    --width 1440 --height 2560 --fps 60 ) || \
  { echo "ERROR: hyperframes render failed"; exit 1; }

[ -f "$HF_OUT" ] || { echo "ERROR: preview.mp4 not produced"; exit 1; }
echo "CP3 ready: $HF_OUT. Awaiting review."
```

- [ ] **Step 4: Run test, expect pass**

```bash
chmod +x tools/scripts/run-stage2.sh
tools/scripts/test/test-run-stage2.sh
```

Expected: `OK`. If `npx hyperframes render` arguments differ from what `docs/notes/hyperframes-cli.md` documented, fix the script and re-run.

- [ ] **Step 5: Commit**

```bash
git add tools/scripts/run-stage2.sh tools/scripts/test/test-run-stage2.sh
git commit -m "feat: run-stage2.sh produces seam-plan and preview"
```

---

### Task 12: `render-final.sh` — full render + ffmpeg merge with music

**Files:**
- Create: `tools/scripts/render-final.sh`
- Create: `tools/scripts/test/test-render-final.sh`

- [ ] **Step 1: Write failing test**

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
mkdir -p "$EP/stage-1-cut" "$EP/stage-2-composite" "$WORK/repo/library/music"

cp tools/compositor/test/fixtures/transcript.sample.json "$EP/stage-1-cut/transcript.json"
printf "at_ms=0\nat_ms=750\n" > "$EP/stage-1-cut/cut-list.md"
ffmpeg -y -f lavfi -i "color=c=red:s=1440x2560:r=60:d=2" -c:v libx264 -pix_fmt yuv420p \
  "$EP/stage-1-cut/master.mp4" >/dev/null 2>&1
ffmpeg -y -f lavfi -i "anoisesrc=d=2:c=pink:r=48000:a=0.05" -c:a libmp3lame \
  "$WORK/repo/library/music/test.mp3" >/dev/null 2>&1

cat > "$EP/meta.yaml" <<EOF
title: "Demo"
slug: 2026-04-27-demo
date: 2026-04-27
duration_seconds: 2
tags: []
targets: [youtube-shorts]
music: library/music/test.mp3
EOF

./tools/scripts/run-stage2.sh 2026-04-27-demo
./tools/scripts/render-final.sh 2026-04-27-demo \
  || { echo "FAIL: render-final exited non-zero"; exit 1; }

FINAL="$EP/stage-2-composite/final.mp4"
[ -f "$FINAL" ] || { echo "FAIL: final.mp4 missing"; exit 1; }

RES="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of default=nw=1 "$FINAL")"
echo "$RES" | grep -q "width=1440"  || { echo "FAIL: width"; echo "$RES"; exit 1; }
echo "$RES" | grep -q "height=2560" || { echo "FAIL: height"; echo "$RES"; exit 1; }
echo "$RES" | grep -qE "r_frame_rate=60(/1)?" || { echo "FAIL: fps"; echo "$RES"; exit 1; }

MEAN_VOL="$(ffmpeg -i "$FINAL" -af volumedetect -vn -f null /dev/null 2>&1 | grep mean_volume | awk '{print $5}')"
[ -n "$MEAN_VOL" ] || { echo "FAIL: no audio in final"; exit 1; }

echo "OK: final.mp4 conforms to spec"
```

- [ ] **Step 2: Run, expect failure**

```bash
chmod +x tools/scripts/test/test-render-final.sh
tools/scripts/test/test-render-final.sh
```

Expected: failure.

- [ ] **Step 3: Implement `render-final.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 1 ]; then echo "Usage: $0 <slug>"; exit 1; fi
SLUG="$1"
REPO_ROOT="$(pwd)"
EP="$REPO_ROOT/episodes/$SLUG"
COMPOSITION="$EP/stage-2-composite/composition.html"
MASTER="$EP/stage-1-cut/master.mp4"
META="$EP/meta.yaml"
FINAL="$EP/stage-2-composite/final.mp4"

[ -f "$COMPOSITION" ] || { echo "ERROR: composition.html missing"; exit 1; }
[ -f "$MASTER" ]      || { echo "ERROR: master.mp4 missing"; exit 1; }
[ -f "$META" ]        || { echo "ERROR: meta.yaml missing"; exit 1; }

MUSIC_REL="$(grep '^music:' "$META" | sed 's/music:[[:space:]]*//;s/^"//;s/"$//')"
if [ -z "$MUSIC_REL" ]; then
  echo "ERROR: meta.yaml music: field is empty. Set it to library/music/<file>.mp3"
  exit 1
fi
MUSIC="$REPO_ROOT/$MUSIC_REL"
[ -f "$MUSIC" ] || { echo "ERROR: music file not found at $MUSIC"; exit 1; }

OVERLAYS="$EP/stage-2-composite/overlays.mov"
( cd "$EP/stage-2-composite" && npx -y hyperframes render \
    --input composition.html --output overlays.mov \
    --width 1440 --height 2560 --fps 60 --transparent ) || \
  { echo "ERROR: hyperframes final render failed"; exit 1; }

ffmpeg -y \
  -i "$MASTER" \
  -i "$OVERLAYS" \
  -i "$MUSIC" \
  -filter_complex "[0:v][1:v]overlay=0:0:format=auto[vout]; \
                   [2:a]loudnorm=I=-22:TP=-1:LRA=11[mloud]; \
                   [0:a][mloud]amix=inputs=2:duration=first:weights='1 0.6':normalize=0[aout]" \
  -map "[vout]" -map "[aout]" \
  -c:v libx264 -profile:v high -level 5.1 -pix_fmt yuv420p \
  -b:v 35M -maxrate 40M -bufsize 70M \
  -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
  -c:a aac -b:a 320k -ar 48000 -ac 2 \
  "$FINAL"

echo "Final render complete: $FINAL"
```

- [ ] **Step 4: Run test, expect pass**

```bash
chmod +x tools/scripts/render-final.sh
tools/scripts/test/test-render-final.sh
```

Expected: `OK: final.mp4 conforms to spec`. If `npx hyperframes render --transparent` is not the actual flag name per docs, fix.

- [ ] **Step 5: Commit**

```bash
git add tools/scripts/render-final.sh tools/scripts/test/test-render-final.sh
git commit -m "feat: render-final.sh merges overlays + master + music to spec"
```

---

### Task 13: Phase verification

- [ ] **Step 1: Run all tests**

```bash
tools/scripts/test/test-check-deps.sh
tools/scripts/test/test-new-episode.sh
tools/scripts/test/test-run-stage1.sh
tools/scripts/test/test-run-stage2.sh
tools/scripts/test/test-render-final.sh
( cd tools/compositor && npx vitest run )
```

Expected: all pass.

- [ ] **Step 2: Tag**

```bash
git status   # expect clean
git tag phase-3-compositor
```

---

## Phase 3 done. Next: `2026-04-27-phase-4-first-episode-and-retro.md`.
