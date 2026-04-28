# Phase 6a-aftermath follow-ups — design

**Date:** 2026-04-28
**Branch:** `phase-6a-followups`
**Source:** 12 follow-ups appended to `standards/retro-changelog.md` under "2026-04-28 — Phase 6a-aftermath close → Open follow-ups".

## Goal

Close every open follow-up from the Phase 6a-aftermath retrospective before starting Phase 6b. After merge, `run-stage2-compose.sh` must produce zero WARN noise on the smoke fixture, `git status` must be clean on the FROZEN pilot, and every deferred item must have a tracked reason in code or docs (no silent kicks-down-the-road).

## Non-goals

- No Phase 6b work (agentic graphics planner). The bespoke-seam round-trip plumbing on `Seam.graphic` stays as `TODO(6b)`.
- No new architectural decisions. This is cleanup of known papercuts surfaced by the Phase 6a-aftermath review.
- No upgrades to `hyperframes` or `@hyperframes/producer` beyond the existing pin (`0.4.31`).

## Approach

Six focused commits on a single feature branch (`phase-6a-followups`) → single PR against `main`. Each commit is self-contained and keeps `lint 0/0`, `validate 0/0`, `inspect ok=true`, and `75/75 vitest` green on the smoke fixture (`episodes/2026-04-28-phase-6a-smoke-test`).

### Commit 1 — `fix(hf-skills): provide @hyperframes/producer to vendored skill scripts`

**Closes follow-up #1.**

The vendored skill scripts at `tools/hyperframes-skills/hyperframes/scripts/animation-map.mjs` and `contrast-report.mjs` import `@hyperframes/producer`. This is a separate npm package — HF internal, ships independently from the `hyperframes` CLI tarball. In the upstream HF monorepo it is a workspace sibling of the skill scripts; our vendored copy needs the same dependency to be resolvable.

**Architectural placement:** the dep belongs where its consumer lives. Only the vendored skill scripts import `@hyperframes/producer`; our compositor source code does not. Therefore `tools/hyperframes-skills/` becomes a self-contained vendored subproject with its own `package.json` and `node_modules`, mirroring how the upstream monorepo provides the dep to the same scripts.

ESM bare-specifier resolution walks from the importing file's directory upward looking for `node_modules/`. The skill script's parent walk now reaches `tools/hyperframes-skills/node_modules/@hyperframes/producer` — no flags, no `NODE_PATH`, no symlinks, no wrapper.

Changes:
- New file: `tools/hyperframes-skills/package.json` — single dep `"@hyperframes/producer": "0.4.31"` (exact-pin, lockstep with the CLI pin).
- New file: `tools/hyperframes-skills/.gitignore` — ignores `node_modules/`.
- `npm install` in `tools/hyperframes-skills/` produces `package-lock.json` (tracked) and `node_modules/` (ignored).
- `tools/scripts/sync-hf-skills.sh`: replace `rm -rf "$SKILLS_DIR"` (which would nuke our `package.json`/lockfile/node_modules on every sync) with targeted removal of the three upstream-managed subtrees: `gsap/`, `hyperframes/`, `hyperframes-cli/`. The local `package.json`, `package-lock.json`, `node_modules/`, and `VERSION` (rewritten by the script itself) survive.
- `tools/scripts/check-updates.sh`: read producer pin from `tools/hyperframes-skills/package.json` (its actual home), not from `tools/compositor/package.json`. Continue checking pin-vs-latest drift and pin-vs-CLI lockstep.
- Re-run `run-stage2-compose.sh` against smoke fixture; verify the previous `WARN: animation-map errored; continuing` is gone, `.hyperframes/anim-map/` populates with output files, and exit is clean.

Implementation notes for engineers picking this up:
- Do NOT add `@hyperframes/producer` to `tools/compositor/package.json`. The compositor never imports it; placing it there would couple a 300-MB-with-Chromium dep to a project that does not consume it.
- Repo onboarding now requires two `npm install` invocations: `cd tools/compositor && npm install` and `cd tools/hyperframes-skills && npm install`. Document this in `AGENTS.md` and any README that lists setup steps.

