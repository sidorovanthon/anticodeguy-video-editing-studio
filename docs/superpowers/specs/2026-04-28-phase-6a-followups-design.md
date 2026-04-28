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

### Commit 1 — `fix(compositor): pin @hyperframes/producer 0.4.31 for animation-map`

**Closes follow-up #1.**

`@hyperframes/producer` is a separate npm package (HF internal) that the vendored skill scripts `animation-map.mjs` and `contrast-report.mjs` import. It is not bundled with `hyperframes@0.4.31` and is not declared anywhere on our side, so the scripts fail at module-resolve time and `run-stage2-compose.sh` swallows it as informational WARN.

`0.4.31` of `@hyperframes/producer` exists on npm (published 2026-04-26T23:42:36Z, same minute as `hyperframes@0.4.31` — lockstep release).

Changes:
- `tools/compositor/package.json` `dependencies`: add `"@hyperframes/producer": "0.4.31"` (exact pin, no caret/tilde — same convention as `hyperframes`).
- `npm install` in `tools/compositor/` to refresh `package-lock.json`.
- `tools/scripts/check-updates.sh`: extend the existing hyperframes drift check to also `npm view @hyperframes/producer version` and warn on drift from the installed version.
- Re-run `run-stage2-compose.sh` against smoke fixture; verify the previous animation-map WARN is gone and the script exits cleanly.

Out of scope: investigating whether the upstream HF repo intends `@hyperframes/producer` to be a runtime dep of the skill scripts. We treat this as "the skills assume it; we provide it."

### Commit 2 — `chore(gitignore): re-narrow FROZEN pilot hf-project to exact path`

**Closes follow-up #12.**

Phase F dropped the wildcard `episodes/*/stage-2-composite/hf-project/` rule. The FROZEN pilot retains its pre-6a `hf-project/` directory (per E7/E8 the pilot is non-canonical and must not be touched), so it now shows as untracked in `git status`.

Changes:
- `.gitignore`: replace any leftover wildcard (or absence) with an exact path: `episodes/2026-04-27-desktop-software-licensing-it-turns-out/stage-2-composite/hf-project/`. Add a comment immediately above: `# FROZEN pilot — pre-6a archive, never edited; ignored to keep git status clean. See AGENTS.md / standards/pipeline-contracts.md.`
- Verify `git status` is clean after the change.

This narrows the rule strictly to the one historical path, so future episodes that accidentally regenerate `hf-project/` will surface (intentional regression detector).

### Commit 3 — `fix(smoke-fixture): #smoke-plate WCAG-compliant colours`

**Closes follow-up #3.**

The synthetic "6A WIRING OK" plate in `episodes/2026-04-28-phase-6a-smoke-test/.../seam-4.html` (or wherever `#smoke-plate` is authored) fails WCAG AA 3:1 contrast at 5 sample times during HF `validate`. This is fixture content, not architecture.

Changes:
- Locate the plate's foreground/background colour pair. Compute current contrast ratio. Adjust foreground (likely darken text or pick a higher-luminance text colour) until it passes ≥3:1 against its background (large-text WCAG AA threshold). Keep within `DESIGN.md` palette where possible; if no palette pair works, document the override inline.
- Re-run smoke compose; expect `validate` 0 WARN.
- If the plate uses tokens that themselves are mid-grey on mid-grey, prefer tightening the fixture rather than rewriting palette tokens — the goal is a clean smoke-fixture, not a palette change.

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
- (#1) `@hyperframes/producer@0.4.31` exact-pinned in `tools/compositor/package.json`; `check-updates.sh` extended.
- (#3) `#smoke-plate` repainted; smoke-fixture validate 0/0.
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
