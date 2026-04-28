# Phase 6a-aftermath Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the three confirmed HF-methodology divergences from the post-6a audit (captions, transitions, inspect gate), add operational guardrails (doctor preflight, Docker render mode, version-pinned HF upgrade procedure), close the alignment gaps surfaced by independent re-audits (single-track seams, literal hex on captured elements, layout-before-animation, scene phases, typography compensation, named palettes, fitTextFontSize formalisation, hyperframes.json + meta.json scaffolding), and clean up pre-HF rudiments — all in a single PR-able phase against the smoke-test fixture.

**Architecture:** Surgical edits to the existing Stage 2 compositor (`tools/compositor/src/`) + orchestration scripts (`tools/scripts/`) + project-level standards docs. No new architectural layers. The compositor stays as the transcript→seam-plan→HF-composition generator (HF init does not provide that layer). Two new sub-composition generators (`transitionsComposition.ts`, captions rewrite), a token resolver (literal hex), a shared shell preflight library (`lib/preflight.sh`), and three new docs (`hyperframes-upgrade.md`, `hyperframes-integration.md`, `standards/typography.md`, `standards/bespoke-seams.md`).

**Tech Stack:** TypeScript (compositor, vitest), Bash (orchestration scripts), Markdown (specs/standards), HyperFrames CLI 0.4.31 (lint/validate/inspect/animation-map/render/doctor). GSAP 3.14.2 in compositions. Docker for memory-safe rendering on Windows.

---

## File structure overview

**Created:**
- `tools/compositor/src/transitionsComposition.ts` — generator for `compositions/transitions.html`.
- `tools/compositor/src/groupWords.ts` — pure helper for caption word-grouping (extracted for testability).
- `tools/compositor/src/episodeMeta.ts` — emits `hyperframes.json` + `meta.json` for an episode dir.
- `tools/compositor/test/transitionsComposition.test.ts`
- `tools/compositor/test/groupWords.test.ts`
- `tools/compositor/test/episodeMeta.test.ts`
- `tools/scripts/lib/preflight.sh` — shared HF doctor preflight; sourced by compose/preview/render scripts.
- `docs/hyperframes-upgrade.md` — upgrade procedure.
- `docs/hyperframes-integration.md` — contract surface registry.
- `standards/typography.md` — weight/tracking/dark-bg compensation rules + Inter override rationale.
- `standards/bespoke-seams.md` — authoring guide naming `fitTextFontSize` as canonical overflow primitive.
- `episodes/<slug>/stage-2-composite/hyperframes.json` (emitted by compositor at compose time).
- `episodes/<slug>/stage-2-composite/meta.json` (emitted by compositor at compose time).
- `episodes/<slug>/stage-2-composite/compositions/transitions.html` (emitted by compositor at compose time).

**Modified:**
- `tools/compositor/src/captionsComposition.ts` — full rewrite: groups, autoAlpha hard-kill, fitTextFontSize, self-lint, literal hex.
- `tools/compositor/src/composer.ts` — single-track seams (drop `TRACK_SEAM_BASE + i`), literal hex in inline styles, embed transitions clip.
- `tools/compositor/src/designMd.ts` — add `resolveToken(name)` API + accessors used by composers.
- `tools/compositor/src/index.ts` — call episodeMeta emitter; wire compose entrypoint to write the new files.
- `tools/compositor/src/types.ts` — `// TODO(6b)` comment on `Seam.graphic`.
- `tools/compositor/src/seamPlanWriter.ts` — `// TODO(6b)` comment on `graphic:` line round-trip.
- `tools/compositor/src/sceneMode.ts` — transitional-shim comment.
- `tools/compositor/package.json` — exact-pin hyperframes (drop caret).
- `tools/scripts/sync-hf-skills.sh` — read pinned version from package.json (no `npm view`).
- `tools/scripts/check-updates.sh` — flag CLI/skills version mismatch.
- `tools/scripts/run-stage2-compose.sh` — source preflight, restore strict inspect.
- `tools/scripts/run-stage2-preview.sh` — source preflight, Docker-by-default.
- `tools/scripts/render-final.sh` — Docker-by-default switch.
- `tools/scripts/test/test-run-stage2.sh` — fix `composition.html` → `index.html` assertion.
- `DESIGN.md` — extend `hyperframes-tokens` JSON with `transition` block, add `## Transitions` prose section, extend `Colors` with base-palette declaration, extend `Typography` with Inter override rationale, extend `What NOT to Do` with shader-compat anti-patterns.
- `AGENTS.md` — rename `composition.html` → `index.html`; add FROZEN-pilot note; document `HF_RENDER_MODE=local` opt-out.
- `standards/pipeline-contracts.md` — add FROZEN-pilot note.
- `standards/captions.md` — rewrite `tokens.*` references to DESIGN.md `hyperframes-tokens` keys.
- `standards/motion-graphics.md` — rewrite `tokens.*` references; add Layout-Before-Animation and Scene-phases sections.
- `design-system/README.md` — rewrite to lead with 6a state.
- `episodes/2026-04-28-phase-6a-smoke-test/stage-2-composite/compositions/seam-4.html` — add `data-layout-allow-overflow` if `inspect` flags it.
- `tools/compositor/test/composer.test.ts` — update for single-track + literal-hex changes.

**Deleted:**
- `tools/scripts/run-stage2.sh` (after fixing the test that calls it).
- `.gitignore` line `episodes/*/stage-2-composite/hf-project/`.

---

## Phase A — HF version pinning & sync infrastructure

**Why first:** Pinning before further changes guarantees that all subsequent test runs use the same HF CLI/skills version. Without this, a transient `npm view latest` could pull a different CLI mid-implementation.

### Task A1: Pin hyperframes exact version + sync from pin

**Files:**
- Modify: `tools/compositor/package.json`
- Modify: `tools/scripts/sync-hf-skills.sh`

- [ ] **Step 1: Drop the caret from `tools/compositor/package.json`**

Change `"hyperframes": "^0.4.31"` to `"hyperframes": "0.4.31"` (exact pin).

```json
"dependencies": {
  "hyperframes": "0.4.31"
}
```

- [ ] **Step 2: Refresh the lockfile**

Run: `cd tools/compositor && npm install && cd ../..`
Expected: `package-lock.json` updated; no other deps changed.

- [ ] **Step 3: Rewrite `sync-hf-skills.sh` to read pinned version**

Replace the version-discovery block. The script must read `tools/compositor/package.json` `dependencies.hyperframes` exactly and refuse to sync if not exact-pinned (no caret/tilde).

```bash
#!/usr/bin/env bash
set -euo pipefail

# Sync vendored HyperFrames skills to match the pinned CLI version in
# tools/compositor/package.json. CLI and skills MUST stay at the same
# version — drift causes methodology rules and runtime to diverge silently.

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SKILLS_DIR="$REPO_ROOT/tools/hyperframes-skills"
PKG_JSON="$REPO_ROOT/tools/compositor/package.json"

VERSION="$(node -e "const v=require('$PKG_JSON').dependencies.hyperframes; if(/^[\\^~]/.test(v)){process.stderr.write('ERROR: hyperframes pin '+v+' is not exact (no ^ or ~ allowed)\\n');process.exit(2);} console.log(v);")"
[ -n "$VERSION" ] || { echo "ERROR: could not read pinned hyperframes version"; exit 1; }

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

TARBALL_URL="$(npm view "hyperframes@$VERSION" dist.tarball)"
[ -n "$TARBALL_URL" ] || { echo "ERROR: hyperframes@$VERSION has no tarball on npm"; exit 1; }

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

- [ ] **Step 4: Run sync to verify it still works against the pin**

Run: `bash tools/scripts/sync-hf-skills.sh`
Expected output ends with `Done. Vendored at ... (version 0.4.31).`
`tools/hyperframes-skills/VERSION` reads `0.4.31`.

- [ ] **Step 5: Verify the no-caret guard fires**

Temporarily edit `package.json` to `"hyperframes": "^0.4.31"`, run `bash tools/scripts/sync-hf-skills.sh`.
Expected: exits with `ERROR: hyperframes pin ^0.4.31 is not exact (no ^ or ~ allowed)`.
Revert `package.json` to `"hyperframes": "0.4.31"`.

- [ ] **Step 6: Commit**

```bash
git add tools/compositor/package.json tools/compositor/package-lock.json tools/scripts/sync-hf-skills.sh
git commit -m "chore(hf): exact-pin hyperframes and sync skills from pin

Drops caret from package.json so npm install cannot drift CLI ahead of
vendored skills. sync-hf-skills.sh now reads the pinned version and
refuses to operate on non-exact pins."
```

### Task A2: Flag CLI/skills version mismatch in check-updates.sh

**Files:**
- Modify: `tools/scripts/check-updates.sh`

- [ ] **Step 1: Add CLI/skills version-mismatch check**

Insert after the existing hyperframes-version check, before the `video-use` check:

```bash
# 1a. CLI/skills mismatch (exact-pin in package.json must equal vendored VERSION)
SKILLS_VERSION_FILE="$REPO_ROOT/tools/hyperframes-skills/VERSION"
if [ -n "$LOCAL_HF" ] && [ -f "$SKILLS_VERSION_FILE" ]; then
  SKILLS_VER="$(tr -d '[:space:]' < "$SKILLS_VERSION_FILE")"
  if [ "$LOCAL_HF" != "$SKILLS_VER" ]; then
    note "hyperframes CLI pin ($LOCAL_HF) ≠ vendored skills version ($SKILLS_VER) — run tools/scripts/sync-hf-skills.sh"
  fi
fi
```

- [ ] **Step 2: Verify**

Run: `bash tools/scripts/check-updates.sh`
Expected: clean run, no notice about CLI/skills mismatch (since A1 just synced them).

- [ ] **Step 3: Verify the mismatch trigger**

Temporarily edit `tools/hyperframes-skills/VERSION` to `0.0.0`, run check-updates.
Expected: a notice line `- hyperframes CLI pin (0.4.31) ≠ vendored skills version (0.0.0) — run tools/scripts/sync-hf-skills.sh`.
Restore `VERSION` to `0.4.31`.

- [ ] **Step 4: Commit**

```bash
git add tools/scripts/check-updates.sh
git commit -m "chore(hf): flag CLI/skills version mismatch in check-updates"
```

---

## Phase B — Compositor: literal-hex token resolver, single-track seams, episode meta

### Task B1: Add `resolveToken` API to designMd.ts (test-first)

**Files:**
- Test: `tools/compositor/test/designMd.test.ts`
- Modify: `tools/compositor/src/designMd.ts`

- [ ] **Step 1: Add failing test for `resolveToken`**

Append to `tools/compositor/test/designMd.test.ts`:

```typescript
import { resolveToken, parseDesignMd } from "../src/designMd.js";

