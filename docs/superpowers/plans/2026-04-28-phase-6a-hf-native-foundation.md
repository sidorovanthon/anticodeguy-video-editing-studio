# Phase 6a — HF-native foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Stage 2 onto HyperFrames' canonical sub-composition model, replace `tokens.json` with a single `DESIGN.md`, migrate captions to the HF pattern, vendor HF skills for future agentic use, and prove end-to-end wiring with one synthetic bespoke sub-composition. No graphics planner, no real bespoke graphics — that is Phase 6b.

**Architecture:** Compositor parses a fenced JSON block in repo-root `DESIGN.md` and emits `episodes/<slug>/stage-2-composite/index.html` (HF-canonical root) plus `compositions/captions.html` (HF sub-composition). Per-seam sub-compositions are discovered by file existence at `compositions/seam-<id>.html`; in 6a only one synthetic test file exists. Validation (`hyperframes lint/validate/inspect` + `animation-map`) is wired into `run-stage2-compose.sh`. HF skills are vendored read-only at `tools/hyperframes-skills/` for future subagent access.

**Tech Stack:** TypeScript (compositor, vitest), bash (scripts), markdown (DESIGN.md, standards), HyperFrames v0.4.31 (render + skills tarball).

**Spec source:** `docs/superpowers/specs/2026-04-28-phase-6a-hf-native-foundation-design.md`

**Branch model:** Work directly on `main` is acceptable (tests gate every task). Each task ends with one commit. Final tag `phase-6a-hf-native-foundation` lands at the end.

---

## Task 1: Generate DESIGN.md draft and gate on user approval

**Files:**
- Create: `DESIGN.md` (repo root)

This task is the HARD-GATE for everything else. The compositor rewrite reads `DESIGN.md`; until it exists and is approved, no other task starts.

- [ ] **Step 1: Read source material**

Read these files to extract values for the draft:
- `design-system/tokens/tokens.json` — all hex values, blur sizes, spacing, radii, type families.
- `standards/motion-graphics.md` — frosted-glass language, transition matrix.
- `standards/captions.md` — caption typography rules.
- `design-system/components/_base.css` — confirms which CSS variable names are referenced (`--color-bg-transparent`, `--color-glass-fill`, etc.).

- [ ] **Step 2: Write DESIGN.md draft**

Create `DESIGN.md` at the repo root with the following structure. Substitute real values from `tokens.json`:

```markdown
# DESIGN.md — anticodeguy video editing studio

Brand identity for motion graphics across all episodes. This file is the single source of truth for the visual contract, and the compositor parses the fenced `hyperframes-tokens` JSON block below to emit `:root` CSS variables. Prose sections are read by humans and by coding subagents (Phase 6b) but not parsed.

## Style Prompt

Calm, deliberate, frosted-glass aesthetic on top of talking-head footage. Surfaces are translucent white with subtle blue accents; text is high-contrast white with a quieter secondary tone. Motion is deliberate and short — entrances under half a second, eases ranging from `power3.out` for arrivals to `power2.in` for the rare exit. Nothing flashes, strobes, or screams; the channel's tone is technical-confident, not loud.

## Colors

Roles:
- **bg.transparent** — full-canvas transparent background; the talking-head video sits underneath.
- **glass.fill / glass.stroke / glass.shadow** — frosted-glass surface stack. All sub-compositions that overlay text on video sit on a glass surface.
- **text.primary** — pure white for headings and active captions.
- **text.secondary** — 72%-opacity white for supporting copy.
- **text.accent** — soft sky-blue for highlights, links, and one-word emphasis.
- **caption.active / caption.inactive** — karaoke caption pair: full-white when the word is being spoken, 55% white before/after.

```json hyperframes-tokens
{
  "color": {
    "bg":      { "transparent": "rgba(0,0,0,0)" },
    "glass":   { "fill": "rgba(255,255,255,0.18)", "stroke": "rgba(255,255,255,0.32)", "shadow": "rgba(0,0,0,0.35)" },
    "text":    { "primary": "#FFFFFF", "secondary": "rgba(255,255,255,0.72)", "accent": "#7CC4FF" },
    "caption": { "active": "#FFFFFF", "inactive": "rgba(255,255,255,0.55)" }
  },
  "type": {
    "family": { "caption": "'Inter', system-ui, sans-serif", "display": "'Inter Display', 'Inter', sans-serif" },
    "weight": { "regular": 500, "bold": 700, "black": 900 },
    "size":   { "caption": "64px", "title": "96px", "body": "44px" }
  },
  "blur":     { "glass-sm": "16px", "glass-md": "24px", "glass-lg": "40px" },
  "radius":   { "sm": "16px", "md": "28px", "lg": "44px", "pill": "9999px" },
  "spacing":  { "xs": "8px", "sm": "16px", "md": "24px", "lg": "40px", "xl": "64px" },
  "safezone": { "top": "8%", "bottom": "22%", "side": "6%" },
  "video":    { "width": 1440, "height": 2560, "fps": 60, "color": "rec709-sdr" }
}
```

## Typography

- **Caption / body copy:** `Inter` 500 — 44–64 px depending on emphasis. Tabular-nums on any numeric column.
- **Display / headings:** `Inter Display` 700–900 — 96 px+. Used for title cards and seam-level emphasis only, never on captions.

System-font fallback chain: `system-ui, sans-serif`. The HyperFrames compiler embeds Inter on render.

## Motion

- **Entrances:** `gsap.from()` with `power3.out`, 0.4–0.7 s duration, offset 0.1–0.3 s after the seam start.
- **Holds:** the body of every non-`head` seam is held still — no idle motion, no looping shimmer.
- **Exits:** none, except the final scene of the episode (per HyperFrames scene-transition rules). Seam boundaries handle scene change; the outgoing scene must be fully visible at transition.
- **Vary eases per scene:** at least three different easings across entrances within a single seam composition.

## What NOT to Do

1. **No flashing or strobing.** Anything blinking faster than 2 Hz is rejected at review.
2. **No exit animations except on the final scene.** The scene transition is the exit; per-element fade-out tweens before a transition are a bug.
3. **No off-palette colors.** Hex values come from the JSON block above; no `#333`, no `#3b82f6`, no on-the-fly tints. Adjust within the palette family to fix contrast warnings.
4. **No full-screen linear gradients on dark backgrounds.** H.264 banding makes them ugly. Use a radial gradient or solid + localized glow.
5. **No `Math.random()` / `Date.now()` / network fetches** in any composition — HyperFrames runtime forbids them and the render breaks.
```

- [ ] **Step 3: Commit the draft**

```bash
git add DESIGN.md
git commit -m "feat(phase-6a): add DESIGN.md as single source of visual contract