Out of scope: investigating whether HF intends to ship `dist/skills/` such that `@hyperframes/producer` resolves automatically. We treat this as "skills assume it; we provide it where they look for it."

### Commit 2 — `chore(gitignore): re-narrow FROZEN pilot hf-project to exact path`

**Closes follow-up #12.**

Phase F dropped the wildcard `episodes/*/stage-2-composite/hf-project/` rule. The FROZEN pilot retains its pre-6a `hf-project/` directory (per E7/E8 the pilot is non-canonical and must not be touched), so it now shows as untracked in `git status`.

Changes:
- `.gitignore`: replace any leftover wildcard (or absence) with an exact path: `episodes/2026-04-27-desktop-software-licensing-it-turns-out/stage-2-composite/hf-project/`. Add a comment immediately above: `# FROZEN pilot — pre-6a archive, never edited; ignored to keep git status clean. See AGENTS.md / standards/pipeline-contracts.md.`
- Verify `git status` is clean after the change.

This narrows the rule strictly to the one historical path, so future episodes that accidentally regenerate `hf-project/` will surface (intentional regression detector).

### Commit 3 — `fix(hf-patch): patch HF 0.4.31 contrast-audit OOB bug`

**Closes follow-up #3.**

Upon investigation, the 5 WCAG WARN against `#smoke-plate` are not a fixture-content issue. `hyperframes validate --json` returns `ratio: null, fg: rgb(NaN,NaN,NaN), bg: rgb(undefined,undefined,undefined)` regardless of plate colours (verified by trying class-rule literals, inline styles, GSAP tween removal, and backdrop-filter removal — all five attempts produced identical NaN/undefined output).

Root cause is in HF 0.4.31's `src/commands/validate.ts` and inlined `src/commands/contrast-audit.browser.js`:

1. `validate.ts` sets `page.setViewport({width:1920, height:1080})` unconditionally.
2. The screenshot is taken at viewport size — 1920×1080.
3. For our 1440×2560 vertical composition, text elements below y=1080 have `rect.y > h` (canvas height).
4. `contrast-audit.browser.js` clamps `y0 = Math.max(0, Math.floor(rect.y) - 4)` only against zero, not against `h-1`. The ring-sampling loop then reads `px[(y0 * w + x) * 4]` where `idx` exceeds the screenshot's `Uint8ClampedArray` length → returns `undefined`.
5. `median(rr)` over `undefined` values returns `undefined`. `compR = Math.round(fg[0]*fg[3] + undefined*0)` → `NaN`. Output has `fg: rgb(NaN,...)` and `bg: rgb(undefined,...)`.

Fix: patch `node_modules/hyperframes/dist/cli.js` (the inlined audit script) via `patch-package`. Two changes:

- Skip elements that fall fully outside the screenshot canvas (`continue` when `rect.x + rect.width <= 0 || rect.x >= w || rect.y + rect.height <= 0 || rect.y >= h`).
- Double-clamp the ring-sampling bounds to keep indices inside `[0, w-1]` × `[0, h-1]` for partial overlaps.

Changes:
- `tools/compositor/package.json` `devDependencies`: add `"patch-package": "^8.0.1"`.
- `tools/compositor/package.json` `scripts.postinstall`: `"patch-package"` (auto-applies on every `npm install`).
- New file: `tools/compositor/patches/hyperframes+0.4.31.patch` (generated via `npx patch-package hyperframes`).
- `docs/hyperframes-upgrade.md`: new "Local patches against `hyperframes`" section listing this patch and the procedure to evaluate it on every version bump.
- New file: `docs/hyperframes-patches/0.4.31-contrast-audit-oob.md` — upstream issue draft (reproduction, root cause, suggested minimal + proper fixes). To be filed against the HF repo when publicly tracked.