describe("resolveToken", () => {
  const md = `\`\`\`json hyperframes-tokens
{
  "color": { "text": { "primary": "#FFFFFF" }, "glass": { "fill": "rgba(255,255,255,0.18)" } },
  "type":  { "size": { "caption": "64px" } },
  "video": { "fps": 60 }
}
\`\`\``;
  const tree = parseDesignMd(md);

  it("returns literal string values by dotted path", () => {
    expect(resolveToken(tree, "color.text.primary")).toBe("#FFFFFF");
    expect(resolveToken(tree, "color.glass.fill")).toBe("rgba(255,255,255,0.18)");
    expect(resolveToken(tree, "type.size.caption")).toBe("64px");
  });

  it("returns numbers as strings", () => {
    expect(resolveToken(tree, "video.fps")).toBe("60");
  });

  it("throws on missing path", () => {
    expect(() => resolveToken(tree, "color.text.nonexistent")).toThrow(/color.text.nonexistent/);
  });

  it("throws when path resolves to a subtree, not a leaf", () => {
    expect(() => resolveToken(tree, "color.text")).toThrow(/leaf/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/compositor && npx vitest run test/designMd.test.ts`
Expected: FAIL — `resolveToken` is not exported.

- [ ] **Step 3: Implement `resolveToken`**

Append to `tools/compositor/src/designMd.ts`:

```typescript
export function resolveToken(tree: TokenTree, dottedPath: string): string {
  const parts = dottedPath.split(".");
  let cursor: TokenTree | string | number = tree;
  for (const part of parts) {
    if (cursor === null || typeof cursor !== "object" || Array.isArray(cursor)) {
      throw new Error(`resolveToken: '${dottedPath}' missing — '${part}' has no parent object`);
    }
    if (!(part in (cursor as TokenTree))) {
      throw new Error(`resolveToken: '${dottedPath}' not found in DESIGN.md tokens`);
    }
    cursor = (cursor as TokenTree)[part];
  }
  if (cursor !== null && typeof cursor === "object") {
    throw new Error(`resolveToken: '${dottedPath}' resolves to a subtree, not a leaf value`);
  }
  return String(cursor);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd tools/compositor && npx vitest run test/designMd.test.ts`
Expected: PASS for all four `resolveToken` cases plus existing tests.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/designMd.ts tools/compositor/test/designMd.test.ts
git commit -m "feat(compositor): add resolveToken for literal hex resolution

Returns leaf token values by dotted path so composers can inline literal
hex/RGBA into element styles instead of var() references — the
shader-compat rule from references/transitions.md."
```

### Task B2: Replace `var(--…)` in inline styles in composer.ts

**Files:**
- Modify: `tools/compositor/src/composer.ts`
- Modify: `tools/compositor/test/composer.test.ts`

- [ ] **Step 1: Add failing test for literal-hex root styles**

Insert into `tools/compositor/test/composer.test.ts`'s describe block:

```typescript
it("inlines literal hex/RGBA on captured elements (no var() in body styles)", () => {
  // The :root { --… } declarations are documentation only; the body's own
  // style attributes must use literal values for shader-compat.
  const bodyStyleMatch = html.match(/<style>[\s\S]*?<\/style>/);
  expect(bodyStyleMatch).toBeTruthy();
  const styleBlock = bodyStyleMatch![0];
  const bodyRule = styleBlock.match(/html,\s*body\s*\{[^}]*\}/);
  expect(bodyRule).toBeTruthy();
  expect(bodyRule![0]).not.toMatch(/var\(--/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/compositor && npx vitest run test/composer.test.ts`
Expected: FAIL — body rule currently uses `var(--color-bg-transparent)` etc.

- [ ] **Step 3: Update composer.ts to inline literals**

In `tools/compositor/src/composer.ts`, change `buildRootIndexHtml` to call `resolveToken` and emit literal values into the `html, body` rule. Update imports:

```typescript
import { loadDesignMd, designMdToCss, resolveToken } from "./designMd.js";
```

Resolve tokens once at the top of `buildRootIndexHtml`:

```typescript
const tree = loadDesignMd(args.designMdPath);
const css = designMdToCss(tree);
const bgTransparent = resolveToken(tree, "color.bg.transparent");
const textPrimary  = resolveToken(tree, "color.text.primary");
const fontCaption  = resolveToken(tree, "type.family.caption");
```

In the template literal, replace the body rule:

```css
/* Before: html, body { … background: var(--color-bg-transparent); color: var(--color-text-primary); font-family: var(--type-family-caption); … } */
/* After:  html, body { … background: ${bgTransparent}; color: ${textPrimary}; font-family: ${fontCaption}; … } */
```

The `:root { --… }` block emitted by `designMdToCss(tree)` stays — it is documentation-only and is not consumed by captured-element styles.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tools/compositor && npx vitest run test/composer.test.ts`
Expected: PASS for the new test plus existing assertions.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/composer.ts tools/compositor/test/composer.test.ts
git commit -m "fix(compositor): inline literal hex on root composition body styles

html2canvas does not reliably resolve var() at capture time
(references/transitions.md shader-compat rule). The :root { --… } block
remains as documentation; captured-element styles use resolved literals."
```

### Task B3: Single-track seam emission

**Files:**
- Modify: `tools/compositor/src/composer.ts`
- Modify: `tools/compositor/test/composer.test.ts`

- [ ] **Step 1: Add failing test for single-track seams**

Insert into the composer test:

```typescript
it("emits all seams on a single track index (3)", () => {
  const seamClipMatches = html.match(/data-composition-src="compositions\/seam-\d+\.html"[\s\S]*?data-track-index="(\d+)"/g);
  expect(seamClipMatches).not.toBeNull();
  for (const clip of seamClipMatches!) {
    const m = clip.match(/data-track-index="(\d+)"/);
    expect(m![1]).toBe("3");
  }
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/compositor && npx vitest run test/composer.test.ts`
Expected: FAIL — current code uses `TRACK_SEAM_BASE + i`.

- [ ] **Step 3: Drop the `+ i` ladder**

In `tools/compositor/src/composer.ts`:

```typescript
// Before:
//   const trackIndex = TRACK_SEAM_BASE + i;
// After:
//   const trackIndex = TRACK_SEAM_BASE; // seams are non-overlapping; per HF SKILL.md they share one track
```

Drop the `(s, i) =>` second parameter since `i` is no longer used. Final shape:

```typescript
const seamFragments = args.plan.seams
  .filter((s) => args.existingSeamFiles.has(s.index))
  .map((s) => {
    const startSec = msToSeconds(s.at_ms);
    const durationSec = msToSeconds(s.ends_at_ms - s.at_ms);
    return `<div class="clip"
     data-composition-src="compositions/seam-${s.index}.html"
     data-composition-id="seam-${s.index}"
     data-start="${startSec}"
     data-duration="${durationSec}"
     data-width="${ROOT_WIDTH}"
     data-height="${ROOT_HEIGHT}"
     data-track-index="${TRACK_SEAM_BASE}"></div>`;
  });
```

- [ ] **Step 4: Run all compositor tests**

Run: `cd tools/compositor && npx vitest run`
Expected: PASS for all suites including the new single-track test.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/composer.ts tools/compositor/test/composer.test.ts
git commit -m "fix(compositor): emit all seams on a single track index

Per HF SKILL.md 'data-track-index does not affect visual layering — use
CSS z-index'. Seams tile non-overlappingly so they belong on one track.
Track-laddering was a misreading of the contract."
```

### Task B4: Emit `hyperframes.json` and `meta.json` (episodeMeta module)

**Files:**
- Create: `tools/compositor/src/episodeMeta.ts`
- Create: `tools/compositor/test/episodeMeta.test.ts`
- Modify: `tools/compositor/src/index.ts`

- [ ] **Step 1: Write failing test**

Create `tools/compositor/test/episodeMeta.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { mkdtempSync, readFileSync, existsSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { writeEpisodeMeta } from "../src/episodeMeta.js";

describe("writeEpisodeMeta", () => {
  it("writes hyperframes.json with the canonical paths config", () => {
    const dir = mkdtempSync(path.join(os.tmpdir(), "epmeta-"));
    writeEpisodeMeta({ episodeSlug: "demo-episode", outDir: dir, createdAt: "2026-04-28T00:00:00.000Z" });
    const hf = JSON.parse(readFileSync(path.join(dir, "hyperframes.json"), "utf8"));
    expect(hf).toEqual({
      $schema: "https://hyperframes.heygen.com/schema/hyperframes.json",
      registry: "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
      paths: {
        blocks: "compositions",
        components: "compositions/components",
        assets: "assets",
      },
    });
  });

  it("writes meta.json with id, name, createdAt", () => {
    const dir = mkdtempSync(path.join(os.tmpdir(), "epmeta-"));
    writeEpisodeMeta({ episodeSlug: "demo-episode", outDir: dir, createdAt: "2026-04-28T00:00:00.000Z" });
    const meta = JSON.parse(readFileSync(path.join(dir, "meta.json"), "utf8"));
    expect(meta).toEqual({ id: "demo-episode", name: "demo-episode", createdAt: "2026-04-28T00:00:00.000Z" });
  });

  it("creates the output dir if missing", () => {
    const dir = path.join(mkdtempSync(path.join(os.tmpdir(), "epmeta-")), "nested");
    writeEpisodeMeta({ episodeSlug: "x", outDir: dir, createdAt: "2026-04-28T00:00:00.000Z" });
    expect(existsSync(path.join(dir, "hyperframes.json"))).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/compositor && npx vitest run test/episodeMeta.test.ts`
Expected: FAIL — `episodeMeta.ts` does not exist.

- [ ] **Step 3: Implement `episodeMeta.ts`**

Create `tools/compositor/src/episodeMeta.ts`:

```typescript
import { writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";

export interface EpisodeMetaArgs {
  episodeSlug: string;
  outDir: string;
  createdAt?: string;
}

const HF_PROJECT_CONFIG = {
  $schema: "https://hyperframes.heygen.com/schema/hyperframes.json",
  registry: "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
  paths: {
    blocks: "compositions",
    components: "compositions/components",
    assets: "assets",
  },
} as const;

export function writeEpisodeMeta(args: EpisodeMetaArgs): { hyperframesJsonPath: string; metaJsonPath: string } {
  mkdirSync(args.outDir, { recursive: true });
  const hyperframesJsonPath = path.join(args.outDir, "hyperframes.json");
  const metaJsonPath = path.join(args.outDir, "meta.json");
  const createdAt = args.createdAt ?? new Date().toISOString();

  writeFileSync(hyperframesJsonPath, JSON.stringify(HF_PROJECT_CONFIG, null, 2) + "\n");
  writeFileSync(metaJsonPath, JSON.stringify({ id: args.episodeSlug, name: args.episodeSlug, createdAt }, null, 2) + "\n");

  return { hyperframesJsonPath, metaJsonPath };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd tools/compositor && npx vitest run test/episodeMeta.test.ts`
Expected: PASS for all three tests.

- [ ] **Step 5: Wire into the compose command**

In `tools/compositor/src/index.ts`, add the import at the top:

```typescript
import { writeEpisodeMeta } from "./episodeMeta.js";
```

In the `compose` branch, after `writeCompositionFiles(...)`:

```typescript
const compositeDir = path.join(episodeDir, "stage-2-composite");
const slug = path.basename(path.resolve(episodeDir));
const meta = writeEpisodeMeta({ episodeSlug: slug, outDir: compositeDir });
console.log(`Wrote ${meta.hyperframesJsonPath}`);
console.log(`Wrote ${meta.metaJsonPath}`);
```

- [ ] **Step 6: Commit**

```bash
git add tools/compositor/src/episodeMeta.ts tools/compositor/test/episodeMeta.test.ts tools/compositor/src/index.ts
git commit -m "feat(compositor): emit hyperframes.json + meta.json per episode

HF init scaffolds these at project root. Our compose step now writes them
into stage-2-composite/ so each episode is HF-canonical at the directory
level, not just at the index.html level."
```

---

## Phase C — Captions rewrite (word-grouped, autoAlpha, fitTextFontSize, self-lint)

### Task C1: Extract `groupWords` pure helper (test-first)

**Files:**
- Create: `tools/compositor/src/groupWords.ts`
- Create: `tools/compositor/test/groupWords.test.ts`

- [ ] **Step 1: Write failing test**

Create `tools/compositor/test/groupWords.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { groupWords } from "../src/groupWords.js";

describe("groupWords (medium-energy default)", () => {
  it("breaks on a >120ms gap to the next word", () => {
    const words = [
      { text: "one",   startMs: 0,    endMs: 200 },
      { text: "two",   startMs: 220,  endMs: 400 },
      { text: "three", startMs: 600,  endMs: 800 },
    ];
    const groups = groupWords(words, { maxWordsPerGroup: 5, breakAfterPauseMs: 120 });
    expect(groups).toHaveLength(2);
    expect(groups[0].words.map((w) => w.text)).toEqual(["one", "two"]);
    expect(groups[1].words.map((w) => w.text)).toEqual(["three"]);
  });

  it("caps group size at maxWordsPerGroup even without a pause", () => {
    const words = Array.from({ length: 7 }, (_, i) => ({ text: `w${i}`, startMs: i * 100, endMs: i * 100 + 80 }));
    const groups = groupWords(words, { maxWordsPerGroup: 5, breakAfterPauseMs: 120 });
    expect(groups).toHaveLength(2);
    expect(groups[0].words).toHaveLength(5);
    expect(groups[1].words).toHaveLength(2);
  });

  it("sets group.startMs to first word.startMs and group.endMs to last word.endMs", () => {
    const words = [
      { text: "a", startMs: 100, endMs: 200 },
      { text: "b", startMs: 220, endMs: 380 },
    ];
    const [g] = groupWords(words, { maxWordsPerGroup: 5, breakAfterPauseMs: 120 });
    expect(g.startMs).toBe(100);
    expect(g.endMs).toBe(380);
  });

  it("returns an empty array on empty input", () => {
    expect(groupWords([], { maxWordsPerGroup: 5, breakAfterPauseMs: 120 })).toEqual([]);
  });

  it("assigns sequential ids g0, g1, g2…", () => {
    const words = [
      { text: "a", startMs: 0, endMs: 100 },
      { text: "b", startMs: 300, endMs: 400 },
      { text: "c", startMs: 600, endMs: 700 },
    ];
    const groups = groupWords(words, { maxWordsPerGroup: 5, breakAfterPauseMs: 120 });
    expect(groups.map((g) => g.id)).toEqual(["g0", "g1", "g2"]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/compositor && npx vitest run test/groupWords.test.ts`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `groupWords`**

Create `tools/compositor/src/groupWords.ts`:

```typescript
export interface GroupWordsInput {
  text: string;
  startMs: number;
  endMs: number;
}

export interface CaptionGroup {
  id: string;
  startMs: number;
  endMs: number;
  words: GroupWordsInput[];
}

export interface GroupWordsOptions {
  maxWordsPerGroup: number;
  breakAfterPauseMs: number;
}

export function groupWords(words: GroupWordsInput[], opts: GroupWordsOptions): CaptionGroup[] {
  const groups: CaptionGroup[] = [];
  let current: GroupWordsInput[] = [];

  const flush = (): void => {
    if (current.length === 0) return;
    groups.push({
      id: `g${groups.length}`,
      startMs: current[0].startMs,
      endMs: current[current.length - 1].endMs,
      words: current,
    });
    current = [];
  };

  for (let i = 0; i < words.length; i++) {
    const w = words[i];
    current.push(w);
    const next = words[i + 1];
    const reachedCap = current.length >= opts.maxWordsPerGroup;
    const pauseAfter = next ? next.startMs - w.endMs > opts.breakAfterPauseMs : false;
    if (reachedCap || pauseAfter || !next) {
      flush();
    }
  }

  return groups;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tools/compositor && npx vitest run test/groupWords.test.ts`
Expected: PASS for all five tests.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/groupWords.ts tools/compositor/test/groupWords.test.ts
git commit -m "feat(compositor): add groupWords helper for caption grouping

Pure helper: walks transcript words, breaks on >120ms pause or 5-word cap.
Returns groups with stable ids (g0, g1, …) and start/end ms derived from
first/last word. Used by the captions sub-composition rewrite (next)."
```

### Task C2: Rewrite `captionsComposition.ts`

**Files:**
- Modify: `tools/compositor/src/captionsComposition.ts`
- Create or modify: `tools/compositor/test/captionsComposition.test.ts`
- Modify: `tools/compositor/src/composer.ts`

- [ ] **Step 1: Write failing tests for the rewritten output**

Create `tools/compositor/test/captionsComposition.test.ts` (overwrite if it exists):

```typescript
import { describe, it, expect } from "vitest";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildCaptionsCompositionHtml } from "../src/captionsComposition.js";
import { loadDesignMd } from "../src/designMd.js";
import type { MasterBundle } from "../src/types.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const designMdPath = path.join(__dirname, "fixtures", "design-minimal.md");

const bundle: MasterBundle = {
  schemaVersion: 1,
  slug: "fixture",
  master: { durationMs: 5000, width: 1440, height: 2560, fps: 60 },
  boundaries: [],
  transcript: {
    language: "en",
    words: [
      { text: "one",   startMs: 0,    endMs: 200 },
      { text: "two",   startMs: 220,  endMs: 400 },
      { text: "three", startMs: 600,  endMs: 800 },
      { text: "four",  startMs: 820,  endMs: 1000 },
    ],
  },
};

describe("buildCaptionsCompositionHtml (grouped rewrite)", () => {
  const tree = loadDesignMd(designMdPath);
  const html = buildCaptionsCompositionHtml({ bundle, tree });

  it("emits one .caption-group div per group", () => {
    const groupMatches = html.match(/class="caption-group"/g) ?? [];
    expect(groupMatches.length).toBe(2);
  });

  it("uses literal hex/rgba in element styles, no var(--…)", () => {
    const noScript = html.replace(/<script[\s\S]*?<\/script>/g, "");
    expect(noScript).not.toMatch(/var\(--/);
  });

  it("registers autoAlpha:0 hard-kill at group.endMs in the runtime script", () => {
    expect(html).toMatch(/tl\.set\([^,]+,\s*\{\s*autoAlpha:\s*0\s*\}\s*,\s*[\d.]+\s*\)/);
  });

  it("calls window.__hyperframes.fitTextFontSize per group", () => {
    expect(html).toMatch(/window\.__hyperframes\.fitTextFontSize/);
  });

  it("appends a self-lint sweep that throws on missing entry/exit", () => {
    expect(html).toMatch(/getChildren\(\)/);
    expect(html).toMatch(/throw/);
  });

  it("registers window.__timelines.captions", () => {
    expect(html).toMatch(/window\.__timelines\["captions"\]\s*=\s*tl/);
  });

  it("emits an empty template + no timeline registration when there are no words", () => {
    const emptyBundle: MasterBundle = { ...bundle, transcript: { language: "en", words: [] } };
    const out = buildCaptionsCompositionHtml({ bundle: emptyBundle, tree });
    expect(out).not.toMatch(/window\.__timelines\["captions"\]/);
    expect(out).toMatch(/<template/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/compositor && npx vitest run test/captionsComposition.test.ts`
Expected: FAIL — current output uses `var(--…)`, has no `.caption-group`, no `autoAlpha`, no `fitTextFontSize`, no self-lint.

- [ ] **Step 3: Rewrite `captionsComposition.ts`**

Replace the entire contents of `tools/compositor/src/captionsComposition.ts`:

```typescript
import type { MasterBundle } from "./types.js";
import type { TokenTree } from "./designMd.js";
import { resolveToken } from "./designMd.js";
import { groupWords } from "./groupWords.js";

export interface CaptionsArgs {
  bundle: MasterBundle;
  tree: TokenTree;
}

const MAX_WORDS_PER_GROUP = 5;
const BREAK_AFTER_PAUSE_MS = 120;

export function buildCaptionsCompositionHtml(args: CaptionsArgs): string {
  const totalSec = (Math.round(args.bundle.master.durationMs) / 1000).toFixed(3);
  const words = args.bundle.transcript.words;

  const fontFamily      = resolveToken(args.tree, "type.family.caption");
  const fontSize        = resolveToken(args.tree, "type.size.caption");
  const fontWeight      = resolveToken(args.tree, "type.weight.bold");
  const colorActive     = resolveToken(args.tree, "color.caption.active");
  const colorInactive   = resolveToken(args.tree, "color.caption.inactive");
  const safezoneSide    = resolveToken(args.tree, "safezone.side");
  const safezoneBottom  = resolveToken(args.tree, "safezone.bottom");

  if (words.length === 0) {
    return `<template id="captions-template">
<div data-composition-id="captions" data-start="0" data-duration="${totalSec}" data-width="1440" data-height="2560">
  <!-- no transcript words; captions sub-composition emits no timeline -->
</div>
</template>`;
  }

  const groups = groupWords(
    words.map((w) => ({ text: w.text, startMs: w.startMs, endMs: w.endMs })),
    { maxWordsPerGroup: MAX_WORDS_PER_GROUP, breakAfterPauseMs: BREAK_AFTER_PAUSE_MS },
  );

  const groupsForRuntime = groups.map((g) => ({
    id: g.id,
    startSec: g.startMs / 1000,
    endSec: g.endMs / 1000,
  }));

  const groupDivs = groups
    .map((g) => {
      const inner = g.words.map((w) => `<span class="caption-word">${escapeHtml(w.text)}</span>`).join(" ");
      return `<div class="caption-group" data-group-id="${g.id}">${inner}</div>`;
    })
    .join("\n  ");

  const fontSizePx = parseFontSizePx(fontSize);

  return `<template id="captions-template">
<div data-composition-id="captions" data-start="0" data-duration="${totalSec}" data-width="1440" data-height="2560">
  <style>
    [data-composition-id="captions"] {
      width: 100%; height: 100%; position: relative;
      background-color: rgba(0,0,0,0);
    }
    [data-composition-id="captions"] .caption-group {
      position: absolute;
      left: ${safezoneSide}; right: ${safezoneSide};
      bottom: ${safezoneBottom};
      text-align: center;
      font-family: ${fontFamily};
      font-size: ${fontSize};
      font-weight: ${fontWeight};
      line-height: 1.2;
      color: ${colorActive};
      visibility: hidden;
      opacity: 0;
    }
    [data-composition-id="captions"] .caption-word {
      display: inline-block;
      margin: 0 0.18em;
    }
    [data-composition-id="captions"] .caption-group.muted .caption-word {
      color: ${colorInactive};
    }
  </style>
  ${groupDivs}
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <script>
    (function () {
      var GROUPS = ${JSON.stringify(groupsForRuntime)};
      var root = document.querySelector('[data-composition-id="captions"]');
      window.__timelines = window.__timelines || {};
      var tl = gsap.timeline({ paused: true });
      var fit = (window.__hyperframes && window.__hyperframes.fitTextFontSize) || null;

      GROUPS.forEach(function (g) {
        var sel = '[data-group-id="' + g.id + '"]';
        var el = root.querySelector(sel);
        // Entrance: fade + small lift, hero-frame is the static CSS position.
        tl.from(el, { autoAlpha: 0, y: 24, duration: 0.32, ease: "power3.out" }, g.startSec);
        // Hard-kill at group end (autoAlpha = opacity:0 + visibility:hidden).
        tl.set(el, { autoAlpha: 0 }, g.endSec);
        // Size to canvas on first show.
        if (fit) {
          tl.call(function () { fit(el, { maxFontSize: ${fontSizePx}, minFontSize: 28 }); }, [], g.startSec);
        }
      });

      tl.to({}, { duration: ${totalSec} }, 0);
      window.__timelines["captions"] = tl;

      // Self-lint: every group must have an entry tween and a hard-kill set.
      var children = tl.getChildren(false, true, true);
      GROUPS.forEach(function (g) {
        var hasEntry = children.some(function (c) { return Math.abs(c.startTime() - g.startSec) < 1e-3 && c.vars && c.vars.duration; });
        var hasKill  = children.some(function (c) { return Math.abs(c.startTime() - g.endSec)   < 1e-3 && c.vars && c.vars.autoAlpha === 0 && !c.vars.duration; });
        if (!hasEntry || !hasKill) {
          throw new Error("captions self-lint failed for group " + g.id + ": entry=" + hasEntry + " kill=" + hasKill);
        }
      });
    })();
  </script>
</div>
</template>`;
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string));
}

function parseFontSizePx(token: string): number {
  const m = token.match(/^(\d+(?:\.\d+)?)px$/);
  return m ? Number(m[1]) : 64;
}
```

- [ ] **Step 4: Update the composer call to pass `tree`**

In `tools/compositor/src/composer.ts`, refactor `writeCompositionFiles` so the captions builder receives the parsed token tree, and `buildRootIndexHtml` accepts an optional pre-parsed tree to avoid loading DESIGN.md twice:

```typescript
import type { TokenTree } from "./designMd.js";

export function buildRootIndexHtml(args: ComposeArgs, tree?: TokenTree): string {
  const t = tree ?? loadDesignMd(args.designMdPath);
  const css = designMdToCss(t);
  const bgTransparent = resolveToken(t, "color.bg.transparent");
  const textPrimary  = resolveToken(t, "color.text.primary");
  const fontCaption  = resolveToken(t, "type.family.caption");
  // ... existing template body with literal substitutions
}

export function writeCompositionFiles(args: WriteCompositionArgs): { indexPath: string; captionsPath: string } {
  const compositeDir = path.join(args.episodeDir, "stage-2-composite");
  const compositionsDir = path.join(compositeDir, "compositions");
  mkdirSync(compositionsDir, { recursive: true });

  const tree = loadDesignMd(args.designMdPath);
  const indexPath = path.join(compositeDir, "index.html");
  const captionsPath = path.join(compositionsDir, "captions.html");

  writeFileSync(indexPath, buildRootIndexHtml(args, tree));
  writeFileSync(captionsPath, buildCaptionsCompositionHtml({ bundle: args.bundle, tree }));

  return { indexPath, captionsPath };
}
```

- [ ] **Step 5: Run all compositor tests**

Run: `cd tools/compositor && npx vitest run`
Expected: PASS for all suites.

- [ ] **Step 6: Commit**

```bash
git add tools/compositor/src/captionsComposition.ts tools/compositor/src/composer.ts tools/compositor/test/captionsComposition.test.ts
git commit -m "feat(captions): word-grouped HF-spec rewrite

- Groups via groupWords helper (5-word cap, 120ms pause break)
- Animates group containers, not per-word — entry tween + autoAlpha:0
  hard-kill at group.end (collapses opacity:0 + visibility:hidden)
- Calls window.__hyperframes.fitTextFontSize per group on first show
- Literal hex/rgba on captured styles (shader-compat)
- Self-lint sweep throws on missing entry or hard-kill before render

Closes the captions divergence flagged in the post-6a HF audit."
```

---

## Phase D — Transitions sub-composition

### Task D1: Parse `transition` block from DESIGN.md (test-first)

**Files:**
- Modify: `tools/compositor/src/designMd.ts`
- Modify: `tools/compositor/test/designMd.test.ts`

- [ ] **Step 1: Write failing test for transition block**

Append to `tools/compositor/test/designMd.test.ts`:

```typescript
import { readTransitionConfig } from "../src/designMd.js";

describe("readTransitionConfig", () => {
  it("returns the transition block when present", () => {
    const md = `\`\`\`json hyperframes-tokens
{
  "color": {},
  "transition": { "primary": "blur-crossfade", "duration": 0.5, "easing": "sine.inOut" }
}
\`\`\``;
    const tree = parseDesignMd(md);
    expect(readTransitionConfig(tree)).toEqual({ primary: "blur-crossfade", duration: 0.5, easing: "sine.inOut" });
  });

  it("returns the safe default when the block is absent", () => {
    const md = `\`\`\`json hyperframes-tokens
{ "color": {} }
\`\`\``;
    const tree = parseDesignMd(md);
    expect(readTransitionConfig(tree)).toEqual({ primary: "crossfade", duration: 0.4, easing: "power2.inOut" });
  });

  it("throws on unknown primary", () => {
    const md = `\`\`\`json hyperframes-tokens
{ "transition": { "primary": "warp-fold", "duration": 0.5, "easing": "sine.inOut" } }
\`\`\``;
    const tree = parseDesignMd(md);
    expect(() => readTransitionConfig(tree)).toThrow(/warp-fold/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/compositor && npx vitest run test/designMd.test.ts`
Expected: FAIL — `readTransitionConfig` not exported.

- [ ] **Step 3: Implement `readTransitionConfig`**

Append to `tools/compositor/src/designMd.ts`:

```typescript
export type TransitionPrimary = "crossfade" | "blur-crossfade" | "push-slide" | "zoom-through";

export interface TransitionConfig {
  primary: TransitionPrimary;
  duration: number;
  easing: string;
}

const KNOWN_PRIMARIES: ReadonlySet<string> = new Set([
  "crossfade",
  "blur-crossfade",
  "push-slide",
  "zoom-through",
]);

const DEFAULT_TRANSITION: TransitionConfig = {
  primary: "crossfade",
  duration: 0.4,
  easing: "power2.inOut",
};

export function readTransitionConfig(tree: TokenTree): TransitionConfig {
  const block = (tree as Record<string, unknown>).transition;
  if (!block) return DEFAULT_TRANSITION;
  if (typeof block !== "object" || Array.isArray(block)) {
    throw new Error("DESIGN.md: transition block must be a JSON object");
  }
  const b = block as Record<string, unknown>;
  const primary = b.primary;
  if (typeof primary !== "string" || !KNOWN_PRIMARIES.has(primary)) {
    throw new Error(
      `DESIGN.md: transition.primary='${String(primary)}' is not in the catalog ` +
        `(known: ${[...KNOWN_PRIMARIES].join(", ")})`,
    );
  }
  const duration = typeof b.duration === "number" ? b.duration : DEFAULT_TRANSITION.duration;
  const easing = typeof b.easing === "string" ? b.easing : DEFAULT_TRANSITION.easing;
  return { primary: primary as TransitionPrimary, duration, easing };
}
```

- [ ] **Step 4: Run test**

Run: `cd tools/compositor && npx vitest run test/designMd.test.ts`
Expected: PASS for all three new cases.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/designMd.ts tools/compositor/test/designMd.test.ts
git commit -m "feat(designMd): parse optional transition block with safe default

readTransitionConfig returns DESIGN.md's transition block or a crossfade
fallback. Validates primary against a closed catalog so unknown names
fail at compose time, not at render."
```

### Task D2: Implement `transitionsComposition.ts` (test-first)

**Files:**
- Create: `tools/compositor/src/transitionsComposition.ts`
- Create: `tools/compositor/test/transitionsComposition.test.ts`

- [ ] **Step 1: Write failing test**

Create `tools/compositor/test/transitionsComposition.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { buildTransitionsHtml } from "../src/transitionsComposition.js";
import type { Seam } from "../src/types.js";

const seams: Seam[] = [
  { index: 0, at_ms: 0,     ends_at_ms: 7040,  scene: "broll" },
  { index: 1, at_ms: 7040,  ends_at_ms: 17480, scene: "split" },
  { index: 2, at_ms: 17480, ends_at_ms: 29420, scene: "head" },
];

describe("buildTransitionsHtml", () => {
  it("registers a window.__timelines['transitions'] entry", () => {
    const html = buildTransitionsHtml({
      seams,
      totalDurationMs: 29420,
      transition: { primary: "crossfade", duration: 0.4, easing: "power2.inOut" },
    });
    expect(html).toMatch(/window\.__timelines\["transitions"\]\s*=\s*tl/);
  });

  it("emits N-1 transition markers for N seams", () => {
    const html = buildTransitionsHtml({
      seams,
      totalDurationMs: 29420,
      transition: { primary: "crossfade", duration: 0.4, easing: "power2.inOut" },
    });
    const txMatches = html.match(/\/\* transition at /g) ?? [];
    expect(txMatches.length).toBe(2);
  });

  it("emits an empty template when seams.length < 2", () => {
    const html = buildTransitionsHtml({
      seams: [seams[0]],
      totalDurationMs: 7040,
      transition: { primary: "crossfade", duration: 0.4, easing: "power2.inOut" },
    });
    expect(html).not.toMatch(/window\.__timelines\["transitions"\]/);
    expect(html).toMatch(/<template/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/compositor && npx vitest run test/transitionsComposition.test.ts`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `transitionsComposition.ts`**

Create `tools/compositor/src/transitionsComposition.ts`:

```typescript
import type { Seam } from "./types.js";
import type { TransitionConfig } from "./designMd.js";

export interface TransitionsArgs {
  seams: Seam[];
  totalDurationMs: number;
  transition: TransitionConfig;
}

export function buildTransitionsHtml(args: TransitionsArgs): string {
  const totalSec = (Math.round(args.totalDurationMs) / 1000).toFixed(3);

  if (args.seams.length < 2) {
    return `<template id="transitions-template">
<div data-composition-id="transitions" data-start="0" data-duration="${totalSec}" data-width="1440" data-height="2560">
  <!-- single-seam composition: no transitions emitted -->
</div>
</template>`;
  }

  const halfMs = (args.transition.duration * 1000) / 2;
  const boundaries = args.seams.slice(0, -1).map((s, i) => ({
    index: i,
    boundaryMs: s.ends_at_ms,
    startSec: Math.max(0, (s.ends_at_ms - halfMs) / 1000),
  }));

  const boundaryComments = boundaries
    .map((b) => `      /* transition at boundary ${b.index} (seam ${b.index} -> seam ${b.index + 1}) at ${b.boundaryMs}ms */`)
    .join("\n");

  const tlCalls = boundaries
    .map((b) => `      tl.fromTo(maskEl, { autoAlpha: 0 }, { autoAlpha: 1, duration: ${args.transition.duration / 2}, ease: "${args.transition.easing}" }, ${b.startSec.toFixed(3)});\n      tl.to(maskEl,   { autoAlpha: 0, duration: ${args.transition.duration / 2}, ease: "${args.transition.easing}" }, ${(b.startSec + args.transition.duration / 2).toFixed(3)});`)
    .join("\n");

  return `<template id="transitions-template">
<div data-composition-id="transitions" data-start="0" data-duration="${totalSec}" data-width="1440" data-height="2560">
  <style>
    [data-composition-id="transitions"] { position: absolute; inset: 0; pointer-events: none; }
    [data-composition-id="transitions"] .transition-mask {
      position: absolute; inset: 0;
      background-color: #000;
      visibility: hidden;
      opacity: 0;
    }
  </style>
  <div class="transition-mask" id="transitions-mask"></div>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <script>
    (function () {
      var maskEl = document.getElementById("transitions-mask");
      window.__timelines = window.__timelines || {};
      var tl = gsap.timeline({ paused: true });
${boundaryComments}
${tlCalls}
      tl.to({}, { duration: ${totalSec} }, 0);
      window.__timelines["transitions"] = tl;
    })();
  </script>
</div>
</template>`;
}
```

The runtime is intentionally a black-mask crossfade — the simplest visualisable primary. `blur-crossfade`, `push-slide`, `zoom-through` round-trip through the catalog gate but share the baseline implementation until 6b drives richer per-seam content.

- [ ] **Step 4: Run test**

Run: `cd tools/compositor && npx vitest run test/transitionsComposition.test.ts`
Expected: PASS for all three tests.

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/transitionsComposition.ts tools/compositor/test/transitionsComposition.test.ts
git commit -m "feat(compositor): add transitions sub-composition generator

Emits compositions/transitions.html with one black-mask crossfade per
seam boundary. Closes the 'no transitions = jump cuts' divergence from
references/transitions.md."
```

### Task D3: Wire transitions into composer.ts

**Files:**
- Modify: `tools/compositor/src/composer.ts`
- Modify: `tools/compositor/src/index.ts`
- Modify: `tools/compositor/test/composer.test.ts`

- [ ] **Step 1: Add failing test for transitions clip in root index**

Insert into `composer.test.ts`:

```typescript
it("emits a transitions clip referencing compositions/transitions.html", () => {
  expect(html).toContain('data-composition-src="compositions/transitions.html"');
  expect(html).toContain('data-composition-id="transitions"');
});
```

Run: `cd tools/compositor && npx vitest run test/composer.test.ts`
Expected: FAIL — composer doesn't emit a transitions clip.

- [ ] **Step 2: Update composer to emit transitions clip + write the file**

In `tools/compositor/src/composer.ts`:

1. Add a new track constant near the top: `const TRACK_TRANSITIONS = 4;` (after `TRACK_SEAM_BASE = 3`).
2. After the captions clip in the body template literal, add:

```typescript
<div class="clip"
     data-composition-src="compositions/transitions.html"
     data-composition-id="transitions"
     data-start="0"
     data-duration="${masterDurationSec}"
     data-width="${ROOT_WIDTH}"
     data-height="${ROOT_HEIGHT}"
     data-track-index="${TRACK_TRANSITIONS}"></div>
```

3. In `writeCompositionFiles`, also write transitions:

```typescript
import { buildTransitionsHtml } from "./transitionsComposition.js";
import { readTransitionConfig } from "./designMd.js";
// ... inside writeCompositionFiles, after the captions write:
const transitionConfig = readTransitionConfig(tree);
const transitionsPath = path.join(compositionsDir, "transitions.html");
writeFileSync(transitionsPath, buildTransitionsHtml({
  seams: args.plan.seams,
  totalDurationMs: args.bundle.master.durationMs,
  transition: transitionConfig,
}));
```

4. Update the return type to `{ indexPath; captionsPath; transitionsPath }`.

- [ ] **Step 3: Run all compositor tests**

Run: `cd tools/compositor && npx vitest run`
Expected: PASS — composer references transitions; `writeCompositionFiles` returns the new path; all suites green.

- [ ] **Step 4: Update `index.ts` compose log lines**

In `tools/compositor/src/index.ts` compose branch:

```typescript
const { indexPath, captionsPath, transitionsPath } = writeCompositionFiles({...});
console.log(`Wrote ${indexPath}`);
console.log(`Wrote ${captionsPath}`);
console.log(`Wrote ${transitionsPath}`);
```

- [ ] **Step 5: Commit**

```bash
git add tools/compositor/src/composer.ts tools/compositor/src/index.ts tools/compositor/test/composer.test.ts
git commit -m "feat(compositor): wire transitions sub-composition into root index

Root index.html now references compositions/transitions.html on track 4.
writeCompositionFiles emits the new file at compose time, parameterised
by DESIGN.md's transition block (or the safe crossfade default)."
```

---

## Phase E — DESIGN.md, standards, AGENTS.md, design-system docs

### Task E1: Extend DESIGN.md

**Files:**
- Modify: `DESIGN.md`

- [ ] **Step 1: Add `transition` field to the `hyperframes-tokens` JSON block**

Inside the fenced JSON, after the `"video"` field, add:

```json
"transition": { "primary": "crossfade", "duration": 0.4, "easing": "power2.inOut" }
```

- [ ] **Step 2: Insert a `## Transitions` prose section above the JSON block**

Place between `## Typography` and `## Motion`:

```markdown
## Transitions

The channel's primary scene-to-scene transition is a 0.4 s crossfade with `power2.inOut` easing — calm, neutral, non-disruptive. This matches the "calm / brand story" energy bucket from `tools/hyperframes-skills/hyperframes/references/transitions.md`. Per HF's non-negotiable rules, every multi-scene composition uses transitions; jump cuts are a bug. Bolder primaries (`blur-crossfade`, `push-slide`, `zoom-through`) are catalog-spelled and reserved for episodes whose mood explicitly calls for them.
```

- [ ] **Step 3: Extend the `## Colors` section with a base-palette declaration**

Insert immediately after the role list, before the JSON fence:

```markdown
**Base palette:** custom — not a derivative of any catalog palette in `tools/hyperframes-skills/hyperframes/palettes/`. The frosted-glass-on-dark aesthetic is channel-specific. If a palette deviation is requested per-episode, document it in that episode's `notes.md`; never override DESIGN.md's tokens.
```

- [ ] **Step 4: Extend the `## Typography` section with the Inter rationale**

Append after the existing two bullets:

```markdown
**Inter override (intentional):** HF's `references/typography.md` lists Inter on the banned-fonts catalogue (it's an over-used default). We override deliberately: the channel's calm-technical voice is well-served by a neutral grotesque, and Inter's tabular-nums + display variants cover our needs without introducing a second family. Re-evaluate during channel rebrands; do not switch silently.
```

- [ ] **Step 5: Extend `## What NOT to Do` with shader-compat anti-patterns**

Add new numbered items after the existing five:

```markdown
6. **No `var(--…)` on captured elements.** html2canvas (used by shader transitions) does not reliably resolve custom properties. The compositor inlines literal hex/RGBA into element styles. `:root { --… }` declarations may exist in `<head>` for documentation/fallback, but no element style consumed by capture references them via `var()`.
7. **No `transparent` keyword in gradients.** Canvas interpolates `transparent` as `rgba(0,0,0,0)` — black at zero alpha — creating dark fringes. Use the target colour at zero alpha: `rgba(255,255,255,0)`, never `transparent`.
8. **No gradient backgrounds on elements thinner than 4 px.** Canvas can't match CSS gradient rendering at 1–2 px. Use a solid `background-color` on thin accent lines.
9. **Mark uncapturable decorative elements with `data-no-capture`.** They render in the live DOM but skip the shader texture; use this for elements that violate the rules above.
10. **No gradient opacity below 0.15.** Below 10 % opacity, canvas and CSS render gradients differently. Bump to 0.15+ or use a solid colour at equivalent brightness.
11. **Every `.scene` div carries an explicit `background-color`** matching the `init({ bgColor })` config. Without both, the scene texture renders as black.
```

- [ ] **Step 6: Verify the JSON still parses**

Run: `cd tools/compositor && npx vitest run test/designMd.test.ts`
Expected: PASS — all existing tests + readTransitionConfig.

- [ ] **Step 7: Commit**

```bash
git add DESIGN.md
git commit -m "docs(design): transition block, base palette, Inter rationale, shader-compat

- Adds optional 'transition' to hyperframes-tokens JSON, defaulted to a
  0.4s crossfade matching the channel's calm energy.
- Documents the custom-palette decision and the deliberate Inter override
  against HF's banned list.
- Codifies the shader-compat CSS rules from references/transitions.md as
  anti-patterns 6–11 in 'What NOT to Do', forward-protecting bespoke
  6b sub-compositions before shader transitions are adopted."
```

### Task E2: Create `standards/typography.md`

**Files:**
- Create: `standards/typography.md`

- [ ] **Step 1: Write the file**

```markdown
# Typography standards

Compensation rules drawn from `tools/hyperframes-skills/hyperframes/references/typography.md`. Apply to every text-bearing sub-composition (captions, titles, lower-thirds, plate copy, future bespoke seams).

## Weight contrast (display vs body)

Pair display weight 700–900 against body/caption weight 400–500. Same-weight stacks read flat on small mobile renders.

| Role | Family | Weight |
|------|--------|--------|
| Display / headline | Inter Display | 700–900 |
| Body / supporting | Inter | 400–500 |
| Caption (active) | Inter | 700 |
| Caption (inactive / muted) | Inter | 500 |

## Tracking (display sizes)

Display copy at 96 px+ tracks tighter to feel intentional, not stretched.

- 96–144 px: `letter-spacing: -0.03em`
- 144 px+:   `letter-spacing: -0.04em` to `-0.05em`

Body copy at ≤64 px uses default tracking. Tabular-nums on numeric columns.

## Dark-background weight compensation

Light text on dark surfaces appears thinner than the same weight on light surfaces. **Bump body and caption weights by one step** when on dark surfaces (which is the default for our talking-head footage):

- Body: 400 → 500
- Caption: 500 → 600 (or stay at 700 for active captions)

This is load-bearing for legibility — captions over the talking-head plate look "fine but slightly off" without it.

## The Inter override

HF's `references/typography.md` lists Inter on the banned-fonts catalogue. We override deliberately; see `DESIGN.md` § Typography for the rationale. Do not switch silently during episode polish — that is a brand decision, not a copy edit.
```

- [ ] **Step 2: Verify the file lands**

Run: `ls standards/typography.md`
Expected: file exists.

- [ ] **Step 3: Commit**

```bash
git add standards/typography.md
git commit -m "docs(standards): add typography compensation rules

Weight contrast, tracking, dark-bg compensation, Inter override
rationale. Drawn from HF references/typography.md but adapted to our
channel's frosted-glass-on-dark default."
```

### Task E3: Create `standards/bespoke-seams.md`

**Files:**
- Create: `standards/bespoke-seams.md`

- [ ] **Step 1: Write the file**

```markdown
# Bespoke seam authoring guide

For Phase 6b coding subagents (and humans authoring per-seam sub-compositions). The captions sub-composition (`tools/compositor/src/captionsComposition.ts`) is the reference example — read it before writing a new sub-composition.

## Layout before animation

Source: `tools/hyperframes-skills/hyperframes/SKILL.md` §"Layout Before Animation".

Position every element at its **hero-frame** in static CSS first. Then animate *toward* that position with `gsap.from()`. Never use `position: absolute; top: Npx` on a content container as a layout primitive — that's a layout bug masquerading as motion.

```html
<!-- correct: hero-frame in CSS, animate from offset -->
<div class="title">…</div>
<style>.title { position: absolute; left: 50%; top: 40%; transform: translate(-50%, -50%); }</style>
<script>gsap.from(".title", { y: 40, autoAlpha: 0, duration: 0.4 });</script>
```

## Scene phases (build / breathe / resolve)

Source: `tools/hyperframes-skills/hyperframes/references/motion-principles.md`.

Every multi-second seam allocates time across three phases:

- **0–30 % entrance:** elements fade/slide/scale in.
- **30–70 % breathe:** held still — no idle motion, no looping shimmer.
- **70–100 % resolve:** outgoing scene is fully visible; the seam transition (handled by `transitions.html`) is the exit. No per-element fade-out tweens.

Dumping all motion at `t=0` and holding for the rest of the seam is a bug.

## fitTextFontSize is the canonical overflow primitive

Source: `tools/hyperframes-skills/hyperframes/references/captions.md`.

For any dynamic-content text (caption groups, lower-thirds, name plates, overlay headers, bespoke seam copy), call `window.__hyperframes.fitTextFontSize(el, { maxFontSize, minFontSize })` on first show. This sizes the text to the available canvas without overflow and without manual font-size juggling.

**Anti-patterns:**
- Per-comp font-size clamps (`Math.min(window.innerWidth/N, …)`).
- `text-overflow: ellipsis` as the overflow strategy.
- Hand-tuned `font-size: clamp(...)` rules per text element.

## Shader-compat CSS rules

Even if the seam doesn't use shader transitions today, follow these rules so 6b can adopt them later without an audit. See `DESIGN.md` § "What NOT to Do" items 6–11 for the full list:

- Literal hex/RGBA in element styles, no `var(--…)`.
- No `transparent` keyword in gradients — use `rgba(target,0)`.
- No gradients on elements thinner than 4 px.
- Mark uncapturable decorative elements with `data-no-capture`.
- No gradient opacity below 0.15.
- Every `.scene` div has explicit `background-color`.

## Inspect annotations

Use `data-layout-allow-overflow` on entrance/exit-animated elements that legitimately overflow the canvas during their tween. Use `data-layout-ignore` on purely decorative elements that should not be audited at all. Do NOT weaken the inspect gate at the script level — annotate at source.
```

- [ ] **Step 2: Commit**

```bash
git add standards/bespoke-seams.md
git commit -m "docs(standards): add bespoke seam authoring guide for Phase 6b"
```

### Task E4: Rewrite `standards/motion-graphics.md`

**Files:**
- Modify: `standards/motion-graphics.md`

- [ ] **Step 1: Read the current file**

Run: `cat standards/motion-graphics.md`

- [ ] **Step 2: Replace `tokens.*` references with DESIGN.md token paths**

Mechanical substitutions throughout the file:

| Old | New |
|-----|-----|
| `tokens.color.glass.fill`   | `color.glass.fill` (resolved from DESIGN.md) |
| `tokens.color.glass.stroke` | `color.glass.stroke` |
| `tokens.color.glass.shadow` | `color.glass.shadow` |
| `tokens.blur.glass-sm` / `tokens.blur.glass-md` / `tokens.blur.glass-lg` | `blur.glass-sm` / `blur.glass-md` / `blur.glass-lg` |
| `tokens.radius.sm/md/lg/pill` | `radius.sm/md/lg/pill` |
| `tokens.spacing.xs/sm/md/lg/xl` | `spacing.xs/sm/md/lg/xl` |

Also rewrite any prose like "see `tokens/tokens.json`" to "see `DESIGN.md` `hyperframes-tokens` JSON block".

- [ ] **Step 3: Add the "Layout Before Animation" and "Scene phases" sections**

Append at the end of the file:

```markdown
## Layout Before Animation

Source: `tools/hyperframes-skills/hyperframes/SKILL.md#layout-before-animation`.

Position elements at their hero-frame in static CSS first. Animate *toward* that position with `gsap.from()`. Never use `position: absolute; top: Npx` on a content container as a layout primitive. See `standards/bespoke-seams.md` for the canonical pattern.

## Scene phases (build / breathe / resolve)

Source: `tools/hyperframes-skills/hyperframes/references/motion-principles.md`.

Every multi-second seam allocates ~0–30 % entrance, ~30–70 % ambient breathe, ~70–100 % resolve. The seam-to-seam transition (handled by `transitions.html`) is the exit; per-element fade-outs before a transition are a bug.
```

- [ ] **Step 4: Verify**

Run: `grep -n "tokens\." standards/motion-graphics.md || true`
Expected: no `tokens.<word>` matches remain.

Run: `grep -n "Layout Before Animation\|Scene phases" standards/motion-graphics.md`
Expected: both anchors found.

- [ ] **Step 5: Commit**

```bash
git add standards/motion-graphics.md
git commit -m "docs(standards): rewrite tokens.* refs + add HF-native sections

Drops the deleted tokens.* namespace; references DESIGN.md's
hyperframes-tokens keys instead. Adds Layout-Before-Animation and Scene
phases sections so 6b agents have a single canonical entry point for
the HF methodology gates."
```

### Task E5: Rewrite `standards/captions.md`

**Files:**
- Modify: `standards/captions.md`

- [ ] **Step 1: Read current file**

Run: `cat standards/captions.md`

- [ ] **Step 2: Mechanical token substitutions**

| Old | New |
|-----|-----|
| `tokens.color.caption.active` | `color.caption.active` (DESIGN.md) |
| `tokens.color.caption.inactive` | `color.caption.inactive` |
| `tokens.safezone.bottom` | `safezone.bottom` |
| `tokens.safezone.side` | `safezone.side` |
| `tokens.type.family.caption` | `type.family.caption` |
| `tokens.type.size.caption` | `type.size.caption` |
| `tokens.type.weight.bold` | `type.weight.bold` |

Replace any `tokens/tokens.json` reference with `DESIGN.md (hyperframes-tokens block)`.

- [ ] **Step 3: Add a one-line note pointing to bespoke-seams.md for the overflow primitive**

After the paragraph discussing caption sizing/overflow:

```markdown
For overflow, captions call `window.__hyperframes.fitTextFontSize` per group on first show — the project-wide primitive. See `standards/bespoke-seams.md` for the rationale and anti-patterns.
```

- [ ] **Step 4: Verify**

Run: `grep -n "tokens\." standards/captions.md || true`
Expected: no matches.

- [ ] **Step 5: Commit**

```bash
git add standards/captions.md
git commit -m "docs(standards): rewrite captions.md tokens.* refs to DESIGN.md keys"
```

### Task E6: Rewrite `design-system/README.md`

**Files:**
- Modify: `design-system/README.md`

- [ ] **Step 1: Replace the file contents**

Overwrite with:

```markdown
# design-system/

Phase 6b layout-shell home. **Currently empty** — populated when Phase 6b's agentic graphics planner lands.

## Phase 6a state (current)

- **Visual contract source of truth:** `DESIGN.md` at the repo root (the `hyperframes-tokens` JSON block + prose). The compositor parses this directly; the legacy `tokens/tokens.json` was deleted in 6a.
- **Compositor:** `tools/compositor/src/` reads DESIGN.md, parses seam-plan, emits `index.html` + `compositions/captions.html` + `compositions/transitions.html` + per-seam `compositions/seam-<id>.html` (when authored), plus `hyperframes.json` and `meta.json`.
- **Standards:** `standards/{motion-graphics,captions,typography,bespoke-seams,pipeline-contracts}.md` carry the editorial / methodology layer.
- **Vendored HF skills:** `tools/hyperframes-skills/` (read-only, version-pinned to `tools/compositor/package.json`).

## What goes here in Phase 6b

- `design-system/components/` — layout-shell sub-compositions for `split` and `overlay` scene modes (e.g., `split-frame.html`, `overlay-plate.html`). These hold the brand-level frame; per-seam bespoke fills live in each episode's `compositions/seam-<id>.html`.
- Catalog of named patterns (lower-third, name-plate, broll-frame) the agentic planner can compose from.

Do NOT add `tokens/`, `tokens.json`, or any other parallel design-token file — DESIGN.md is the contract.
```

- [ ] **Step 2: Commit**

```bash
git add design-system/README.md
git commit -m "docs(design-system): rewrite README to lead with 6a state"
```

### Task E7: Update AGENTS.md

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Read current AGENTS.md**

Run: `grep -n "composition.html\|stage-2-composite\|Pipeline overview" AGENTS.md`

- [ ] **Step 2: Rename `composition.html` → `index.html`**

Replace each Stage 2 reference. Verify no occurrences remain except those that explicitly call out the FROZEN pilot.

- [ ] **Step 3: Add the FROZEN-pilot note**

Insert after the Pipeline overview:

```markdown
> **FROZEN pilot caveat.** `episodes/2026-04-27-desktop-software-licensing-it-turns-out/` predates Phase 6a and ships a non-canonical Stage 2 layout (`composition.html`, `hf-project/` staging dir, no `hyperframes.json`/`meta.json`). Do not use it as a reference for compositor output, lint settings, or directory structure. The smoke-test fixture `episodes/2026-04-28-phase-6a-smoke-test/` is the canonical example.
```

- [ ] **Step 4: Add the `HF_RENDER_MODE` env-var doc**

Insert into the section discussing Stage 2 rendering:

```markdown
### Render modes

By default, Stage 2 preview/final rendering uses Docker (`hyperframes render --docker`) for memory-safe execution on Windows hosts. Contributors without Docker installed can opt out:

```
HF_RENDER_MODE=local tools/scripts/run-stage2-preview.sh <slug>
```

Local mode falls back to `--workers 1 --max-concurrent-renders 1 -q draft` to bound RAM. Do not change these knobs without re-running the smoke test on a memory-pressured host.
```

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): rename composition.html, FROZEN-pilot note, HF_RENDER_MODE"
```

### Task E8: Add FROZEN-pilot note to `standards/pipeline-contracts.md`

**Files:**
- Modify: `standards/pipeline-contracts.md`

- [ ] **Step 1: Append the FROZEN-pilot note in the Stage 2 section**

```markdown
> **FROZEN pilot caveat.** `episodes/2026-04-27-desktop-software-licensing-it-turns-out/stage-2-composite/` is non-canonical (predates Phase 6a; uses `composition.html` + `hf-project/`). The canonical contract below is what `run-stage2-compose.sh` emits today: `index.html`, `compositions/captions.html`, `compositions/transitions.html`, `compositions/seam-<id>.html`, `hyperframes.json`, `meta.json`, `seam-plan.md`.
```

- [ ] **Step 2: Commit**

```bash
git add standards/pipeline-contracts.md
git commit -m "docs(contracts): note FROZEN pilot non-canonicality + 6a-aftermath outputs"
```

---

## Phase F — Operational scripts: preflight, Docker, strict inspect, test fixes

### Task F1: Create `tools/scripts/lib/preflight.sh`

**Files:**
- Create: `tools/scripts/lib/preflight.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# Sourced by run-stage2-compose.sh / run-stage2-preview.sh / render-final.sh.
# Runs `npx hyperframes doctor` and exits the calling shell on critical
# failures.
#
# Critical failures (always fatal):  Node, FFmpeg, Chrome.
# Conditional failures (fatal only when HF_RENDER_MODE != local):
#   Docker, Docker running.
#
# HF_RENDER_MODE defaults to docker. Set HF_RENDER_MODE=local to bypass
# Docker checks (e.g., on hosts without Docker installed).

hf_preflight() {
  local mode="${HF_RENDER_MODE:-docker}"
  local out
  out="$(npx -y hyperframes doctor 2>&1 || true)"

  if echo "$out" | grep -E "^\s*✗\s+(Node\.js|FFmpeg|FFprobe|Chrome)\b" >/dev/null; then
    echo "[preflight] Critical doctor check failed:"
    echo "$out" | grep -E "^\s*✗\s+(Node\.js|FFmpeg|FFprobe|Chrome)\b"
    return 1
  fi

  if [ "$mode" != "local" ]; then
    if echo "$out" | grep -E "^\s*✗\s+Docker(\s+running)?\b" >/dev/null; then
      echo "[preflight] Docker check failed (HF_RENDER_MODE=docker default):"
      echo "$out" | grep -E "^\s*✗\s+Docker(\s+running)?\b"
      echo "[preflight] To bypass: rerun with HF_RENDER_MODE=local"
      return 1
    fi
  fi

  echo "[preflight] hyperframes doctor OK (mode=$mode)"
  return 0
}
```

- [ ] **Step 2: Verify it sources cleanly**

Run: `bash -c 'source tools/scripts/lib/preflight.sh && hf_preflight && echo OK'`
Expected: prints `[preflight] hyperframes doctor OK (mode=docker)` then `OK`. (If Docker is not installed, retry with `HF_RENDER_MODE=local bash -c '...'`.)

- [ ] **Step 3: Commit**

```bash
git add tools/scripts/lib/preflight.sh
git commit -m "feat(scripts): add hf_preflight shared library"
```

### Task F2: Update `run-stage2-compose.sh`

**Files:**
- Modify: `tools/scripts/run-stage2-compose.sh`

- [ ] **Step 1: Source preflight at the top**

After `set -euo pipefail`, before the slug check:

```bash
# shellcheck source=tools/scripts/lib/preflight.sh
. "$(dirname "$0")/lib/preflight.sh"
hf_preflight || { echo "ERROR: doctor preflight failed; aborting compose"; exit 1; }
```

- [ ] **Step 2: Restore strict inspect**

Replace the `inspect` and `validate` lines (currently downgraded to WARN):

```bash
npx hyperframes validate "$COMPOSITE_DIR" || { echo "ERROR: hyperframes validate failed"; exit 1; }
npx hyperframes inspect "$COMPOSITE_DIR" --json > "$COMPOSITE_DIR/.inspect.json" || {
  echo "ERROR: hyperframes inspect failed; see $COMPOSITE_DIR/.inspect.json"
  echo "       annotate intentional overflow with data-layout-allow-overflow / data-layout-ignore"
  exit 1
}
```

- [ ] **Step 3: Add post-emit guard for `var(--…)` on captured elements**

After the gates block, add:

```bash
# Captured-element guard: shader-compat rule forbids var() in inline styles
# and class rules consumed by html2canvas. The :root { --… } docs are fine.
if grep -REn 'style="[^"]*var\(--' "$COMPOSITE_DIR/index.html" "$COMPOSITE_DIR/compositions"/*.html >/dev/null; then
  echo "ERROR: var(--…) found in inline style attribute on a captured element."
  echo "       Resolve via designMd.resolveToken at compose time; see DESIGN.md 'What NOT to Do' #6."
  grep -REn 'style="[^"]*var\(--' "$COMPOSITE_DIR/index.html" "$COMPOSITE_DIR/compositions"/*.html
  exit 1
fi
```

- [ ] **Step 4: Smoke-test the script**

Run: `bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test`
Expected: exits 0; preflight prints OK; lint/validate/inspect/animation-map all pass; var() guard passes.

If `inspect` flags real overflow on `compositions/seam-4.html`, defer to Task G3.

- [ ] **Step 5: Commit**

```bash
git add tools/scripts/run-stage2-compose.sh
git commit -m "fix(scripts): preflight + strict inspect + var() guard"
```

### Task F3: Update `run-stage2-preview.sh`

**Files:**
- Modify: `tools/scripts/run-stage2-preview.sh`

- [ ] **Step 1: Source preflight, branch on `HF_RENDER_MODE`**

After the existing arg parsing, before the render call:

```bash
# shellcheck source=tools/scripts/lib/preflight.sh
. "$(dirname "$0")/lib/preflight.sh"
hf_preflight || { echo "ERROR: doctor preflight failed; aborting preview"; exit 1; }

HF_RENDER_MODE="${HF_RENDER_MODE:-docker}"
RENDER_FLAGS=()
if [ "$HF_RENDER_MODE" = "docker" ]; then
  RENDER_FLAGS+=(--docker)
elif [ "$HF_RENDER_MODE" = "local" ]; then
  WORKERS=1
  QUALITY=draft
else
  echo "ERROR: HF_RENDER_MODE must be 'docker' or 'local' (got '$HF_RENDER_MODE')"
  exit 1
fi
```

- [ ] **Step 2: Pass `${RENDER_FLAGS[@]}` to the render call**

```bash
npx -y hyperframes render "$COMPOSITE_DIR" \
  -o preview.mp4 \
  -f "$FPS" \
  -q "$QUALITY" \
  --format mp4 \
  --workers "$WORKERS" \
  --max-concurrent-renders 1 \
  "${RENDER_FLAGS[@]}" || { echo "ERROR: hyperframes render failed"; exit 1; }
```

- [ ] **Step 3: Verify in both modes**

Docker mode:
Run: `bash tools/scripts/run-stage2-preview.sh 2026-04-28-phase-6a-smoke-test --draft`
Expected: render via Docker; `preview.mp4` produced.

Local mode:
Run: `HF_RENDER_MODE=local bash tools/scripts/run-stage2-preview.sh 2026-04-28-phase-6a-smoke-test --draft`
Expected: render via local Chromium; `preview.mp4` produced.

- [ ] **Step 4: Commit**

```bash
git add tools/scripts/run-stage2-preview.sh
git commit -m "fix(scripts): preflight + Docker render default"
```

### Task F4: Update `render-final.sh`

**Files:**
- Modify: `tools/scripts/render-final.sh`

- [ ] **Step 1: Read current render-final.sh**

Run: `cat tools/scripts/render-final.sh`

- [ ] **Step 2: Apply the same preflight + Docker pattern**

If `render-final.sh` shells `hyperframes render` directly, mirror Task F3's structure: source preflight, branch on `HF_RENDER_MODE`, append `--docker` to render args by default.

If it shells `run-stage2-preview.sh`, the change is just sourcing preflight at the top.

- [ ] **Step 3: Smoke-test**

Run: `bash tools/scripts/render-final.sh --help`
Expected: prints usage without errors.

- [ ] **Step 4: Commit**

```bash
git add tools/scripts/render-final.sh
git commit -m "fix(scripts): preflight + Docker default for final render"
```

### Task F5: Fix `test-run-stage2.sh` and delete `run-stage2.sh`

**Files:**
- Modify: `tools/scripts/test/test-run-stage2.sh`
- Delete: `tools/scripts/run-stage2.sh`

- [ ] **Step 1: Read the current test**

Run: `cat tools/scripts/test/test-run-stage2.sh`

- [ ] **Step 2: Fix the assertion**

Replace `composition.html` with `index.html` in the assertion line.

- [ ] **Step 3: Replace the wrapper invocation**

If the test calls `tools/scripts/run-stage2.sh "$SLUG"`, change it to:

```bash
bash tools/scripts/run-stage2-compose.sh "$SLUG"
bash tools/scripts/run-stage2-preview.sh "$SLUG" --draft
```

- [ ] **Step 4: Run the test**

Run: `bash tools/scripts/test/test-run-stage2.sh`
Expected: exits 0.

- [ ] **Step 5: Delete the wrapper**

Run: `git rm tools/scripts/run-stage2.sh`

- [ ] **Step 6: Verify nothing else calls the deleted wrapper**

Run: `grep -REn "run-stage2\.sh" tools/ docs/ AGENTS.md standards/ 2>&1 | grep -v "run-stage2-compose\|run-stage2-preview" || echo "no stale references"`
Expected: prints `no stale references`.

- [ ] **Step 7: Commit**

```bash
git add tools/scripts/test/test-run-stage2.sh
git rm tools/scripts/run-stage2.sh
git commit -m "fix(scripts): re-arm test-run-stage2 + delete obsolete wrapper"
```

### Task F6: Drop the obsolete `.gitignore` line

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Remove the `hf-project/` line**

Edit `.gitignore`: delete the line `episodes/*/stage-2-composite/hf-project/`.

- [ ] **Step 2: Verify**

Run: `grep -n "hf-project" .gitignore || echo "removed"`
Expected: prints `removed`.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: drop obsolete hf-project gitignore rule (removed in 6a)"
```

---

## Phase G — Comments + smoke-fixture annotations

### Task G1: Add `// TODO(6b)` comments

**Files:**
- Modify: `tools/compositor/src/types.ts`
- Modify: `tools/compositor/src/seamPlanWriter.ts`

- [ ] **Step 1: Annotate `Seam.graphic`**

In `tools/compositor/src/types.ts`, just above the `graphic?:` field:

```typescript
export interface Seam {
  index: number;
  at_ms: number;
  scene: SceneMode;
  // TODO(6b): consumed by the agentic graphics planner; currently round-trip
  // only — the compositor selects per-seam HTML by file existence, not by
  // reading this field. Do not delete as "unused".
  graphic?: {
    component: string;
    data: Record<string, unknown>;
  };
  ends_at_ms: number;
}
```

- [ ] **Step 2: Annotate the `graphic:` line round-trip in `seamPlanWriter.ts`**

In the read/write code that handles `graphic:`, add the same TODO above the relevant block.

- [ ] **Step 3: Commit**

```bash
git add tools/compositor/src/types.ts tools/compositor/src/seamPlanWriter.ts
git commit -m "chore(compositor): mark Seam.graphic + writer as 6b-reserved"
```

### Task G2: Add transitional-shim comment to `sceneMode.ts`

**Files:**
- Modify: `tools/compositor/src/sceneMode.ts`

- [ ] **Step 1: Annotate the `full` rejection**

Above the `full` rejection block:

```typescript
// Transitional shim: the legacy `full` scene-mode name is rejected here so a
// stale seam-plan.md fails fast instead of silently misbehaving. Remove once
// the FROZEN pilot is unfrozen and re-cut on 6a-aftermath (no other producer
// emits `full`).
```

- [ ] **Step 2: Commit**

```bash
git add tools/compositor/src/sceneMode.ts
git commit -m "chore(compositor): document the legacy 'full' scene-mode shim"
```

### Task G3: Annotate the smoke-test seam-4 fixture if needed

**Files:**
- Maybe-modify: `episodes/2026-04-28-phase-6a-smoke-test/stage-2-composite/compositions/seam-4.html`

- [ ] **Step 1: Run compose to surface any flags**

Run: `bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test`
If it succeeds, skip to step 4.
If it fails on `inspect` for a `seam-4.html` element, note the element selector and reason from `.inspect.json`.

- [ ] **Step 2: Add `data-layout-allow-overflow` to legitimately overflowing elements**

For each flagged element whose overflow is intentional:

```html
<div class="frosted-plate" data-layout-allow-overflow>…</div>
```

For purely decorative elements, use `data-layout-ignore`.

- [ ] **Step 3: Re-run compose**

Run: `bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test`
Expected: exits 0.

- [ ] **Step 4: Commit (if changed)**

```bash
git add episodes/2026-04-28-phase-6a-smoke-test/stage-2-composite/compositions/seam-4.html
git commit -m "fix(smoke): annotate seam-4 entrance overflow for strict inspect"
```

---

## Phase H — Upgrade docs + contract surface registry

### Task H1: Create `docs/hyperframes-upgrade.md`

**Files:**
- Create: `docs/hyperframes-upgrade.md`

- [ ] **Step 1: Write the doc**

```markdown
# HyperFrames upgrade procedure

Single PR per upgrade. The version of `hyperframes` resolved at runtime, the version of skills vendored at `tools/hyperframes-skills/`, and the contract surface in `docs/hyperframes-integration.md` must all stay in sync.

## When to upgrade

`tools/scripts/check-updates.sh` notices upstream versions newer than the local pin and prints a one-line note. That note is the trigger; do not bump on a whim.

## Procedure

1. **Bump the pin.** Edit `tools/compositor/package.json` `dependencies.hyperframes` to the new exact version (no caret, no tilde). Run `cd tools/compositor && npm install` to refresh the lockfile.

2. **Sync the skills.** Run `bash tools/scripts/sync-hf-skills.sh`. The script reads the new pinned version from `package.json` and refreshes `tools/hyperframes-skills/` + `VERSION` to match. If the script aborts on a non-exact pin, recheck step 1.

3. **Read the skills diff.** `git diff tools/hyperframes-skills/`. Pay particular attention to:
   - `SKILL.md` "non-negotiable" sections — new mandatory rules are methodology events.
   - New files under `references/` — new authoring patterns.
   - Removed APIs or deprecated patterns.
   - Changes to runtime globals (`window.__hyperframes.*`).
   Capture every methodology change in the PR description.

4. **Run doctor.** `npx hyperframes doctor` against the local host. All critical checks (Node, FFmpeg, Chrome) must pass. Docker passes only if `HF_RENDER_MODE` defaults to docker.

5. **Run the smoke test (mandatory).**

   ```bash
   bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test
   bash tools/scripts/run-stage2-preview.sh 2026-04-28-phase-6a-smoke-test --draft
   ```

   Both must exit 0 with `lint`/`validate`/`inspect`/`animation-map` green and `preview.mp4` rendering. If anything regresses, fix in the same PR or revert the bump.

6. **Update `docs/hyperframes-integration.md`** if the diff in step 3 added/removed any contract-surface entry (CLI flag, DOM attribute, runtime global, JSON schema, methodology rule).

7. **Open the PR.** Title: `chore(hf): upgrade to <version>`. Body lists methodology changes from step 3.

## Cadence

Operator-driven. A `/schedule`-able background agent that opens upgrade PRs on a cadence is a follow-up after Phase 6a-aftermath; not in this phase.
```

- [ ] **Step 2: Commit**

```bash
git add docs/hyperframes-upgrade.md
git commit -m "docs: HyperFrames upgrade procedure"
```

### Task H2: Create `docs/hyperframes-integration.md`

**Files:**
- Create: `docs/hyperframes-integration.md`

- [ ] **Step 1: Write the registry**

```markdown
# HyperFrames integration — contract surface

The single living document of HF surfaces this project depends on. During an HF version upgrade (see `docs/hyperframes-upgrade.md`), changes to anything below are a methodology event, not a routine bump.

## Pinned version

- CLI: `tools/compositor/package.json` `dependencies.hyperframes` (exact pin, no caret).
- Skills: `tools/hyperframes-skills/VERSION` — must equal the CLI pin.

## CLI commands and parsed flags

We invoke and parse output from:

- `hyperframes lint <dir>` — pass/fail; failure aborts compose.
- `hyperframes validate <dir>` — pass/fail; failure aborts compose.
- `hyperframes inspect <dir> --json` — JSON written to `.inspect.json`; non-zero exit aborts compose.
- `hyperframes animation-map <dir>` — informational; via `tools/hyperframes-skills/hyperframes/scripts/animation-map.mjs`.
- `hyperframes render <dir> -o <name> -f <fps> -q <quality> --format mp4 --workers <n> --max-concurrent-renders <n> [--docker]` — `--docker` is the default render mode.
- `hyperframes doctor` — parsed by `tools/scripts/lib/preflight.sh`.

## DOM data-attributes

- `data-composition-id`, `data-composition-src`
- `data-start`, `data-duration`
- `data-width`, `data-height`
- `data-track-index`
- `data-layout-allow-overflow`, `data-layout-ignore`
- `data-no-capture` (reserved for shader-transition adoption)

## Runtime globals

- `window.__timelines["<id>"]` — timeline registration; `<id>` matches `data-composition-id`.
- `window.__hyperframes.fitTextFontSize(el, { maxFontSize, minFontSize })` — overflow primitive used by captions.

## JSON schemas

- `hyperframes.json` (per-episode `stage-2-composite/`) — `{ $schema, registry, paths: { blocks, components, assets } }`.
- `meta.json` (per-episode `stage-2-composite/`) — `{ id, name, createdAt }`.

## Methodology rules from SKILL.md / references

Pointers; the source files are authoritative. We propagate these into our standards:

- **Visual Identity Gate ordering** (`SKILL.md`) — DESIGN.md is consulted first.
- **Composition Structure** (`SKILL.md`) — `<template>`, scoped styles, `window.__timelines["<id>"]` registration.
- **Scene Transitions Non-Negotiable** (`SKILL.md`, `references/transitions.md`) — every multi-scene composition uses transitions.
- **Captions authoring rules** (`references/captions.md`) — word grouping, per-group hard-kill, `fitTextFontSize`, post-build self-lint.
- **Animation entrance/exit policy** (`SKILL.md`, `references/motion-principles.md`) — entrance on every scene; exits banned except final scene; build/breathe/resolve phasing.
- **Layout Before Animation** (`SKILL.md`) — hero-frame in static CSS, animate from offset.
- **Shader-compat CSS rules** (`references/transitions.md`) — literal hex/RGBA, no `transparent` keyword in gradients, `data-no-capture` for uncapturable elements.
- **Typography compensation** (`references/typography.md`) — weight contrast, tracking, dark-bg compensation; codified in `standards/typography.md`.

## Update protocol

When step 3 of the upgrade procedure (`docs/hyperframes-upgrade.md`) finds a methodology change, update the relevant section above in the same PR. Empty diffs are fine; out-of-date sections are not.
```

- [ ] **Step 2: Commit**

```bash
git add docs/hyperframes-integration.md
git commit -m "docs: HyperFrames contract surface registry"
```

---

## Phase I — End-to-end verification

### Task I1: Full smoke-test run

**Files:** none (verification only)

- [ ] **Step 1: Compose**

Run: `bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test`
Expected: exits 0; preflight OK; lint/validate/inspect/animation-map all green; var() guard passes. Files emitted:
- `episodes/2026-04-28-phase-6a-smoke-test/stage-2-composite/index.html`
- `.../compositions/captions.html`
- `.../compositions/transitions.html`
- `.../hyperframes.json`
- `.../meta.json`

- [ ] **Step 2: Verify single-track + literal hex**

```bash
grep -c 'data-track-index="3"' episodes/2026-04-28-phase-6a-smoke-test/stage-2-composite/index.html
grep -E 'style="[^"]*var\(--' episodes/2026-04-28-phase-6a-smoke-test/stage-2-composite/index.html episodes/2026-04-28-phase-6a-smoke-test/stage-2-composite/compositions/*.html || echo "no var() in inline styles — OK"
```

Expected: at least one `data-track-index="3"`; second command prints `no var() in inline styles — OK`.

- [ ] **Step 3: Preview**

Run: `bash tools/scripts/run-stage2-preview.sh 2026-04-28-phase-6a-smoke-test --draft`
Expected: exits 0; `preview.mp4` produced.

(If Docker is not installed, run with `HF_RENDER_MODE=local`.)

- [ ] **Step 4: Visual sanity check (manual)**

Open `preview.mp4` in a player. Confirm:
- Captions appear in groups, one group at a time.
- No jump cut between seam 3 and seam 4 — there's a brief crossfade through black.
- Seam 4 still shows the "6A WIRING OK" plate.

### Task I2: Doctor preflight failure path

**Files:** none (verification only)

- [ ] **Step 1: Simulate a missing FFmpeg**

Mask `ffmpeg` in PATH temporarily.

- [ ] **Step 2: Run compose, expect a clear preflight failure**

Run: `bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test`
Expected: aborts at preflight with `[preflight] Critical doctor check failed:` + the FFmpeg ✗ line.

- [ ] **Step 3: Restore FFmpeg, verify recovery**

Restore PATH. Run compose again — passes.

### Task I3: Upgrade strategy dry-run

**Files:** none (verification only)

- [ ] **Step 1: Bump to a non-existent version**

Edit `tools/compositor/package.json` to `"hyperframes": "0.4.99"`. **Do NOT run `npm install`.**

- [ ] **Step 2: Run sync — expect a clear failure**

Run: `bash tools/scripts/sync-hf-skills.sh`
Expected: aborts with `ERROR: hyperframes@0.4.99 has no tarball on npm`. Must NOT silently fall back to latest.

- [ ] **Step 3: Restore the pin**

Edit `package.json` back to `"hyperframes": "0.4.31"`. Run `cd tools/compositor && npm install && cd ../..`.

- [ ] **Step 4: Re-run sync to confirm green state**

Run: `bash tools/scripts/sync-hf-skills.sh`
Expected: `Done. Vendored at … (version 0.4.31).`

### Task I4: Final review checklist

**Files:** none (verification only)

- [ ] **Step 1: All compositor tests green**

Run: `cd tools/compositor && npx vitest run`
Expected: PASS for all suites.

- [ ] **Step 2: Static check — no `tokens.*` references in standards/**

Run: `grep -REn "tokens\.[a-z]" standards/ || echo "clean"`
Expected: prints `clean`.

- [ ] **Step 3: Static check — no captured-element `var(--…)` in compositor sources**

Run: `grep -REn 'var\(--' tools/compositor/src/composer.ts tools/compositor/src/captionsComposition.ts tools/compositor/src/transitionsComposition.ts || echo "clean"`
Expected: prints `clean`.

- [ ] **Step 4: All new files exist**

```bash
for f in \
  tools/compositor/src/transitionsComposition.ts \
  tools/compositor/src/groupWords.ts \
  tools/compositor/src/episodeMeta.ts \
  tools/scripts/lib/preflight.sh \
  docs/hyperframes-upgrade.md \
  docs/hyperframes-integration.md \
  standards/typography.md \
  standards/bespoke-seams.md ; do
  [ -f "$f" ] && echo "OK $f" || echo "MISSING $f"
done
```

Expected: every line is `OK`.

- [ ] **Step 5: Deleted files are gone**

```bash
[ ! -f tools/scripts/run-stage2.sh ] && echo "OK run-stage2.sh deleted" || echo "FAIL"
grep -n 'hf-project' .gitignore && echo "FAIL line still present" || echo "OK gitignore line removed"
```

- [ ] **Step 6: AGENTS.md and standards/pipeline-contracts.md carry the FROZEN-pilot note**

```bash
grep -n "FROZEN" AGENTS.md standards/pipeline-contracts.md
```

Expected: at least one match in each file.

- [ ] **Step 7: Commit any post-verification fixes**

```bash
git add -A
git commit -m "fix(phase-6a-aftermath): post-verification cleanup"
```

---

## Self-review notes

- **Spec coverage:** Each spec section maps to tasks. Captions → C1+C2. Transitions → D1+D2+D3. Inspect re-strict → F2 step 2. Doctor preflight → F1+F2+F3+F4. Docker mode → F3+F4. HF upgrade strategy (pin + sync + check-updates + procedure + registry) → A1+A2+H1+H2. Single-track → B3. Literal hex → B1+B2. Standards (motion-graphics, typography, bespoke-seams, captions) → E2+E3+E4+E5. DESIGN.md extensions → E1. hyperframes.json + meta.json → B4. AGENTS.md → E7. design-system/README → E6. pipeline-contracts FROZEN note → E8. Rudiment cleanup (run-stage2.sh delete, gitignore, comments, test fix) → F5+F6+G1+G2.
- **Acceptance criteria 1–14:** All implemented or verified by tasks above. Acceptance #14 (`hyperframes.json` + `meta.json` in smoke fixture) is implicitly verified by I1 step 1.
- **Risks:** Captioning awkward breaks → tunable in `groupWords` (Task C1); not a hard failure path. Default `crossfade` mood mismatch → DESIGN.md `transition` block override. Strict inspect flagging legitimate overflow → annotated at source via Task G3.
- **Type/name consistency:** `groupWords` returns `CaptionGroup[]` with `id`/`startMs`/`endMs`/`words`; the captions composer uses these names verbatim. `resolveToken(tree, dottedPath)` returns `string`; all callers receive strings. `readTransitionConfig` returns `TransitionConfig` with `primary`/`duration`/`easing`; the transitions composer destructures these names. `writeEpisodeMeta` takes `episodeSlug`/`outDir`/`createdAt?`. `hf_preflight` returns 0/non-zero per shell convention; both compose and preview check `|| { abort }`.