Replaces tokens.json (still in tree until compositor rewrite lands).
Style Prompt and What NOT to Do sections drafted from current pilot
aesthetic; palette and typography migrated verbatim from tokens.json.
Awaiting host review before compositor refactor proceeds.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

- [ ] **Step 4: Pause for host review**

Surface to the host: "DESIGN.md draft committed. Please review Style Prompt, What NOT to Do, and Motion sections specifically — those were drafted from inspection, not migrated from existing files. Approve to continue, or edit in place and tell me to proceed."

Do not start Task 2 until the host says go.

---

## Task 2: Vendor HyperFrames skills

**Files:**
- Create: `tools/scripts/sync-hf-skills.sh`
- Create: `tools/hyperframes-skills/VERSION`
- Create: `tools/hyperframes-skills/{hyperframes,hyperframes-cli,gsap}/...` (extracted from npm tarball)

- [ ] **Step 1: Write the sync script**

Create `tools/scripts/sync-hf-skills.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Sync vendored HyperFrames skills from the latest npm tarball.
# Writes the resolved version to tools/hyperframes-skills/VERSION.
# Run on demand when HyperFrames updates and we want their newer skill text.

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SKILLS_DIR="$REPO_ROOT/tools/hyperframes-skills"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

VERSION="$(npm view hyperframes version)"
TARBALL_URL="$(npm view hyperframes dist.tarball)"

echo "Syncing hyperframes@$VERSION skills from $TARBALL_URL"
curl -sL "$TARBALL_URL" | tar xz -C "$TMP_DIR"

[ -d "$TMP_DIR/package/dist/skills" ] || {
  echo "ERROR: tarball has no dist/skills/ — HF may have changed layout"
  exit 1
}

rm -rf "$SKILLS_DIR"
mkdir -p "$SKILLS_DIR"
cp -r "$TMP_DIR/package/dist/skills/." "$SKILLS_DIR/"
echo "$VERSION" > "$SKILLS_DIR/VERSION"

echo "Done. Vendored at $SKILLS_DIR (version $VERSION)."
```

```bash
chmod +x tools/scripts/sync-hf-skills.sh
```

- [ ] **Step 2: Run the sync once**

```bash
bash tools/scripts/sync-hf-skills.sh
```

Expected: `Syncing hyperframes@0.4.31 skills from ...` then `Done. Vendored at .../tools/hyperframes-skills (version 0.4.31).`

- [ ] **Step 3: Verify the vendored layout**

```bash
ls tools/hyperframes-skills/
cat tools/hyperframes-skills/VERSION
ls tools/hyperframes-skills/hyperframes/SKILL.md tools/hyperframes-skills/gsap/SKILL.md tools/hyperframes-skills/hyperframes-cli/SKILL.md
```

Expected: three subdirs (`gsap`, `hyperframes`, `hyperframes-cli`); `VERSION` reads `0.4.31`; all three SKILL.md files exist.

- [ ] **Step 4: Commit**

```bash
git add tools/scripts/sync-hf-skills.sh tools/hyperframes-skills/
git commit -m "feat(phase-6a): vendor HyperFrames skills at v0.4.31

Read-only mirror of dist/skills/ from the npm tarball. Coding subagents
in Phase 6b read SKILL.md / references / palettes / scripts from this
directory, decoupling agent runtime from npx hyperframes skills which
is interactive and fragile in headless contexts.

Refresh via tools/scripts/sync-hf-skills.sh.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: Update standards documents

**Files:**
- Modify: `standards/motion-graphics.md` (rewrite the WATCH catalog section)
- Modify: `standards/pipeline-contracts.md` (Stage 2 output contract update)
- Modify: `standards/captions.md` (add HF references pointer)
- Modify: `AGENTS.md` (file-location quick map)

- [ ] **Step 1: Rewrite WATCH catalog in `standards/motion-graphics.md`**

Find the section starting `## Scene-mode → component catalog (WATCH)` and ending before `## Hard rules`. Replace its body with:

```markdown
## Scene-mode → component catalog (WATCH)
Working catalog of which graphic sources each scene mode admits as of
2026-04-28. Will harden into a hard rule once the agentic planner
exists (Phase 6b). The list is not frozen — Phase 6b refines it
based on real seam-by-seam tests.

| Scene mode | Allowed sources                                                                                                       |
|---|---|
| `head`     | (none — talking-head only)                                                                                             |
| `split`    | `bespoke` via `split-frame` shell (shell ships in 6b; not available in 6a)                                            |
| `broll`    | `bespoke` ∪ catalog: `data-chart`, `flowchart`, `logo-outro`, `app-showcase`, `ui-3d-reveal`                          |
| `overlay`  | `bespoke` via `overlay-plate` shell (shell ships in 6b) ∪ catalog: `yt-lower-third`, `instagram-follow`, `tiktok-follow`, `x-post`, `reddit-post`, `spotify-card`, `macos-notification` |

`bespoke` means a per-seam HTML sub-composition written by a coding
subagent into `episodes/<slug>/stage-2-composite/compositions/seam-<id>.html`,
following the HyperFrames skill methodology vendored at
`tools/hyperframes-skills/hyperframes/`. Catalog entries are HF
registry blocks installed via `npx hyperframes add <name>`.

A compositor lint that warns when a `split` / `overlay` / `broll`
seam has no graphic, and rejects components outside the allowed set,
is part of Phase 6b.
```

- [ ] **Step 1b: Update Hard rules in the same file (`standards/motion-graphics.md`)**

Find the `## Hard rules` section. Replace this bullet:

```
- Components live in `design-system/components/`. Never inline raw HTML in `composition.html` — always reference a component template.
- All component styling reads from `design-system/tokens/tokens.json` via CSS variables. No hardcoded color/size/blur values.
```

With:

```
- Per-seam graphics live in `episodes/<slug>/stage-2-composite/compositions/seam-<id>.html` as HyperFrames sub-compositions. Layout shells (`split-frame`, `overlay-plate`) live in `design-system/components/` and are populated during Phase 6b. The compositor never inlines raw HTML in `index.html` — it references sub-compositions via `data-composition-src`.
- All composition styling reads CSS variables emitted from the `hyperframes-tokens` JSON block in `DESIGN.md` at the repo root. No hardcoded color/size/blur values; no parallel token files.
```