Acceptance: `hyperframes validate --json` against the smoke fixture returns `contrastFailures: 0`. Compose script tail shows `0 errors, 0 warnings` and no contrast-warning section. The patch reapplies on a clean `rm -rf node_modules/hyperframes && npm install`.

The smoke fixture's `seam-4.html` is unchanged; the bug was upstream all along.

### Commit 4 — `fix: defensive guards (transitions clamp, preflight regex, render-final note)`

**Closes follow-ups #8, #10, #11.**

Three defensive papercuts grouped because they are all "guard against future-edge that today's code doesn't trigger". Bundling reduces commit count without mixing unrelated themes.

Changes:
- **transitions clamp** (`tools/compositor/src/compositions/transitionsComposition.ts` or equivalent): replace the second `tl.to` end-time with `Math.min(b.startSec + duration, totalSec - duration)`. `planSeams` shouldn't produce this today, but the clamp is two characters of insurance.
- **preflight regex** (`tools/scripts/lib/preflight.sh`): the existing regex relies on the literal `✗` glyph emitted by `hyperframes doctor`. Add an OR-fallback: also match the label words `Node\.js|FFmpeg|FFprobe|Chrome` in any line that does not contain `OK`. If a future HF version wraps the marker in ANSI colour codes, we still catch real failures.
- **render-final destructive note** (`tools/scripts/render-final.sh:39`): single-line comment immediately above `rm -f "$FINAL"`: `# destructive on rerun: previous final.mp4 is removed before render starts`.

### Commit 5 — `refactor: cosmetic cleanups (TRACKS const, episodeMeta comment, sync-hf-skills dead branch)`

**Closes follow-ups #4, #7, #9.**

