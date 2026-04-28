# Phase 6a-aftermath follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all 12 open follow-ups from the 2026-04-28 Phase 6a-aftermath retrospective on a single feature branch (`phase-6a-followups`) and open one PR against `main`.

**Architecture:** Six commits, each self-contained. After every commit the smoke fixture (`episodes/2026-04-28-phase-6a-smoke-test`) must yield `lint 0/0`, `validate 0/0`, `inspect ok=true`, and `vitest 75/75`. No new behavior is introduced; this is cleanup. One follow-up (#2 Docker render-mode verification) is deferred-with-reason because the dev host has no Docker — captured in a new ops-doc.

**Tech Stack:** TypeScript (compositor, vitest), bash (scripts), `hyperframes@0.4.31` CLI, `@hyperframes/producer@0.4.31` (added in Task 1), Node 20+, npm.

**Spec:** `docs/superpowers/specs/2026-04-28-phase-6a-followups-design.md`

**Branch state at start:** `phase-6a-followups` already created from `main`; spec already committed (commit `de06181`). Every task below adds exactly one commit on top.

---

## Task 0: Baseline verification

**Files:**
- Read only: `tools/compositor/package.json`, `tools/hyperframes-skills/VERSION`

- [ ] **Step 0.1: Confirm branch and clean state**

Run:
```bash
git status -sb
git log --oneline -3
```
Expected: branch shows `## phase-6a-followups`, working tree clean except possibly the two known untracked items (`.claude/`, FROZEN-pilot `hf-project/`). `HEAD` is `de06181 docs(spec): phase-6a-aftermath follow-ups design`.

- [ ] **Step 0.2: Confirm tests + smoke baseline are green**

Run:
```bash
cd tools/compositor && npm test 2>&1 | tail -20
```
Expected: `Test Files  13 passed (13)` and `Tests  75 passed (75)`.

Run:
```bash
cd ../.. && bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test 2>&1 | tail -30
```
Expected (current pre-fix state): `lint`, `validate`, `inspect` all complete; `validate` reports the 5 known WCAG WARN against `#smoke-plate`; an animation-map WARN may also appear (`Cannot find package '@hyperframes/producer'`). `Compose ready:` is the final line, exit code 0.

If anything else fails, STOP and surface the regression — do not proceed.

---

## Task 1: provide `@hyperframes/producer@0.4.31` to vendored skill scripts (closes #1)

**Files:**
- Create: `tools/hyperframes-skills/package.json`
- Create: `tools/hyperframes-skills/.gitignore`
- Generated: `tools/hyperframes-skills/package-lock.json`
- Modify: `tools/scripts/sync-hf-skills.sh`
- Modify: `tools/scripts/check-updates.sh`

**What and why:** Vendored skill scripts at `tools/hyperframes-skills/hyperframes/scripts/animation-map.mjs` and `contrast-report.mjs` import `@hyperframes/producer`. ESM bare-specifier resolution walks from the importing file's directory upward looking for `node_modules/`. Placing the dep in `tools/compositor/node_modules/` does NOT help — it is a sibling of the skill scripts, not an ancestor.

Architecturally, the dep belongs where it is consumed. `tools/hyperframes-skills/` becomes a self-contained vendored subproject with its own `package.json` listing `@hyperframes/producer` as an exact-pin dep, mirroring how the upstream HF monorepo provides the same dep to the same scripts (workspace sibling there → vendored sibling here). The skill scripts' parent walk reaches `tools/hyperframes-skills/node_modules/@hyperframes/producer`. No flags, no `NODE_PATH`, no symlinks, no wrappers.

`sync-hf-skills.sh` previously wiped the entire `tools/hyperframes-skills/` directory before resync. With this change, three subtrees (`gsap/`, `hyperframes/`, `hyperframes-cli/`) come from the upstream tarball and are synced; everything else (`package.json`, `package-lock.json`, `node_modules/`, `VERSION`) is ours and survives sync.

- [ ] **Step 1.1: Create `tools/hyperframes-skills/package.json`**

Write the file with the single exact-pin dep:

```json
{
  "name": "hyperframes-skills",
  "version": "1.0.0",
  "description": "Vendored HyperFrames skill scripts (markdown + helper .mjs). This package.json provides the runtime deps the skill scripts need; sync-hf-skills.sh preserves it on resync.",
  "private": true,
  "dependencies": {
    "@hyperframes/producer": "0.4.31"
  }
}
```

Notes:
- `private: true` — never published.
- The pin matches `hyperframes@0.4.31` in `tools/compositor/package.json` (lockstep).
- `name` is descriptive only; nothing imports this package.

- [ ] **Step 1.2: Create `tools/hyperframes-skills/.gitignore`**

```
node_modules/
```

`package-lock.json` IS tracked (deterministic installs); `node_modules/` is not.

- [ ] **Step 1.3: Install and verify**

Run:
```bash
cd tools/hyperframes-skills && npm install
```

Expected: install completes (puppeteer postinstall downloads Chromium — multi-minute, that is normal). Exit 0. `package-lock.json` and `node_modules/@hyperframes/producer/` exist.

Verify version:
```bash
ls node_modules/@hyperframes/producer/package.json && grep '"version"' node_modules/@hyperframes/producer/package.json
```
Expected: `"version": "0.4.31"`.

- [ ] **Step 1.4: Verify animation-map.mjs now runs without WARN**

Run from repo root:
```bash
cd ../.. && HF_RENDER_MODE=local bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test 2>&1 | tail -40
```

Expected: NO `WARN: animation-map errored; continuing` line; NO `Cannot find package '@hyperframes/producer'` block. Final line is `Compose ready:`. Exit 0.

Verify the output dir:
```bash
ls episodes/2026-04-28-phase-6a-smoke-test/stage-2-composite/.hyperframes/anim-map 2>&1 | head -10
```
Expected: at least one JSON or HTML file present.

- [ ] **Step 1.5: Update `tools/scripts/sync-hf-skills.sh` to preserve our files**

Currently the script does (lines ~50–53):
```bash
rm -rf "$SKILLS_DIR"
mkdir -p "$SKILLS_DIR"
cp -r "$TMP_DIR/package/dist/skills/." "$SKILLS_DIR/"
echo "$VERSION" > "$SKILLS_DIR/VERSION"
```

This nukes our local `package.json`, `package-lock.json`, and `node_modules/` on every sync. Replace with targeted removal of upstream-managed subtrees only.

Tarball `dist/skills/` contains exactly three top-level subtrees: `gsap/`, `hyperframes/`, `hyperframes-cli/` (verified during planning). Remove only those before copy.

Replace the four-line block above with:

```bash
# Sync upstream-managed subtrees only. tools/hyperframes-skills/package.json,
# package-lock.json, and node_modules/ are ours (provide @hyperframes/producer
# to the vendored skill scripts) and must survive resync.
mkdir -p "$SKILLS_DIR"
for subtree in gsap hyperframes hyperframes-cli; do
  rm -rf "$SKILLS_DIR/$subtree"
done
cp -r "$TMP_DIR/package/dist/skills/." "$SKILLS_DIR/"
echo "$VERSION" > "$SKILLS_DIR/VERSION"
```

If a future HF version adds a new top-level subtree under `dist/skills/`, that subtree will simply be cp'd over but never cleaned on subsequent syncs (stale-content risk). Add an inline note: `# If dist/skills/ adds a new top-level dir, append it to the loop above.`

- [ ] **Step 1.6: Update `tools/scripts/check-updates.sh` to read producer pin from new location**

Open `tools/scripts/check-updates.sh`. After the existing `hyperframes` block (~lines 16–23), add a parallel `1b.` block.

Replace this:
```bash
# 1. HyperFrames (npm, 0.x — published frequently per docs/notes/hyperframes-cli.md)
LOCAL_HF="$(node -e "console.log(require('./tools/compositor/package.json').dependencies?.hyperframes || '')" 2>/dev/null | sed 's/^[~^>=]*//')"
if [ -n "$LOCAL_HF" ]; then
  LATEST_HF="$(npm view hyperframes version 2>/dev/null || true)"
  if [ -n "$LATEST_HF" ] && [ "$LOCAL_HF" != "$LATEST_HF" ]; then
    note "hyperframes: pinned $LOCAL_HF, latest $LATEST_HF — review CHANGELOG before upgrade (CLI surface still moving in 0.x)."
  fi
fi
```

With:
```bash
# 1. HyperFrames (npm, 0.x — published frequently per docs/notes/hyperframes-cli.md)
LOCAL_HF="$(node -e "console.log(require('./tools/compositor/package.json').dependencies?.hyperframes || '')" 2>/dev/null | sed 's/^[~^>=]*//')"
if [ -n "$LOCAL_HF" ]; then
  LATEST_HF="$(npm view hyperframes version 2>/dev/null || true)"
  if [ -n "$LATEST_HF" ] && [ "$LOCAL_HF" != "$LATEST_HF" ]; then
    note "hyperframes: pinned $LOCAL_HF, latest $LATEST_HF — review CHANGELOG before upgrade (CLI surface still moving in 0.x)."
  fi
fi

# 1b. @hyperframes/producer — pinned in tools/hyperframes-skills/package.json (where its
#     consumers live). Must move in lockstep with the hyperframes CLI pin.
LOCAL_HFP="$(node -e "console.log(require('./tools/hyperframes-skills/package.json').dependencies?.['@hyperframes/producer'] || '')" 2>/dev/null | sed 's/^[~^>=]*//')"
if [ -n "$LOCAL_HFP" ]; then
  LATEST_HFP="$(npm view @hyperframes/producer version 2>/dev/null || true)"
  if [ -n "$LATEST_HFP" ] && [ "$LOCAL_HFP" != "$LATEST_HFP" ]; then
    note "@hyperframes/producer: pinned $LOCAL_HFP, latest $LATEST_HFP — must move in lockstep with hyperframes pin."
  fi
  if [ -n "$LOCAL_HF" ] && [ "$LOCAL_HF" != "$LOCAL_HFP" ]; then
    note "hyperframes ($LOCAL_HF) and @hyperframes/producer ($LOCAL_HFP) pins disagree — must be identical."
  fi
fi
```

- [ ] **Step 1.7: Smoke-run check-updates.sh**

Run from repo root:
```bash
bash tools/scripts/check-updates.sh
```
Expected: exit 0. Two notices appear (both `hyperframes` and `@hyperframes/producer` pinned at 0.4.31 vs latest 0.4.32). No cross-pin disagreement notice.

- [ ] **Step 1.8: Smoke-run sync-hf-skills.sh and verify our files survived**

Run:
```bash
bash tools/scripts/sync-hf-skills.sh
```
Expected: `Done. Vendored at .../tools/hyperframes-skills (version 0.4.31).` Exit 0.

Verify our files survived:
```bash
ls tools/hyperframes-skills/package.json tools/hyperframes-skills/package-lock.json tools/hyperframes-skills/node_modules/@hyperframes/producer/package.json
```
Expected: all three exist.

Re-run smoke compose to confirm animation-map still resolves:
```bash
HF_RENDER_MODE=local bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test 2>&1 | grep -E "animation-map|Compose ready" | head -5
```
Expected: no `animation-map errored`; `Compose ready:`.

- [ ] **Step 1.9: Re-run vitest**

```bash
cd tools/compositor && npm test 2>&1 | tail -10
```
Expected: 75/75 pass.

- [ ] **Step 1.10: Document the new install step**

Open `AGENTS.md`. Find the section listing first-time setup or pinned-binary install commands (search for `npm install` or `tools/compositor`). Add `tools/hyperframes-skills && npm install` alongside the compositor install step, with a one-line explanation: "Provides @hyperframes/producer to vendored skill scripts (used by animation-map / contrast-report)."

If `AGENTS.md` does not currently document install steps explicitly, add a short subsection under the relevant top-level section, or add the note inline where `tools/compositor/node_modules/.bin/hyperframes` is first mentioned.

- [ ] **Step 1.11: Commit**

Run:
```bash
cd ../.. && git add tools/hyperframes-skills/package.json tools/hyperframes-skills/package-lock.json tools/hyperframes-skills/.gitignore tools/scripts/sync-hf-skills.sh tools/scripts/check-updates.sh AGENTS.md
git commit -m "$(cat <<'EOF'
fix(hf-skills): provide @hyperframes/producer to vendored skill scripts

Vendored HF skill scripts (animation-map.mjs, contrast-report.mjs)
import @hyperframes/producer. ESM bare-specifier resolution walks
from the importing file's directory upward; placing the dep in
tools/compositor/node_modules/ does not work because compositor is
a sibling of the skill scripts, not an ancestor.

Architecturally the dep belongs where it is consumed: introduce
tools/hyperframes-skills/ as a self-contained vendored subproject
with its own package.json declaring @hyperframes/producer at the
exact-pinned 0.4.31 (lockstep with the hyperframes CLI pin in
tools/compositor/package.json). Skill scripts' parent walk now
reaches tools/hyperframes-skills/node_modules/@hyperframes/producer
naturally — no flags, NODE_PATH, symlinks, or wrappers.

sync-hf-skills.sh previously rm -rf'd the entire skills dir before
resync; now it removes only the upstream-managed subtrees
(gsap/, hyperframes/, hyperframes-cli/) so our package.json,
package-lock.json, and node_modules/ survive.

check-updates.sh reads the producer pin from its actual home and
flags both pinned-vs-latest drift and pin-vs-CLI lockstep drift.

AGENTS.md documents the new tools/hyperframes-skills && npm install
step required on fresh checkouts.

Closes 6a-aftermath follow-up #1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: re-narrow FROZEN pilot `hf-project/` in `.gitignore` (closes #12)

**Files:**
- Modify: `.gitignore`

**What and why:** Phase F dropped the wildcard `episodes/*/stage-2-composite/hf-project/` rule. The FROZEN pilot retains its pre-6a `hf-project/` directory; per E7/E8 it must not be touched. Currently it shows as untracked. Add a strictly-scoped ignore for that one historical path so `git status` is clean and any *future* episode that accidentally regenerates `hf-project/` still surfaces.

- [ ] **Step 2.1: Edit `.gitignore`**

Open `.gitignore`. Insert after the `episodes/*/stage-2-composite/final.mp4` line (after line 27, before the `# HyperFrames render scratch dirs at repo root` block):

```
# FROZEN pilot — pre-6a archive, never edited; ignored to keep git status clean.
# See AGENTS.md and standards/pipeline-contracts.md for FROZEN status.
# Strictly scoped to the one historical pilot path so future episodes that
# accidentally regenerate hf-project/ still surface as untracked.
episodes/2026-04-27-desktop-software-licensing-it-turns-out/stage-2-composite/hf-project/
```

- [ ] **Step 2.2: Verify git status is clean**

Run:
```bash
git status
```
Expected: `nothing to commit, working tree clean` OR only `.gitignore` is modified. The previously-untracked `episodes/2026-04-27-…/stage-2-composite/hf-project/` line is gone.

If `.claude/` still shows as untracked, that is a separate session-local directory and is intentionally not in scope.

- [ ] **Step 2.3: Commit**

Run:
```bash
git add .gitignore
git commit -m "$(cat <<'EOF'
chore(gitignore): re-narrow FROZEN pilot hf-project to exact path

Phase F dropped the wildcard episodes/*/stage-2-composite/hf-project/
rule. The FROZEN pilot retains its pre-6a hf-project/ directory and
must not be touched. Add a strictly-scoped ignore for that one path
so git status stays clean while still surfacing accidental
regenerations on any future episode.

Closes 6a-aftermath follow-up #12.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: patch HF 0.4.31 contrast-audit OOB bug (closes #3)

**Files:**
- Modify: `tools/compositor/package.json` (add `patch-package` devDep + `postinstall` script)
- Create: `tools/compositor/patches/hyperframes+0.4.31.patch`
- Modify: `docs/hyperframes-upgrade.md` (new section + bump-time procedure)
- Create: `docs/hyperframes-patches/0.4.31-contrast-audit-oob.md` (upstream issue draft)

**What and why:** Investigation of the 5 WCAG `#smoke-plate` warnings revealed a HF 0.4.31 bug, not a fixture-content issue. `validate --json` returns `ratio: null, fg: rgb(NaN,NaN,NaN), bg: rgb(undefined,undefined,undefined)` — the validator literally cannot compute contrast for elements below the screenshot canvas. Root cause is a missing bounds clamp in HF's inlined `contrast-audit.browser.js` combined with `validate.ts` setting a fixed 1920×1080 viewport regardless of composition height.

The fix patches `node_modules/hyperframes/dist/cli.js` via `patch-package`. The patch survives `npm install` because of the `postinstall: patch-package` script. The smoke-fixture `seam-4.html` is unchanged; the bug was upstream.

- [ ] **Step 3.1: Install `patch-package` as a devDependency**

```bash
cd tools/compositor && npm install --save-dev patch-package
```

Expected: `package.json` `devDependencies` gains `"patch-package": "^8.0.1"` (or whatever current major); `package-lock.json` updated.

- [ ] **Step 3.2: Add the `postinstall` hook**

Edit `tools/compositor/package.json` `scripts` block. After `"render"`, add:

```json
"render": "tsx src/index.ts render",
"postinstall": "patch-package"
```

- [ ] **Step 3.3: Edit the inline contrast-audit script in `node_modules/hyperframes/dist/cli.js`**

Open `tools/compositor/node_modules/hyperframes/dist/cli.js`. The contrast-audit browser script is a single-quoted JS string assigned to `contrast_audit_browser_default` near line 41114. Find the substring (escapes are literal `\n` characters in the source):

```
    var x0 = Math.max(0, Math.floor(rect.x) - 4);\n    var x1 = Math.min(w - 1, Math.ceil(rect.x + rect.width) + 4);\n    var y0 = Math.max(0, Math.floor(rect.y) - 4);\n    var y1 = Math.min(h - 1, Math.ceil(rect.y + rect.height) + 4);
```

Replace with:

```
    // PATCH: skip elements outside the screenshot canvas (HF validate sets viewport=1920x1080 but compositions can be 1440x2560 — DOM rect.y exceeds canvas bounds, OOB reads return undefined → NaN ratio).\n    if (rect.x + rect.width <= 0 || rect.x >= w || rect.y + rect.height <= 0 || rect.y >= h) continue;\n    var x0 = Math.max(0, Math.min(w - 1, Math.floor(rect.x) - 4));\n    var x1 = Math.max(0, Math.min(w - 1, Math.ceil(rect.x + rect.width) + 4));\n    var y0 = Math.max(0, Math.min(h - 1, Math.floor(rect.y) - 4));\n    var y1 = Math.max(0, Math.min(h - 1, Math.ceil(rect.y + rect.height) + 4));
```

- [ ] **Step 3.4: Verify the patch eliminates `null:1` on the smoke fixture**

```bash
tools/compositor/node_modules/.bin/hyperframes validate episodes/2026-04-28-phase-6a-smoke-test/stage-2-composite --json 2>&1 | grep -E "contrastFailures|ratio|fg|bg" | head -10
```

Expected: `"contrastFailures": 0`. No `rgb(NaN` or `rgb(undefined` in output.

- [ ] **Step 3.5: Generate the patch file**

```bash
cd tools/compositor && npx patch-package hyperframes
```

Expected: `✔ Created file patches/hyperframes+0.4.31.patch`. The diff should show only the lines touched in Step 3.3.

- [ ] **Step 3.6: Verify the patch survives a clean reinstall**

```bash
rm -rf node_modules/hyperframes && npm install 2>&1 | tail -10
grep -c "PATCH: skip elements outside" node_modules/hyperframes/dist/cli.js
```

Expected: `npm install` output contains `Applying patches... hyperframes@0.4.31 ✔`. The grep returns `1` (the patch's PATCH-comment is present).

- [ ] **Step 3.7: Re-run smoke compose end-to-end**

```bash
cd ../.. && HF_RENDER_MODE=local bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test 2>&1 | grep -E "WCAG|warning|error|Compose ready" | head -10
```

Expected: `0 errors, 0 warnings`, no `WCAG AA contrast warnings (...)` block, `Compose ready:` final line.

- [ ] **Step 3.8: Re-run vitest**

```bash
cd tools/compositor && npm test 2>&1 | tail -5
```
Expected: 75/75.

- [ ] **Step 3.9: Add the upgrade-procedure docs**

Append a new "## Local patches against `hyperframes`" section to `docs/hyperframes-upgrade.md` listing this patch (root cause, files affected, link to the upstream issue draft) and the bump-time procedure (run the smoke test; if the patch fails to apply, evaluate whether upstream fixed it or whether the diff needs regenerating).

Create `docs/hyperframes-patches/0.4.31-contrast-audit-oob.md` containing the upstream issue draft (reproduction, root cause analysis, suggested minimal + proper fixes). This is the file we will paste when filing the issue against the HF repo.

- [ ] **Step 3.10: Commit**

```bash
cd ../.. && git add tools/compositor/package.json tools/compositor/package-lock.json tools/compositor/patches/hyperframes+0.4.31.patch docs/hyperframes-upgrade.md docs/hyperframes-patches/0.4.31-contrast-audit-oob.md
git commit -m "$(cat <<'EOF'
fix(hf-patch): patch HF 0.4.31 contrast-audit OOB bug

hyperframes validate reports null:1 contrast warnings with
fg=rgb(NaN,...) bg=rgb(undefined,...) for any text element below
y=1080 in the headless viewport. Investigation showed it is not
fixture-content: changing colours, removing var(), inlining styles,
and stripping the entrance tween all produced identical NaN/undefined
output.

Root cause: validate.ts hard-codes page.setViewport(1920, 1080) and
takes the screenshot at viewport size; for a 1440x2560 composition,
elements below y=1080 produce rect.y > canvas.h. The audit script
in contrast-audit.browser.js clamps x0/y0 only against zero, not
against w-1/h-1, so the ring-sampling loop reads OOB on the
Uint8ClampedArray (returns undefined). median() over undefineds
returns undefined; the composite math degrades to NaN.

Patch (via patch-package) adds a fully-out-of-canvas skip and
double-clamps the ring bounds. The smoke fixture validate now
reports 0 contrast failures. Upstream issue draft at
docs/hyperframes-patches/0.4.31-contrast-audit-oob.md will be filed
when publicly tracked.

Closes 6a-aftermath follow-up #3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: defensive guards (closes #8, #10, #11)

**Files:**
- Modify: `tools/compositor/src/transitionsComposition.ts`
- Modify: `tools/scripts/lib/preflight.sh`
- Modify: `tools/scripts/render-final.sh`
- Modify: `tools/compositor/test/transitionsComposition.test.ts`

**What and why:** Three small defensive papercuts grouped because each is a single guarded edit against an edge case today's code does not exercise.

- [ ] **Step 4.1: Add a failing test for the transitions clamp (TDD)**

Open `tools/compositor/test/transitionsComposition.test.ts`. Append at the end of the existing `describe(...)` block (do not replace existing tests):

```typescript
import type { Seam } from "../src/types.js";
import type { TransitionConfig } from "../src/designMd.js";

it("clamps the second tl.to so it never extends past the timeline duration", () => {
  // Degenerate seam ending exactly at totalDurationMs forces the second
  // tl.to call to start within the last `duration/2` window. The clamp
  // must hold the start <= totalSec - duration.
  const seams: Seam[] = [
    { index: 0, at_ms: 0,    ends_at_ms: 9_800, mode: "head" } as Seam,
    { index: 1, at_ms: 9_800, ends_at_ms: 10_000, mode: "head" } as Seam,
  ];
  const transition: TransitionConfig = { primary: "crossfade", duration: 0.4, easing: "power2.inOut" };
  const html = buildTransitionsHtml({ seams, totalDurationMs: 10_000, transition });

  // Extract the second tl.to call's start-time argument from the rendered HTML.
  // Pattern: tl.to(maskEl,   { autoAlpha: 0, ... }, <startSec>);
  const m = html.match(/tl\.to\(maskEl,\s*\{ autoAlpha: 0[\s\S]*?\}, ([0-9.]+)\)/);
  expect(m, "second tl.to call must be present").toBeTruthy();
  const start = Number(m![1]);
  // totalSec=10.000, duration=0.4 → max allowed start = 10.000 - 0.4 = 9.600
  expect(start).toBeLessThanOrEqual(9.6 + 1e-3);
});
```

- [ ] **Step 4.2: Run the new test and confirm it fails**

Run:
```bash
cd tools/compositor && npx vitest run test/transitionsComposition.test.ts 2>&1 | tail -20
```
Expected: the new test FAILS with the second `tl.to` start being `9.800` (or similar — un-clamped), violating the `<= 9.6` assertion.

If it passes accidentally (e.g. because `planSeams` would never produce this), STOP — the test is mis-targeting. Inspect actual `start` value and adjust the seam fixture so the test is exercising the clamp.

- [ ] **Step 4.3: Apply the clamp to `transitionsComposition.ts`**

Open `tools/compositor/src/transitionsComposition.ts`. Find lines 32–34 (the `tlCalls` map). Change the second tween's third argument from `(b.startSec + args.transition.duration / 2).toFixed(3)` to a clamped form.

Replace:
```typescript
  const tlCalls = boundaries
    .map((b) => `      tl.fromTo(maskEl, { autoAlpha: 0 }, { autoAlpha: 1, duration: ${args.transition.duration / 2}, ease: "${args.transition.easing}" }, ${b.startSec.toFixed(3)});\n      tl.to(maskEl,   { autoAlpha: 0, duration: ${args.transition.duration / 2}, ease: "${args.transition.easing}" }, ${(b.startSec + args.transition.duration / 2).toFixed(3)});`)
    .join("\n");
```

With:
```typescript
  const totalSecNum = Math.round(args.totalDurationMs) / 1000;
  const tlCalls = boundaries
    .map((b) => {
      const halfStart = b.startSec;
      // Defensive clamp: a degenerate seam ending at totalSec would push the
      // second tween past timeline duration. planSeams should not produce
      // this today, but two characters of insurance.
      const secondStart = Math.min(b.startSec + args.transition.duration / 2, totalSecNum - args.transition.duration);
      return `      tl.fromTo(maskEl, { autoAlpha: 0 }, { autoAlpha: 1, duration: ${args.transition.duration / 2}, ease: "${args.transition.easing}" }, ${halfStart.toFixed(3)});\n      tl.to(maskEl,   { autoAlpha: 0, duration: ${args.transition.duration / 2}, ease: "${args.transition.easing}" }, ${secondStart.toFixed(3)});`;
    })
    .join("\n");
```

- [ ] **Step 4.4: Run the test suite to confirm pass**

Run:
```bash
npx vitest run test/transitionsComposition.test.ts 2>&1 | tail -10
```
Expected: all transition tests pass including the new clamp test.

Run the full vitest:
```bash
npm test 2>&1 | tail -5
```
Expected: 76/76 pass (1 new test added).

- [ ] **Step 4.5: Harden `preflight.sh` regex**

Open `tools/scripts/lib/preflight.sh`. Replace the critical-failure block (current lines 23–27):

```bash
  if echo "$out" | grep -E "^\s*✗\s+(Node\.js|FFmpeg|FFprobe|Chrome)\b" >/dev/null; then
    echo "[preflight] Critical doctor check failed:"
    echo "$out" | grep -E "^\s*✗\s+(Node\.js|FFmpeg|FFprobe|Chrome)\b"
    return 1
  fi
```

With (label-word OR-fallback so future ANSI-coloured output still matches):

```bash
  # Match either the literal ✗ marker OR a line that mentions the critical label
  # words AND is not an OK line. Belt-and-suspenders: a future HF version that
  # wraps ✗ in ANSI colour codes will still trip the second branch.
  local crit_re_glyph='^\s*✗\s+(Node\.js|FFmpeg|FFprobe|Chrome)\b'
  local crit_re_words='(Node\.js|FFmpeg|FFprobe|Chrome).*(missing|not found|FAIL|failed)'
  if echo "$out" | grep -E "$crit_re_glyph" >/dev/null \
     || echo "$out" | grep -E "$crit_re_words" >/dev/null; then
    echo "[preflight] Critical doctor check failed:"
    echo "$out" | grep -E "$crit_re_glyph|$crit_re_words"
    return 1
  fi
```

Apply the same pattern to the Docker block (lines 30–35):

Replace:
```bash
    if echo "$out" | grep -E "^\s*✗\s+Docker(\s+running)?\b" >/dev/null; then
      echo "[preflight] Docker check failed (HF_RENDER_MODE=docker default):"
      echo "$out" | grep -E "^\s*✗\s+Docker(\s+running)?\b"
      echo "[preflight] To bypass: rerun with HF_RENDER_MODE=local"
      return 1
    fi
```

With:
```bash
    local docker_re_glyph='^\s*✗\s+Docker(\s+running)?\b'
    local docker_re_words='Docker.*(missing|not found|not running|FAIL|failed)'
    if echo "$out" | grep -E "$docker_re_glyph" >/dev/null \
       || echo "$out" | grep -E "$docker_re_words" >/dev/null; then
      echo "[preflight] Docker check failed (HF_RENDER_MODE=docker default):"
      echo "$out" | grep -E "$docker_re_glyph|$docker_re_words"
      echo "[preflight] To bypass: rerun with HF_RENDER_MODE=local"
      return 1
    fi
```

- [ ] **Step 4.6: Add destructive-rerun comment to `render-final.sh`**

Open `tools/scripts/render-final.sh`. Find line 41 (`rm -f "$FINAL"`). Insert a comment immediately above it:

Replace:
```bash
rm -f "$FINAL"
```

With:
```bash
# Destructive on rerun: the previous final.mp4 is removed before render starts.
# If hyperframes render fails mid-flight, the previous good output is gone.
rm -f "$FINAL"
```

- [ ] **Step 4.7: Re-run smoke fixture (HF_RENDER_MODE=local on this dev host) to verify preflight still passes**

Run:
```bash
cd .. && cd .. && HF_RENDER_MODE=local bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test 2>&1 | grep -E "preflight|Compose ready" | head -5
```
Expected: `[preflight] hyperframes doctor OK (mode=local)` and `Compose ready:`.

- [ ] **Step 4.8: Re-run full vitest one more time**

Run:
```bash
cd tools/compositor && npm test 2>&1 | tail -5
```
Expected: 76/76 (or whatever post-Task-1 count is + 1 new clamp test).

- [ ] **Step 4.9: Commit**

Run:
```bash
cd ../.. && git add tools/compositor/src/transitionsComposition.ts tools/compositor/test/transitionsComposition.test.ts tools/scripts/lib/preflight.sh tools/scripts/render-final.sh
git commit -m "$(cat <<'EOF'
fix: defensive guards (transitions clamp, preflight regex, render-final note)

- transitionsComposition: clamp the second tl.to start to
  totalSec - duration so a degenerate seam ending at totalSec cannot
  produce a tween past timeline duration. Adds a unit test.
- preflight.sh: regex now matches either the literal ✗ glyph or a
  line containing the critical label words + a failure verb, so a
  future HF version that wraps ✗ in ANSI colour codes still trips
  preflight on real failures.
- render-final.sh: one-line note above rm -f $FINAL flagging the
  destructive-on-rerun behaviour.

Closes 6a-aftermath follow-ups #8, #10, #11.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: cosmetic cleanups (closes #4, #7, #9)

**Files:**
- Modify: `tools/compositor/src/composer.ts`
- Modify: `tools/compositor/src/episodeMeta.ts`
- Modify: `tools/scripts/sync-hf-skills.sh`

**What and why:** Three readability cleanups bundled under one cosmetic theme. No behavioral change; vitest must remain green.

- [ ] **Step 5.1: Replace the six `TRACK_*` constants with `TRACKS` const-as-enum**

Open `tools/compositor/src/composer.ts`. Find lines 19–26:

```typescript
const ROOT_WIDTH = 1440;
const ROOT_HEIGHT = 2560;
const TRACK_VIDEO = 0;
const TRACK_CAPTIONS = 1;
const TRACK_AUDIO = 2;
const TRACK_SEAM_BASE = 3;
const TRACK_TRANSITIONS = 4;
const TRACK_MUSIC = 5;
```

Replace with:

```typescript
const ROOT_WIDTH = 1440;
const ROOT_HEIGHT = 2560;
// Track-index ladder. HF treats track-index purely as an identifier
// (it does NOT affect z-order); these are coordination IDs only.
// Adding a new track? Pick the next unused integer and update this object.
const TRACKS = {
  VIDEO: 0,
  CAPTIONS: 1,
  AUDIO: 2,
  SEAM_BASE: 3,
  TRANSITIONS: 4,
  MUSIC: 5,
} as const;
```

Now update every reference in the same file. Find all occurrences (composer.ts is the only file using these per the earlier grep — Found 1 file):

- `${TRACK_VIDEO}` → `${TRACKS.VIDEO}`
- `${TRACK_CAPTIONS}` → `${TRACKS.CAPTIONS}`
- `${TRACK_AUDIO}` → `${TRACKS.AUDIO}`
- `${TRACK_SEAM_BASE}` → `${TRACKS.SEAM_BASE}`
- `${TRACK_TRANSITIONS}` → `${TRACKS.TRANSITIONS}`
- `${TRACK_MUSIC}` → `${TRACKS.MUSIC}`

These are all interpolations inside `data-track-index="..."` template literals (lines 52, 77, 86, 93, 103, 111). Mechanical replace.

- [ ] **Step 5.2: Type-check + run vitest after the rename**

Run:
```bash
cd tools/compositor && npx tsc --noEmit 2>&1 | tail -10
```
Expected: no errors.

Run:
```bash
npm test 2>&1 | tail -5
```
Expected: same count as Task 4 (76/76 if Task 4 added one). The composer test (`test/composer.test.ts`) renders index.html and checks for `data-track-index="..."` literals — those values do not change, so tests pass unchanged.

- [ ] **Step 5.3: Add the integration-doc comment to `episodeMeta.ts`**

Open `tools/compositor/src/episodeMeta.ts`. Find lines 10–18:

```typescript
const HF_PROJECT_CONFIG = {
  $schema: "https://hyperframes.heygen.com/schema/hyperframes.json",
  registry: "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
  paths: {
    blocks: "compositions",
    components: "compositions/components",
    assets: "assets",
  },
} as const;
```

Replace with (single comment block above the const):

```typescript
// $schema and registry URLs are pinned to the contract surface of the
// hyperframes CLI version declared in tools/compositor/package.json.
// They MUST be kept in lockstep with that pin; see
// docs/hyperframes-integration.md for the contract registry.
const HF_PROJECT_CONFIG = {
  $schema: "https://hyperframes.heygen.com/schema/hyperframes.json",
  registry: "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
  paths: {
    blocks: "compositions",
    components: "compositions/components",
    assets: "assets",
  },
} as const;
```

- [ ] **Step 5.4: Drop the dead `[ -n "$TARBALL_URL" ]` branch in `sync-hf-skills.sh`**

Open `tools/scripts/sync-hf-skills.sh`. Find lines 39–40:

```bash
TARBALL_URL="$(npm view "hyperframes@$VERSION" dist.tarball --registry https://registry.npmjs.org)"
[ -n "$TARBALL_URL" ] || { echo "ERROR: hyperframes@$VERSION has no tarball on npm"; exit 1; }
```

Replace with:

```bash
# `set -e` aborts at this `npm view` line if the version does not exist on npm,
# so the previous `[ -n "$TARBALL_URL" ]` guard was unreachable. The npm-native
# 404 already preserves the safety property (no silent fallback to `latest`).
TARBALL_URL="$(npm view "hyperframes@$VERSION" dist.tarball --registry https://registry.npmjs.org)"
```

- [ ] **Step 5.5: Smoke-run sync-hf-skills.sh against the current pin**

Run:
```bash
cd ../.. && bash tools/scripts/sync-hf-skills.sh 2>&1 | tail -10
```
Expected: `Done. Vendored at .../tools/hyperframes-skills (version 0.4.31).` Exit 0. (The script re-syncs the same vendored content; idempotent.)

Run:
```bash
git diff --stat tools/hyperframes-skills/
```
Expected: empty (no actual content changes, just verified the script still works).

- [ ] **Step 5.6: Re-run smoke fixture compose**

Run:
```bash
HF_RENDER_MODE=local bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test 2>&1 | tail -10
```
Expected: clean compose; `lint`/`validate`/`inspect` all pass; `Compose ready:`.

- [ ] **Step 5.7: Commit**

Run:
```bash
git add tools/compositor/src/composer.ts tools/compositor/src/episodeMeta.ts tools/scripts/sync-hf-skills.sh
git commit -m "$(cat <<'EOF'
refactor: cosmetic cleanups (TRACKS const, episodeMeta comment, sync-hf-skills dead branch)

- composer: collapse TRACK_VIDEO/CAPTIONS/AUDIO/SEAM_BASE/TRANSITIONS/MUSIC
  into one `const TRACKS = { … } as const` object so adding a track is
  one diff, not six. Mechanical rename — no behavioural change.
- episodeMeta: comment block above HF_PROJECT_CONFIG points to
  docs/hyperframes-integration.md as the source of truth for the
  pinned $schema and registry URLs.
- sync-hf-skills.sh: remove unreachable `[ -n "$TARBALL_URL" ]` guard;
  set -e already aborts at the upstream `npm view` line if the version
  does not exist, and the npm 404 is loud enough.

Closes 6a-aftermath follow-ups #4, #7, #9.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: defer-with-reason for P3 + Docker verification ops-doc (closes #2, #5, #6)

**Files:**
- Modify: `tools/compositor/src/designMd.ts`
- Modify: `tools/compositor/src/captionsComposition.ts`
- Create: `docs/operations/docker-render-verification.md`

**What and why:** Three follow-ups too speculative or off-host to fix today; each gets a tracked reason in the right place so it is not silently dropped.

- [ ] **Step 6.1: Add JSDoc to `resolveToken` flagging numeric coercion**

Open `tools/compositor/src/designMd.ts`. Find the `resolveToken` function (lines 51–67). Insert a JSDoc block immediately above its `export function resolveToken(...)` line:

```typescript
/**
 * Resolve a dotted token path to its leaf value as a string.
 *
 * NOTE on numeric coercion: this function returns `String(cursor)` for any
 * non-object leaf, which means numeric tokens (e.g. `transition.duration: 0.4`)
 * become the string `"0.4"`. Today only string-typed CSS tokens route through
 * this function; numeric tokens are read via the typed loader
 * `readTransitionConfig` and never see this code path.
 *
 * If a future caller routes a numeric token through `resolveToken`, that caller
 * MUST coerce back to number. Consider adding a `resolveTokenNumber` overload
 * before introducing such a caller. (6a-aftermath follow-up #5.)
 */
export function resolveToken(tree: TokenTree, dottedPath: string): string {
```

- [ ] **Step 6.2: Add inline TODO to captions self-lint**

Open `tools/compositor/src/captionsComposition.ts`. Find the self-lint sweep (lines 105–113):

```typescript
      // Self-lint: every group must have an entry tween and a hard-kill set.
      var children = tl.getChildren(false, true, true);
      GROUPS.forEach(function (g) {
```

Replace with:

```typescript
      // Self-lint: every group must have an entry tween and a hard-kill set.
      // Cost: O(N²) — children.some(...) inside GROUPS.forEach. Fine up to
      // ~200 caption groups (a long episode). If this profiles hot at runtime,
      // hoist behind 'if (!window.__captionsLintRan)' and run once per page
      // load. (6a-aftermath follow-up #6.)
      var children = tl.getChildren(false, true, true);
      GROUPS.forEach(function (g) {
```

- [ ] **Step 6.3: Create `docs/operations/docker-render-verification.md`**

Create the parent dir and write the file:

```bash
mkdir -p docs/operations
```

Write `docs/operations/docker-render-verification.md`:

```markdown
# Docker render-mode verification

Status: **deferred-with-reason** (2026-04-28). The current dev host has no
Docker installed, so the F-phase scripts default to `HF_RENDER_MODE=docker`
but are run with `HF_RENDER_MODE=local`. Before declaring `--docker` a hard
production requirement, an operator on a Docker-capable host must run
through this verification.

This document tracks the procedure so the verification is not silently
skipped when the next operator picks it up.

## Context

`hyperframes render --docker` is the only bit-deterministic mode HyperFrames
ships (per `docs/notes/hyperframes-cli.md`). It also gives a hard cgroup
memory cap, which matters at 1440×2560 where local mode wedged the dev host
during Phase 6a. F-phase scripts therefore default to docker mode, with
`HF_RENDER_MODE=local` as an explicit opt-out.

The architectural assumption is "docker mode works as advertised". This
document is the verification of that assumption.

## Prerequisites

- Linux, macOS, or Windows host with Docker Desktop or Docker Engine
  installed and the daemon running.
- Docker version: `docker version` returns a server version (any 24+ is fine).
- `hyperframes doctor` reports OK on Docker and Docker running:
  ```
  hyperframes doctor
  ```
  Expected lines (no leading `✗`):
  - `✓ Docker`
  - `✓ Docker running`

## Procedure

1. Clone or pull the repo at the latest `main`.
2. `cd tools/compositor && npm install` (installs the pinned hyperframes
   binary + `@hyperframes/producer`).
3. From repo root, run the smoke fixture in docker mode:
   ```bash
   HF_RENDER_MODE=docker bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test
   HF_RENDER_MODE=docker bash tools/scripts/run-stage2-preview.sh 2026-04-28-phase-6a-smoke-test
   ```
4. Capture the SHA-256 of the produced `preview.mp4`:
   ```bash
   sha256sum episodes/2026-04-28-phase-6a-smoke-test/stage-2-composite/preview.mp4
   ```
5. Repeat steps 3–4 once more (clean re-render, no cache reuse if avoidable).
6. Compare the two SHA-256 values.

## Success criteria

- Both runs complete with exit 0 and `Compose ready:` / `Preview ready:`.
- Both `preview.mp4` SHA-256s match.
- Memory consumption (observe via `docker stats` or host Activity Monitor)
  stays within the cgroup cap declared by HF defaults; the host does not
  swap or wedge.
- `vitest 75/75` (or current count) on the verifying host.

## On success

Append a verification entry to `standards/retro-changelog.md` documenting:
- Host OS + Docker version,
- The two matching SHAs,
- Date of verification.

After that, `HF_RENDER_MODE=docker` may be promoted from "default with local
opt-out" to "hard requirement for production", and `HF_RENDER_MODE=local` can
be marked development-only.

## On failure

Open an issue or retro entry capturing:
- The first failing step,
- `hyperframes doctor` output on the verifying host,
- Any `docker stats` excerpt at the failure point.

The fallback is to keep the current "docker default with local opt-out"
posture and re-evaluate at the next HF version bump.

## Why this is not in CI today

CI hosts on the project's current setup do not have Docker available
either. This is operator-driven verification on a host with Docker
installed.
```

- [ ] **Step 6.4: Type-check + vitest after the JSDoc / inline-comment edits**

Run:
```bash
cd tools/compositor && npx tsc --noEmit 2>&1 | tail -10
```
Expected: no errors.

Run:
```bash
npm test 2>&1 | tail -5
```
Expected: same count as Task 5 (76/76).

- [ ] **Step 6.5: Re-run the smoke fixture**

Run:
```bash
cd ../.. && HF_RENDER_MODE=local bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test 2>&1 | tail -10
```
Expected: clean compose.

- [ ] **Step 6.6: Commit**

Run:
```bash
git add tools/compositor/src/designMd.ts tools/compositor/src/captionsComposition.ts docs/operations/docker-render-verification.md
git commit -m "$(cat <<'EOF'
docs: defer-with-reason for P3 follow-ups + Docker verification TODO

- designMd.resolveToken: JSDoc note that numeric leaves are coerced
  to strings via String(cursor). Today only string-typed CSS tokens
  route through this; numeric tokens go through readTransitionConfig.
  Future numeric callers MUST coerce back. Tracked at the definition.
- captionsComposition: inline note on the post-build self-lint sweep
  flagging O(N²) cost and the ~200-group threshold past which it
  should be hoisted behind a 'ran once' guard.
- docs/operations/docker-render-verification.md: new ops-doc tracking
  the procedure to verify HF_RENDER_MODE=docker on a host with Docker.
  The current dev host has none; the verification is deferred-with-
  reason rather than silently skipped.

Closes 6a-aftermath follow-ups #2, #5, #6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: retro-changelog close entry + PR

**Files:**
- Modify: `standards/retro-changelog.md`

- [ ] **Step 7.1: Append the close entry**

Open `standards/retro-changelog.md`. Append at the end (after the last existing line):

```markdown

## 2026-04-28 — Phase 6a-aftermath follow-ups close

All 12 open follow-ups from the 2026-04-28 Phase 6a-aftermath close are resolved on branch `phase-6a-followups`.

Resolved:
- (#1) `@hyperframes/producer@0.4.31` exact-pinned in `tools/hyperframes-skills/package.json` (its actual consumer); `sync-hf-skills.sh` rewritten to preserve our local files; `check-updates.sh` reads the new pin and flags both pinned-vs-latest drift and pin-vs-CLI lockstep drift.
- (#3) HF 0.4.31 contrast-audit OOB bug patched via `patch-package` (`tools/compositor/patches/hyperframes+0.4.31.patch`, applied via `postinstall`). Smoke fixture validate goes from 5 contrast WARN to 0. Upstream issue draft at `docs/hyperframes-patches/0.4.31-contrast-audit-oob.md`.
- (#4) `sync-hf-skills.sh` dead `[ -n "$TARBALL_URL" ]` branch removed; `set -e` already covered the safety property.
- (#5) `resolveToken` numeric-coercion JSDoc added; calls out that numeric tokens go through `readTransitionConfig`, not this path.
- (#6) Captions self-lint O(N²) inline-flagged with the ~200-group threshold past which it should be hoisted.
- (#7) Track index ladder collapsed into `const TRACKS = { … } as const`.
- (#8) `transitionsComposition` second-tween start clamped via `Math.min(b.startSec + duration/2, totalSec - duration)` with a unit test.
- (#9) `episodeMeta` magic-URL comment points at `docs/hyperframes-integration.md`.
- (#10) `preflight.sh` regex hardened with a label-word fallback so ANSI-coloured `✗` lines still trip critical-failure detection.
- (#11) `render-final.sh` `rm -f $FINAL` annotated as destructive-on-rerun.
- (#12) FROZEN pilot `hf-project/` re-narrowed in `.gitignore` to its exact path; future episodes that regenerate `hf-project/` still surface as untracked.

Deferred-with-reason:
- (#2) Docker render-mode verification: requires a host with Docker installed; tracked at `docs/operations/docker-render-verification.md`. Operator-driven, not blocking Phase 6b.

Smoke fixture verified end-to-end: lint 0/0, validate 0/0, inspect ok=true, vitest 76/76.
```

- [ ] **Step 7.2: Commit the retro entry**

Run:
```bash
git add standards/retro-changelog.md
git commit -m "$(cat <<'EOF'
retro(6a-aftermath): close follow-ups

Append the close entry summarising all 12 resolved/deferred items
on phase-6a-followups branch. Pairs with the per-fix commits
de06181..HEAD~1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 7.3: Final smoke + test sweep**

Run:
```bash
cd tools/compositor && npm test 2>&1 | tail -5
```
Expected: 76/76 (or whatever the post-Task-4 count is).

Run:
```bash
cd ../.. && HF_RENDER_MODE=local bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test 2>&1 | tail -20
```
Expected: lint 0/0, validate 0/0 (no WCAG WARN), inspect ok=true, no animation-map WARN, no `var()` guard regressions, `Compose ready:` final line.

- [ ] **Step 7.4: Push branch and open PR**

Run:
```bash
git push -u origin phase-6a-followups
```

Run:
```bash
gh pr create --title "Phase 6a-aftermath: close all 12 open follow-ups" --body "$(cat <<'EOF'
## Summary
- Closes 11 of the 12 open follow-ups from the 2026-04-28 Phase 6a-aftermath retrospective; the remaining one (Docker render-mode verification) is deferred-with-reason in `docs/operations/docker-render-verification.md` because the dev host has no Docker.
- Six focused commits, each self-contained: `@hyperframes/producer` pin, FROZEN-pilot gitignore, smoke-fixture WCAG fix, defensive guards, cosmetic cleanups, P3 doc-only.

## Test plan
- [ ] `cd tools/compositor && npm test` reports 76/76 pass.
- [ ] `HF_RENDER_MODE=local bash tools/scripts/run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test` produces lint 0/0, validate 0/0 (was 5 WCAG WARN), inspect ok=true, no animation-map WARN.
- [ ] `git status` is clean (FROZEN pilot `hf-project/` no longer untracked).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Report back the PR URL.

---

## Self-review checklist (run before declaring complete)

- [ ] Every follow-up #1–#12 has a closing commit or a tracked-reason file.
- [ ] No `TBD` / `TODO` / placeholder text in committed code or docs.
- [ ] `vitest` count: started at 75, +1 from the transitions clamp test in Task 4 → 76 final.
- [ ] `git log --oneline phase-6a-followups ^main` shows 7 commits in this order:
  1. `de06181 docs(spec): phase-6a-aftermath follow-ups design` (pre-existing)
  2. `fix(compositor): pin @hyperframes/producer 0.4.31 for animation-map`
  3. `chore(gitignore): re-narrow FROZEN pilot hf-project to exact path`
  4. `fix(smoke-fixture): #smoke-plate WCAG-compliant colours`
  5. `fix: defensive guards (transitions clamp, preflight regex, render-final note)`
  6. `refactor: cosmetic cleanups (TRACKS const, episodeMeta comment, sync-hf-skills dead branch)`
  7. `docs: defer-with-reason for P3 follow-ups + Docker verification TODO`
  8. `retro(6a-aftermath): close follow-ups`
- [ ] PR open against `main`.