- [ ] **Step 2: Update Stage 2 output contract in `standards/pipeline-contracts.md`**

Open the file and locate the Stage 2 section (search for "Stage 2"). Append this paragraph at the bottom of the section (keep existing content intact):

```markdown
### Stage 2 output (post Phase 6a)
Stage 2 emits a HyperFrames-canonical project rooted at
`episodes/<slug>/stage-2-composite/index.html`, with sub-compositions
under `episodes/<slug>/stage-2-composite/compositions/`. The previous
`hf-project/` staging directory is removed; `index.html` is the
canonical entry consumed directly by `npx hyperframes lint /
validate / inspect / render`. Captions live at
`compositions/captions.html`; per-seam bespoke graphics (when present,
Phase 6b onward) live at `compositions/seam-<id>.html`.
```

- [ ] **Step 3: Add HF references pointer to `standards/captions.md`**

Open the file and find a stable section (e.g., the end of the editorial typography rules, or a section called "Implementation"). Append:

```markdown
## Technical implementation
This standard is the editorial layer (typography, position, karaoke
timing rules, anti-patterns specific to this channel). The technical
implementation pattern — per-word entrance/exit guarantees,
tone-adaptive styling, overflow prevention — follows HyperFrames'
`references/captions.md` (vendored at
`tools/hyperframes-skills/hyperframes/references/captions.md`). When
authoring or modifying captions, read both files together.
```

- [ ] **Step 4: Update `AGENTS.md` file-location map**

Find the section `## File-location quick map`. Update these lines:

Replace:
```
- Brand tokens           → `design-system/tokens/tokens.json`
- Reusable HF components → `design-system/components/`
```

With:
```
- Visual contract         → `DESIGN.md` (repo root; fenced `hyperframes-tokens` JSON block is the only machine-parsed region)
- HF skills (vendored)    → `tools/hyperframes-skills/` (refresh via `tools/scripts/sync-hf-skills.sh`)
- Layout shells           → `design-system/components/` (currently empty in 6a; populated in 6b)
```

- [ ] **Step 5: Commit standards updates**

```bash
git add standards/motion-graphics.md standards/pipeline-contracts.md standards/captions.md AGENTS.md
git commit -m "docs(phase-6a): update standards for HF-native foundation

Rewrite WATCH catalog with real HF registry names + bespoke marker.
Add Stage 2 output contract pointing at canonical index.html.
Reference HF captions pattern from standards/captions.md.
Update AGENTS.md file map: DESIGN.md replaces tokens, HF skills vendored.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: Add DESIGN.md parser to compositor

**Files:**
- Create: `tools/compositor/src/designMd.ts`
- Create: `tools/compositor/test/designMd.test.ts`
- Create: `tools/compositor/test/fixtures/design-minimal.md`

We replace `tokens.ts` (which reads JSON) with a parallel module that reads the fenced JSON block from `DESIGN.md`. Keep `tokens.ts` in place for now; remove it in Task 10 once nothing references it.

- [ ] **Step 1: Write the test fixture**

Create `tools/compositor/test/fixtures/design-minimal.md`:

````markdown
# DESIGN.md — fixture

## Style Prompt

A minimal fixture for testing the parser.

## Colors

```json hyperframes-tokens
{
  "color": { "text": { "primary": "#FFFFFF" } },
  "spacing": { "md": "24px" }
}
```

## What NOT to Do
- Nothing here.
````

- [ ] **Step 2: Write the failing test**

Create `tools/compositor/test/designMd.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseDesignMd, designMdToCss } from "../src/designMd.js";
import { readFileSync } from "node:fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.join(__dirname, "fixtures", "design-minimal.md");

describe("parseDesignMd", () => {
  it("extracts the hyperframes-tokens fenced JSON block", () => {
    const md = readFileSync(FIXTURE, "utf8");
    const tree = parseDesignMd(md);
    expect(tree).toEqual({
      color: { text: { primary: "#FFFFFF" } },
      spacing: { md: "24px" },
    });
  });

  it("throws when no hyperframes-tokens block is present", () => {
    expect(() => parseDesignMd("# no block here")).toThrow(/hyperframes-tokens/);
  });

  it("throws when JSON is malformed", () => {
    const bad = "```json hyperframes-tokens\n{ not json\n```";
    expect(() => parseDesignMd(bad)).toThrow(/JSON/);
  });
});