- **TRACKS const-as-enum** (#7): replace the six flat constants (`TRACK_VIDEO=0`, `TRACK_CAPTIONS=1`, `TRACK_AUDIO=2`, `TRACK_SEAM_BASE=3`, `TRACK_TRANSITIONS=4`, `TRACK_MUSIC=5`) with `export const TRACKS = { VIDEO:0, CAPTIONS:1, AUDIO:2, SEAM_BASE:3, TRANSITIONS:4, MUSIC:5 } as const`. Update every importer. Mechanical rename — no behavioral change. Vitest must stay green.
- **episodeMeta magic URLs comment** (#9 — `tools/compositor/src/episodeMeta.ts` top of file): comment block above the hard-coded `$schema` and `registry` URLs pointing to `docs/hyperframes-integration.md` as the source of truth: `// $schema and registry URLs are pinned to hyperframes 0.4.31's contract surface. // See docs/hyperframes-integration.md for the registry of pinned constants.`
- **sync-hf-skills dead 404 branch** (#4 — `tools/scripts/sync-hf-skills.sh`): remove the `[ -n "$TARBALL_URL" ]` guard that never executes (since `set -e` aborts at the upstream `npm view` line). The npm-native 404 already preserves the safety property (no silent fallback to `latest`). Two lines of dead code go away.

### Commit 6 — `docs: defer-with-reason for P3 + Docker verification TODO`

**Closes follow-ups #2, #5, #6.**

- **`resolveToken` JSDoc note** (#5) (`tools/compositor/src/...resolveToken.ts`): add a JSDoc block explaining: today only string-typed CSS tokens route through `resolveToken`; numeric tokens (e.g. `transition.duration: 0.4`) reach the runtime via `readTransitionConfig` typed loaders. If a future numeric token routes through `resolveToken`, callers MUST coerce back from the `String(cursor)` output. Sentinel for follow-up at the call-site, not at the definition.
- **Captions self-lint inline TODO** (#6) (`tools/compositor/src/...captionsComposition.ts` near the post-build sweep): comment: `// O(N²) sweep — fine up to ~200 caption groups. If a long episode profiles hot, hoist behind 'if (!window.__captionsLintRan)' guard.`
- **`docs/operations/docker-render-verification.md`** (#2 — new file): short ops-doc describing the procedure for validating `HF_RENDER_MODE=docker` on a host that has Docker: required Docker version, expected behaviour of `hyperframes doctor`, the smoke-fixture command to run, and the success criteria (deterministic SHA across two runs, memory cap holds under cgroup). Marks the verification as "tracked, not blocking" until the first operator on a Docker host runs through it.

### After Commit 6 — retro-changelog entry

Append to `standards/retro-changelog.md`:

```markdown
## 2026-04-28 — Phase 6a-aftermath follow-ups close

All 12 open follow-ups from the 2026-04-28 Phase 6a-aftermath close are resolved. See branch `phase-6a-followups` (PR #N).

Resolved:
- (#1) `@hyperframes/producer@0.4.31` exact-pinned in `tools/hyperframes-skills/package.json` (consumer-local); `sync-hf-skills.sh` preserves local files on resync; `check-updates.sh` reads the new pin and warns on cross-pin lockstep drift.
- (#3) HF 0.4.31 contrast-audit OOB bug patched via `patch-package` (`tools/compositor/patches/hyperframes+0.4.31.patch`); applies on every `npm install`. Smoke fixture validate 0/0. Upstream issue draft at `docs/hyperframes-patches/0.4.31-contrast-audit-oob.md`.
- (#4) `sync-hf-skills.sh` dead 404 branch removed.
- (#5) `resolveToken` numeric-coercion JSDoc added.
- (#6) Captions self-lint O(N²) inline-flagged with N≈200 threshold.
- (#7) Track index ladder collapsed into `const TRACKS = { … } as const`.
- (#8) `transitionsComposition` boundary clamped via `Math.min`.
- (#9) `episodeMeta` magic-URL comment added.
- (#10) `preflight.sh` regex hardened with label-word fallback.
- (#11) `render-final.sh` `rm -f` destructive note added.
- (#12) FROZEN pilot `hf-project/` re-narrowed in `.gitignore`.

Deferred-with-reason:
- (#2) Docker render-mode verification: requires a host with Docker installed; tracked at `docs/operations/docker-render-verification.md`. Operator-driven, not blocking Phase 6b.

Smoke fixture verified end-to-end after C6: lint 0/0, validate 0/0, inspect ok=true, 75/75 vitest.
```

## Verification per commit

Each commit MUST end with:

```bash
cd tools/compositor && npm test
cd ../.. && bash tools/scripts/run-stage2-compose.sh episodes/2026-04-28-phase-6a-smoke-test
```

Acceptance: `vitest 75/75` (or higher if new tests are added — none planned), compose exits clean, `validate` and `inspect` report 0/0, no animation-map WARN after C1, no `var()` guard regressions.

## Risk register

- **C1 — `@hyperframes/producer@0.4.31` may have transitive deps that bloat install size.** Mitigation: `npm view @hyperframes/producer@0.4.31 dependencies` before install; if heavy, surface the size delta in the commit message.
- **C3 — palette adjustment for `#smoke-plate` may cascade into other fixture elements.** Mitigation: scope changes to the plate's local CSS; if cascade is unavoidable, drop back to single-purpose plate-local class.
- **C5 — TRACKS rename touches every importer.** Mitigation: TypeScript compile + vitest is the safety net; do not hand-edit, prefer single rg-replace pass and follow with `tsc --noEmit`.

## Out of scope (explicit non-decisions)

- No update to `hyperframes` or `@hyperframes/producer` beyond `0.4.31`.
- No changes to Stage 1 or `master.mp4` write path.
- No new tests added unless directly required by a fix (none expected).
- No bespoke seam authoring; that lives in Phase 6b.
- No FROZEN-pilot edits.

## Acceptance criteria

1. All 12 follow-ups closed (11 resolved + 1 deferred-with-tracked-doc).
2. Single PR open against `main` with 6 commits + retro-changelog entry.
3. Smoke fixture: `lint 0/0`, `validate 0/0`, `inspect ok=true`, `75/75 vitest` after every commit.
4. `git status` clean.
5. After merge: ready to choose first real episode and run baseline pipeline.