describe("designMdToCss", () => {
  it("flattens nested keys into kebab-cased CSS variables", () => {
    const css = designMdToCss({ color: { text: { primary: "#FFFFFF" } }, spacing: { md: "24px" } });
    expect(css).toContain("--color-text-primary: #FFFFFF;");
    expect(css).toContain("--spacing-md: 24px;");
    expect(css.startsWith(":root {")).toBe(true);
    expect(css.trimEnd().endsWith("}")).toBe(true);
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
cd tools/compositor && npx vitest run test/designMd.test.ts
```

Expected: FAIL — "Cannot find module '../src/designMd.js'".

- [ ] **Step 4: Implement the parser**

Create `tools/compositor/src/designMd.ts`:

```typescript
import { readFileSync } from "node:fs";

export type TokenTree = { [k: string]: TokenTree | string | number };

const FENCE_RE = /```json\s+hyperframes-tokens\s*\n([\s\S]*?)\n```/m;

export function parseDesignMd(markdown: string): TokenTree {
  const match = markdown.match(FENCE_RE);
  if (!match) {
    throw new Error("DESIGN.md: no fenced `hyperframes-tokens` JSON block found");
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(match[1]);
  } catch (e) {
    throw new Error(`DESIGN.md: hyperframes-tokens block is not valid JSON: ${(e as Error).message}`);
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error("DESIGN.md: hyperframes-tokens block must be a JSON object");
  }
  return parsed as TokenTree;
}

export function loadDesignMd(filePath: string): TokenTree {
  return parseDesignMd(readFileSync(filePath, "utf8"));
}

function flatten(obj: TokenTree, prefix: string, out: Record<string, string | number>): void {
  for (const [key, value] of Object.entries(obj)) {
    const name = prefix ? `${prefix}-${key}` : key;
    if (value !== null && typeof value === "object") {
      flatten(value as TokenTree, name, out);
    } else {
      out[name] = value as string | number;
    }
  }
}

export function designMdToCss(tree: TokenTree): string {
  const flat: Record<string, string | number> = {};
  flatten(tree, "", flat);
  const lines = [":root {"];
  for (const [name, value] of Object.entries(flat)) {
    lines.push(`  --${name}: ${value};`);
  }
  lines.push("}");
  lines.push("");
  return lines.join("\n");
}
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
cd tools/compositor && npx vitest run test/designMd.test.ts
```

Expected: PASS, 4 tests green.

- [ ] **Step 6: Commit**

```bash
git add tools/compositor/src/designMd.ts tools/compositor/test/designMd.test.ts tools/compositor/test/fixtures/design-minimal.md
git commit -m "feat(compositor): add DESIGN.md parser

Extracts the fenced \`hyperframes-tokens\` JSON block from DESIGN.md
and emits CSS :root variables in the same shape as the legacy
tokens.json path. tokens.ts remains until composer.ts switches over.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: Rewrite composer to emit HF-canonical root index.html

**Files:**
- Modify: `tools/compositor/src/composer.ts` (significant rewrite)
- Modify: `tools/compositor/src/index.ts` (filenames + DESIGN.md path)
- Create: `tools/compositor/src/captionsComposition.ts` (sub-composition emitter)
- Modify: `tools/compositor/test/composer.test.ts` (rewrite expectations)

- [ ] **Step 1: Inspect current composer test to understand current shape**

```bash
cat tools/compositor/test/composer.test.ts
```

Note the existing assertions; the rewrite changes nearly all of them.

- [ ] **Step 2: Replace `composer.test.ts` with new expectations**

Overwrite `tools/compositor/test/composer.test.ts` with:

```typescript
import { describe, it, expect } from "vitest";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildRootIndexHtml } from "../src/composer.js";
import type { SeamPlan, MasterBundle } from "../src/types.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const designMdPath = path.join(__dirname, "fixtures", "design-minimal.md");

const bundle: MasterBundle = {
  slug: "fixture",
  master: { durationMs: 60_000 },
  transcript: { words: [{ text: "hi", startMs: 100, endMs: 400 }] },
  boundaries: [],
} as unknown as MasterBundle;

const plan: SeamPlan = {
  episode_slug: "fixture",
  master_duration_ms: 60_000,
  seams: [
    { index: 1, at_ms: 0, ends_at_ms: 30_000, scene_mode: "head" },
    { index: 2, at_ms: 30_000, ends_at_ms: 60_000, scene_mode: "broll" },
  ],
} as unknown as SeamPlan;

describe("buildRootIndexHtml", () => {
  const html = buildRootIndexHtml({
    designMdPath,
    plan,
    bundle,
    masterRelPath: "../stage-1-cut/master.mp4",
    existingSeamFiles: new Set<number>([2]),
  });

  it("declares root composition with correct dimensions and duration", () => {
    expect(html).toContain('data-composition-id="root"');
    expect(html).toContain('data-width="1440"');
    expect(html).toContain('data-height="2560"');
    expect(html).toContain('data-duration="60.000"');
  });

  it("inlines :root CSS variables from the DESIGN.md fenced block", () => {
    expect(html).toContain("--color-text-primary: #FFFFFF;");
    expect(html).toContain("--spacing-md: 24px;");
  });

  it("emits a muted video track and a separate audio track for master.mp4", () => {
    expect(html).toContain('src="../stage-1-cut/master.mp4"');
    expect(html).toMatch(/<video[^>]*muted/);
    expect(html).toMatch(/<audio[^>]*data-volume="1"/);
  });

  it("loads the captions sub-composition for the full duration", () => {
    expect(html).toMatch(/data-composition-src="compositions\/captions\.html"[^>]*data-start="0"[^>]*data-duration="60\.000"/);
  });

  it("loads per-seam sub-compositions only when their file exists", () => {
    expect(html).toContain('data-composition-src="compositions/seam-2.html"');
    expect(html).not.toContain('data-composition-src="compositions/seam-1.html"');
  });

  it("places per-seam sub-composition at the seam window in seconds", () => {
    expect(html).toMatch(/data-composition-src="compositions\/seam-2\.html"[^>]*data-start="30\.000"[^>]*data-duration="30\.000"/);
  });

  it("uses distinct track indexes per layered element (no collisions)", () => {
    const trackIndexes = [...html.matchAll(/data-track-index="(\d+)"/g)].map((m) => Number(m[1]));
    expect(new Set(trackIndexes).size).toBe(trackIndexes.length);
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
cd tools/compositor && npx vitest run test/composer.test.ts
```

Expected: FAIL — `buildRootIndexHtml` not exported.

- [ ] **Step 4: Write `captionsComposition.ts`**

Create `tools/compositor/src/captionsComposition.ts`:

```typescript
import type { MasterBundle } from "./types.js";

export interface CaptionsArgs {
  bundle: MasterBundle;
}

export function buildCaptionsCompositionHtml(args: CaptionsArgs): string {
  const totalSec = (Math.round(args.bundle.master.durationMs) / 1000).toFixed(3);
  const wordsForRuntime = args.bundle.transcript.words.map((w) => ({
    text: w.text,
    start_ms: w.startMs,
    end_ms: w.endMs,
  }));
  return `<template id="captions-template">
<div data-composition-id="captions" data-width="1440" data-height="2560">
  <style>
    [data-composition-id="captions"] { width: 100%; height: 100%; position: relative; }
    [data-composition-id="captions"] .caption-row {
      position: absolute;
      left: var(--safezone-side, 6%);
      right: var(--safezone-side, 6%);
      bottom: var(--safezone-bottom, 22%);
      text-align: center;
      font-family: var(--type-family-caption, system-ui);
      font-size: var(--type-size-caption, 64px);
      font-weight: var(--type-weight-bold, 700);
      line-height: 1.2;
    }
    [data-composition-id="captions"] .word {
      display: inline-block;
      margin: 0 0.18em;
      color: var(--color-caption-inactive, rgba(255,255,255,0.55));
    }
    [data-composition-id="captions"] .word.active {
      color: var(--color-caption-active, #FFFFFF);
    }
  </style>
  <div class="caption-row" id="captions-row"></div>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <script>
    (function () {
      var WORDS = ${JSON.stringify(wordsForRuntime)};
      var row = document.getElementById("captions-row");
      WORDS.forEach(function (w, i) {
        var span = document.createElement("span");
        span.className = "word";
        span.dataset.start = w.start_ms;
        span.dataset.end = w.end_ms;
        span.textContent = w.text;
        row.appendChild(span);
      });
      window.__timelines = window.__timelines || {};
      var tl = gsap.timeline({ paused: true });
      WORDS.forEach(function (w, i) {
        var sel = ".word:nth-child(" + (i + 1) + ")";
        tl.set(sel, { className: "+=active" }, w.start_ms / 1000);
        tl.set(sel, { className: "-=active" }, w.end_ms / 1000);
      });
      tl.to({}, { duration: ${totalSec} }, 0);
      window.__timelines["captions"] = tl;
    })();
  </script>
</div>
</template>`;
}
```

- [ ] **Step 5: Rewrite `composer.ts`**

Overwrite `tools/compositor/src/composer.ts` with:

```typescript
import { writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import type { SeamPlan, MasterBundle } from "./types.js";
import { loadDesignMd, designMdToCss } from "./designMd.js";
import { buildCaptionsCompositionHtml } from "./captionsComposition.js";

export interface ComposeArgs {
  designMdPath: string;
  plan: SeamPlan;
  bundle: MasterBundle;
  masterRelPath: string;
  existingSeamFiles: Set<number>;
}

const ROOT_WIDTH = 1440;
const ROOT_HEIGHT = 2560;
const TRACK_VIDEO = 0;
const TRACK_CAPTIONS = 1;
const TRACK_AUDIO = 2;
const TRACK_SEAM_BASE = 3;

function msToSeconds(ms: number): string {
  return (Math.round(ms) / 1000).toFixed(3);
}

export function buildRootIndexHtml(args: ComposeArgs): string {
  const tree = loadDesignMd(args.designMdPath);
  const css = designMdToCss(tree);
  const masterDurationSec = msToSeconds(args.bundle.master.durationMs);

  const seamFragments = args.plan.seams
    .filter((s) => args.existingSeamFiles.has(s.index))
    .map((s, i) => {
      const startSec = msToSeconds(s.at_ms);
      const durationSec = msToSeconds(s.ends_at_ms - s.at_ms);
      const trackIndex = TRACK_SEAM_BASE + i;
      return `<div class="clip"
     data-composition-src="compositions/seam-${s.index}.html"
     data-composition-id="seam-${s.index}"
     data-start="${startSec}"
     data-duration="${durationSec}"
     data-width="${ROOT_WIDTH}"
     data-height="${ROOT_HEIGHT}"
     data-track-index="${trackIndex}"></div>`;
    });

  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
${css}
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: ${ROOT_WIDTH}px; height: ${ROOT_HEIGHT}px; background: var(--color-bg-transparent); color: var(--color-text-primary); font-family: var(--type-family-caption); overflow: hidden; }
</style>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
</head>
<body>
<div id="root"
     data-composition-id="root"
     data-start="0"
     data-duration="${masterDurationSec}"
     data-width="${ROOT_WIDTH}"
     data-height="${ROOT_HEIGHT}">
<video id="master-video"
       class="clip"
       data-start="0"
       data-duration="${masterDurationSec}"
       data-track-index="${TRACK_VIDEO}"
       muted
       playsinline
       src="${args.masterRelPath}"></video>
<audio id="master-audio"
       class="clip"
       data-start="0"
       data-duration="${masterDurationSec}"
       data-track-index="${TRACK_AUDIO}"
       data-volume="1"
       src="${args.masterRelPath}"></audio>
<div class="clip"
     data-composition-src="compositions/captions.html"
     data-composition-id="captions"
     data-start="0"
     data-duration="${masterDurationSec}"
     data-width="${ROOT_WIDTH}"
     data-height="${ROOT_HEIGHT}"
     data-track-index="${TRACK_CAPTIONS}"></div>
${seamFragments.join("\n")}
<script>
(function () {
  if (typeof gsap === "undefined") return;
  window.__timelines = window.__timelines || {};
  var tl = gsap.timeline({ paused: true });
  tl.to({}, { duration: ${masterDurationSec} });
  window.__timelines["root"] = tl;
})();
</script>
</div>
</body>
</html>`;
}

export interface WriteCompositionArgs extends ComposeArgs {
  episodeDir: string;
}

export function writeCompositionFiles(args: WriteCompositionArgs): { indexPath: string; captionsPath: string } {
  const compositeDir = path.join(args.episodeDir, "stage-2-composite");
  const compositionsDir = path.join(compositeDir, "compositions");
  mkdirSync(compositionsDir, { recursive: true });

  const indexPath = path.join(compositeDir, "index.html");
  const captionsPath = path.join(compositionsDir, "captions.html");

  writeFileSync(indexPath, buildRootIndexHtml(args));
  writeFileSync(captionsPath, buildCaptionsCompositionHtml({ bundle: args.bundle }));

  return { indexPath, captionsPath };
}
```

- [ ] **Step 6: Update `index.ts` to call the new composer and discover seam files**

Replace `tools/compositor/src/index.ts` with:

```typescript
#!/usr/bin/env node
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { planSeams } from "./seamPlanner.js";
import { writeSeamPlan, readSeamPlan } from "./seamPlanWriter.js";
import { writeCompositionFiles } from "./composer.js";
import { loadBundle } from "./stage2/loadBundle.js";
import { writeFileSync } from "node:fs";

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
  if (existingSeamFiles.size > 0) {
    console.log(`Wired ${existingSeamFiles.size} per-seam sub-composition(s): ${[...existingSeamFiles].join(", ")}`);
  }
} else if (cmd === "render") {
  console.error("Use tools/scripts/render-final.sh <slug> for final render.");
  process.exit(2);
} else {
  usage();
}
```

- [ ] **Step 7: Run all compositor tests**

```bash
cd tools/compositor && npx vitest run
```

Expected: all tests pass. The old `composer.test.ts` content has been replaced with the new expectations from Step 2.

If `tokens.test.ts` still references types or functions that no longer exist on the new path, do not touch it now — `tokens.ts` itself remains in tree until Task 10. The tests must keep passing.

- [ ] **Step 8: Commit**

```bash
git add tools/compositor/src/composer.ts tools/compositor/src/captionsComposition.ts tools/compositor/src/index.ts tools/compositor/test/composer.test.ts
git commit -m "refactor(compositor): emit HF-canonical root index.html with sub-compositions

Compositor now reads DESIGN.md (fenced JSON block) and emits:
- episodes/<slug>/stage-2-composite/index.html as the HF root
- compositions/captions.html as a sub-composition (HF <template> + scoped styles)
- per-seam <div data-composition-src> entries for any compositions/seam-<id>.html
  files present at compose time

Captions still consume the same word list from master/bundle.json; per-frame
timing is preserved within ±1 frame.

tokens.json/tokens.ts remain in tree; deletion is in a later task once nothing
references them.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: Adapt run-stage2-compose.sh and run-stage2-preview.sh

**Files:**
- Modify: `tools/scripts/run-stage2-compose.sh`
- Modify: `tools/scripts/run-stage2-preview.sh`

- [ ] **Step 1: Rewrite `run-stage2-compose.sh`**

Overwrite the file with:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Stage 2a: produce seam-plan.md (CP2.5), root index.html, and the
# captions sub-composition for a given episode slug. Does NOT render
# preview.mp4.
#
# Usage: tools/scripts/run-stage2-compose.sh <slug>

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <slug>"
  exit 1
fi

SLUG="$1"
REPO_ROOT="$(pwd)"
EPISODE="$REPO_ROOT/episodes/$SLUG"
COMPOSITE_DIR="$EPISODE/stage-2-composite"

[ -d "$EPISODE" ]                              || { echo "ERROR: $EPISODE not found"; exit 1; }
[ -f "$EPISODE/stage-1-cut/master.mp4" ]       || { echo "ERROR: master.mp4 missing"; exit 1; }
[ -f "$EPISODE/master/bundle.json" ]           || { echo "ERROR: master/bundle.json missing"; exit 1; }
[ -f "$REPO_ROOT/DESIGN.md" ]                  || { echo "ERROR: $REPO_ROOT/DESIGN.md missing"; exit 1; }

mkdir -p "$COMPOSITE_DIR"

# Step 1: seam-plan (CP2.5)
REPO_ROOT="$REPO_ROOT" npx -y tsx tools/compositor/src/index.ts seam-plan --episode "$EPISODE"
echo "CP2.5 ready: $COMPOSITE_DIR/seam-plan.md. Awaiting review."

# Step 2: emit root index.html + captions sub-composition + per-seam wires
REPO_ROOT="$REPO_ROOT" npx tsx tools/compositor/src/index.ts compose --episode "$EPISODE"

# Step 3: HyperFrames lint + validate + inspect against the canonical
# project (index.html lives directly under stage-2-composite/).
npx -y hyperframes lint "$COMPOSITE_DIR"      || { echo "ERROR: hyperframes lint failed"; exit 1; }
npx hyperframes validate "$COMPOSITE_DIR"     || { echo "ERROR: hyperframes validate failed"; exit 1; }
npx hyperframes inspect "$COMPOSITE_DIR" --json > "$COMPOSITE_DIR/.inspect.json" || {
  echo "ERROR: hyperframes inspect failed; see $COMPOSITE_DIR/.inspect.json"
  exit 1
}

# Step 4: animation-map (informational; does not gate). Outputs JSON for
# review during smoke tests and Phase 6b agent iteration.
ANIM_MAP_SCRIPT="$REPO_ROOT/tools/hyperframes-skills/hyperframes/scripts/animation-map.mjs"
if [ -f "$ANIM_MAP_SCRIPT" ]; then
  node "$ANIM_MAP_SCRIPT" "$COMPOSITE_DIR" --out "$COMPOSITE_DIR/.hyperframes/anim-map" || {
    echo "WARN: animation-map errored; continuing"
  }
fi

echo "Compose ready: $COMPOSITE_DIR/index.html. Run run-stage2-preview.sh next."
```

- [ ] **Step 2: Rewrite `run-stage2-preview.sh`**

Open the existing file, identify the `hyperframes render` invocation. Adapt it so it points at `$COMPOSITE_DIR` (or whatever variable holds the episode's `stage-2-composite/`) instead of the now-removed `hf-project/`. Concretely:

Replace any line like:
```
npx hyperframes render "$COMPOSITE_DIR/hf-project" -f 60 -q draft --output "$COMPOSITE_DIR/preview.mp4"
```
with:
```
npx hyperframes render "$COMPOSITE_DIR" -f 60 -q draft --output "$COMPOSITE_DIR/preview.mp4"
```

Remove any `rm -rf "$COMPOSITE_DIR/hf-project"` or staging-related lines that referenced `hf-project/`. Keep everything else (slug parsing, error guards, final echo).

- [ ] **Step 3: Update `render-final.sh` similarly**

Open `tools/scripts/render-final.sh`. Replace any `hf-project` reference with the parent `stage-2-composite/` directory. Keep the music-merge ffmpeg pass exactly as is — its inputs are `preview.mp4` and `library/music/<track>.mp3`, neither of which moved.

- [ ] **Step 4: Smoke-syntax check the scripts**

```bash
bash -n tools/scripts/run-stage2-compose.sh
bash -n tools/scripts/run-stage2-preview.sh
bash -n tools/scripts/render-final.sh
```

Expected: no output (clean parse on all three).

- [ ] **Step 5: Commit**

```bash
git add tools/scripts/run-stage2-compose.sh tools/scripts/run-stage2-preview.sh tools/scripts/render-final.sh
git commit -m "refactor(stage2): scripts target HF-canonical project layout

Drops the hf-project/ staging directory entirely; index.html now lives
under stage-2-composite/ directly and HyperFrames render/lint/validate/
inspect read it from there.

Adds validate, inspect, and animation-map steps to run-stage2-compose.sh:
lint+validate+inspect gate the build; animation-map is informational.

Requires DESIGN.md at repo root (compose now hard-fails without it).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: Delete deprecated files

**Files:**
- Delete: `design-system/tokens/tokens.json`
- Delete: `design-system/tokens/` (directory, if empty after the file is gone)
- Delete: `design-system/components/glass-card.html`
- Delete: `design-system/components/title-card.html`
- Delete: `design-system/components/overlay-plate.html`
- Delete: `design-system/components/fullscreen-broll.html`
- Delete: `design-system/components/caption-karaoke.html`
- Delete: `design-system/components/split-frame.html` (will be re-authored as HF sub-composition in 6b; current file is not salvageable)
- Audit/Delete: `design-system/components/_base.css`
- Delete: `tools/compositor/src/tokens.ts`
- Delete: `tools/compositor/test/tokens.test.ts`
- Modify or delete: `tools/compositor/src/components.ts` (audit usage)

- [ ] **Step 1: Verify nothing imports `tokens.ts` or `components.ts`**

```bash
grep -rn "from.*['\"].*tokens\.js['\"]" tools/compositor/src tools/compositor/test
grep -rn "from.*['\"].*components\.js['\"]" tools/compositor/src tools/compositor/test
```

Expected: only `tokens.test.ts` references `tokens.js`; no live source under `src/` references either after Task 5. If anything else references them, fix the importer before deleting.

- [ ] **Step 2: Delete the dead source files**

```bash
git rm design-system/tokens/tokens.json
git rm design-system/components/glass-card.html
git rm design-system/components/title-card.html
git rm design-system/components/overlay-plate.html
git rm design-system/components/fullscreen-broll.html
git rm design-system/components/caption-karaoke.html
git rm design-system/components/split-frame.html
git rm tools/compositor/src/tokens.ts
git rm tools/compositor/test/tokens.test.ts
git rm tools/compositor/src/components.ts
```

- [ ] **Step 3: Audit `_base.css`**

Compare the contents of `design-system/components/_base.css` (read it from git history if needed: `git show HEAD~1:design-system/components/_base.css`) against the inline `<style>` block in the new `composer.ts` (the html/body/* rules around line ~50 of the new `buildRootIndexHtml`). Confirm the rules already covered: `* { box-sizing }`, `html/body width/height`, `background`, `color`, `font-family`, `overflow: hidden`. The `.glass` and `.safe-bottom`/`.safe-top` helper classes from `_base.css` are NOT in the inline block — but they were only used by the deleted homemade components and are not referenced from `index.html` or `captions.html`. Safe to delete.

```bash
git rm design-system/components/_base.css
```

- [ ] **Step 4: Remove empty parent directories**

```bash
rmdir design-system/tokens 2>/dev/null || true
rmdir design-system/components 2>/dev/null || true
ls design-system/
```

If `components/` and `tokens/` are now gone, `design-system/` will hold only `README.md`. That's fine for 6a; `components/` will be repopulated with HF-canonical layout shells in 6b.

- [ ] **Step 5: Update `design-system/README.md` to reflect 6a state**

Append a short note at the bottom:

```markdown
---

## Phase 6a state (2026-04-28)

`tokens/` and `components/` were emptied during the HF-native foundation
refactor. The visual contract now lives at the repo-root `DESIGN.md`; the
compositor parses its `hyperframes-tokens` JSON block to emit CSS
variables. Layout-shell sub-compositions (`split-frame`, `overlay-plate`)
will be re-authored here as HyperFrames sub-compositions during Phase 6b.
```

- [ ] **Step 6: Run all compositor tests to confirm nothing broke**

```bash
cd tools/compositor && npx vitest run
```

Expected: all tests pass. If any test file fails to import a deleted module, the test file should also be deleted (or the import fixed).

- [ ] **Step 7: Commit**

```bash
git add -u
git add design-system/README.md
git commit -m "refactor(phase-6a): delete tokens.json and homemade component templates

Files removed (replaced by DESIGN.md + HF-canonical sub-compositions):
- design-system/tokens/tokens.json
- design-system/components/{glass-card,title-card,overlay-plate,fullscreen-broll,caption-karaoke,split-frame}.html
- design-system/components/_base.css (helpers were only used by deleted templates)
- tools/compositor/src/{tokens.ts,components.ts}
- tools/compositor/test/tokens.test.ts

split-frame and overlay-plate will be re-authored as HF-canonical layout
shells in Phase 6b.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 8: Smoke fixture — synthetic seam sub-composition

**Files:**
- Identify or create: a test episode (the pilot is FROZEN; use the next real episode if one exists, otherwise create a fresh fixture episode by copying the pilot's `master.mp4` and `bundle.json` into a new slug).
- Create: `episodes/<test-slug>/stage-2-composite/compositions/seam-<id>.html`

- [ ] **Step 1: Pick the test episode**

Run:

```bash
ls episodes/
```

If a non-frozen episode exists (anything other than `2026-04-27-desktop-software-licensing-it-turns-out`), use it. Otherwise create a copy of the pilot under a new slug — but **do not edit anything inside the pilot directory**, since the pilot is FROZEN per project rules:

```bash
cp -r episodes/2026-04-27-desktop-software-licensing-it-turns-out episodes/2026-04-28-phase-6a-smoke-test
```

(If you copy, the smoke-test slug is `2026-04-28-phase-6a-smoke-test` and that's what subsequent commands target. If you reuse a real episode, substitute its slug.)

Set the slug as a variable for the rest of the task:

```bash
TEST_SLUG="2026-04-28-phase-6a-smoke-test"   # or the real episode slug
```

- [ ] **Step 2: Pick a non-`head` seam to attach the synthetic graphic to**

```bash
cat "episodes/$TEST_SLUG/stage-2-composite/seam-plan.md"
```

Find a seam with `scene_mode: broll` (preferred — full-canvas, no shell required). Note its `index`. Call it `<seam-idx>`.

If no `broll` seam exists in the chosen episode, find any non-`head` seam; the synthetic graphic still works because it's full-canvas regardless.

- [ ] **Step 3: Write the synthetic sub-composition**

Create `episodes/$TEST_SLUG/stage-2-composite/compositions/seam-<seam-idx>.html` (substituting the actual seam index in the filename):

```html
<template id="seam-smoke-template">
<div data-composition-id="seam-smoke" data-width="1440" data-height="2560">
  <style>
    [data-composition-id="seam-smoke"] {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: transparent;
    }
    [data-composition-id="seam-smoke"] .plate {
      background: var(--color-glass-fill, rgba(255,255,255,0.18));
      border: 1px solid var(--color-glass-stroke, rgba(255,255,255,0.32));
      box-shadow: 0 8px 32px var(--color-glass-shadow, rgba(0,0,0,0.35));
      backdrop-filter: blur(var(--blur-glass-md, 24px));
      border-radius: var(--radius-lg, 44px);
      padding: var(--spacing-xl, 64px);
      font-family: var(--type-family-display, 'Inter Display', sans-serif);
      font-weight: 900;
      font-size: var(--type-size-title, 96px);
      color: var(--color-text-primary, #FFFFFF);
      letter-spacing: 0.02em;
      text-align: center;
    }
  </style>
  <div class="plate" id="smoke-plate">6A WIRING OK</div>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <script>
    (function () {
      window.__timelines = window.__timelines || {};
      var tl = gsap.timeline({ paused: true });
      tl.from("#smoke-plate", { scale: 0.85, opacity: 0, duration: 0.5, ease: "power3.out" }, 0.2);
      window.__timelines["seam-smoke"] = tl;
    })();
  </script>
</div>
</template>
```

- [ ] **Step 4: Commit the fixture**

```bash
git add "episodes/$TEST_SLUG"
git commit -m "test(phase-6a): smoke fixture with synthetic seam sub-composition

A bespoke '6A WIRING OK' frosted-glass plate on one non-head seam,
authored as an HF-canonical sub-composition. Used to verify the new
compositor wires per-seam sub-compositions correctly before Phase 6b
introduces a coding subagent.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 9: Run smoke test, verify acceptance, tag

**Files:**
- Modify: `standards/retro-changelog.md` (append entry)

- [ ] **Step 1: Run the new compose pipeline**

```bash
bash tools/scripts/run-stage2-compose.sh "$TEST_SLUG"
```

Expected output: seam-plan written, then index.html + compositions/captions.html + "Wired 1 per-seam sub-composition(s): <idx>", then `lint`/`validate`/`inspect` all pass, then `animation-map` produces JSON without erroring. Final line: `Compose ready: …/index.html. Run run-stage2-preview.sh next.`

If any step fails, do NOT proceed — diagnose and fix the underlying issue. Common failure modes:
- `lint`: composition references unknown attribute → check generated HTML in `episodes/$TEST_SLUG/stage-2-composite/index.html`.
- `validate`: contrast warning → adjust palette in `DESIGN.md` (caution: this is editorial, defer to host before changing).
- `inspect`: text overflow → the synthetic plate's font/padding combo overflows; reduce padding in the synthetic seam HTML.

- [ ] **Step 2: Render the preview**

```bash
bash tools/scripts/run-stage2-preview.sh "$TEST_SLUG"
```

Expected: `preview.mp4` produced under `episodes/$TEST_SLUG/stage-2-composite/preview.mp4`.

- [ ] **Step 3: Verify acceptance criteria**

Open the preview and check:
1. master.mp4 plays as the talking-head track.
2. Captions are present and synced ±1 frame to bundle.json words.
3. At the synthetic seam window (`at_ms`–`ends_at_ms` of the chosen seam), the "6A WIRING OK" frosted-glass plate appears with a 0.5s fade-in, holds, then disappears at the seam's end.
4. Other non-`head` seams render as plain head (no graphic on them — expected).
5. `lint`/`validate`/`inspect` were all green during compose.
6. No reference to `tokens.json` or the deleted components remains:

```bash
grep -rn "tokens\.json\|tokens\.ts\|caption-karaoke\.html\|glass-card\.html\|title-card\.html\|overlay-plate\.html\|fullscreen-broll\.html\|split-frame\.html" tools standards docs episodes 2>/dev/null | grep -v ".tmp\|node_modules\|.git" || echo "clean"
```

Expected: `clean` (no matches), or matches only under retro/changelog history (which is acceptable as the changelog is append-only).

- [ ] **Step 4: Append retro-changelog entry**

Open `standards/retro-changelog.md` and append (at the very end of the file, since the file is append-only):

```markdown

---

## 2026-04-28 — Phase 6a HF-native foundation

Stage 2 pipeline moved onto HyperFrames-canonical project layout:
- Single project-level `DESIGN.md` at repo root replaces
  `design-system/tokens/tokens.json`. The compositor parses a fenced
  `hyperframes-tokens` JSON block to emit `:root` CSS variables.
- Compositor emits `episodes/<slug>/stage-2-composite/index.html` with
  HF sub-compositions under `compositions/`. The `hf-project/` staging
  directory is gone; `index.html` is the canonical entry.
- Captions migrated from `caption-karaoke.html` to
  `compositions/captions.html` (HF sub-composition with `<template>`,
  scoped styles, registered timeline).
- Placeholder homemade components removed
  (`glass-card`, `title-card`, `overlay-plate`, `fullscreen-broll`,
  `split-frame`, `_base.css`); `split-frame` and `overlay-plate` will be
  re-authored as HF layout shells during Phase 6b.
- `hyperframes lint` + `validate` + `inspect` + `animation-map` wired
  into `run-stage2-compose.sh`.
- HF skills vendored at `tools/hyperframes-skills/` (v0.4.31), refresh
  via `tools/scripts/sync-hf-skills.sh`. Available to coding subagents
  in Phase 6b.

WATCH catalog in `standards/motion-graphics.md` rewritten to use real HF
registry block names (`yt-lower-third`, `data-chart`, `flowchart`, …) plus
the `bespoke` marker. The previous aspirational catalog
(`side-figure`, `code-block`, `chart`, `quote-card`, `lower-third`,
`subscribe-cta`, `name-plate`, `full-bleed-figure`, `b-roll-clip`) is
removed.

Spec: `docs/superpowers/specs/2026-04-28-phase-6a-hf-native-foundation-design.md`
Plan: `docs/superpowers/plans/2026-04-28-phase-6a-hf-native-foundation.md`
```

- [ ] **Step 5: Commit changelog**

```bash
git add standards/retro-changelog.md
git commit -m "retro(phase-6a): close HF-native foundation phase

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

- [ ] **Step 6: Tag**

```bash
git tag phase-6a-hf-native-foundation
git log --oneline -10
```

Expected: tag visible at the latest commit; the preceding ~9 commits trace through DESIGN.md, vendoring, standards, compositor refactor, scripts, deletions, fixture, and changelog.

- [ ] **Step 7: Surface completion to host**

Report to host: "Phase 6a closed. Tag `phase-6a-hf-native-foundation` placed at commit `<sha>`. Smoke test rendered with synthetic '6A WIRING OK' graphic on seam <idx> of `<TEST_SLUG>`. Pipeline validated through `lint`/`validate`/`inspect`/`animation-map`. Ready to brainstorm Phase 6b (agentic graphics planner) when you are."

---

## Self-review checklist

Before declaring the plan written, verify:

- [ ] Every spec section maps to a task: DESIGN.md (Task 1), HF skills vendor (Task 2), standards updates including WATCH catalog (Task 3), DESIGN.md parser (Task 4), compositor rewrite + captions migration (Task 5), script adaptation (Task 6), deletions (Task 7), smoke fixture (Task 8), acceptance + retro + tag (Task 9). All §1–§7 of the spec covered.
- [ ] No "TBD", "TODO", "implement later", or vague handwave steps.
- [ ] Function and file names consistent across tasks: `parseDesignMd` / `loadDesignMd` / `designMdToCss` / `buildRootIndexHtml` / `buildCaptionsCompositionHtml` / `writeCompositionFiles` are introduced once and referenced consistently.
- [ ] Each step ends with either a test command + expected outcome or a commit. No dangling state between tasks.
- [ ] Pilot freezing rule respected: Task 8 explicitly forbids editing inside the pilot directory; copies it if reuse is needed.
