# Phase 6a — HF-native foundation (design)

**Status:** approved design, ready for implementation plan.
**Date:** 2026-04-28
**Decomposition source:** `docs/superpowers/specs/2026-04-28-phase-6-decomposition.md`
**Sequel:** Phase 6b — agentic graphics planner (separate brainstorm after 6a closes).

## Goal

Move the existing Stage 2 pipeline onto HyperFrames' canonical project shape so that Phase 6b can dispatch coding subagents into a clean, HF-native architecture. No agentic planner in this phase; no new graphics. The deliverable is the rewritten compositor, the project-level `DESIGN.md`, the captions migration, the dead-component cleanup, and a synthetic smoke-test bespoke sub-composition that proves the wiring end-to-end.

## Acceptance

On a copy of the pilot (`episodes/2026-04-27-desktop-software-licensing-it-turns-out/` is FROZEN — use a copy or the next episode), running `tools/scripts/run-stage2-compose.sh <slug>` followed by `tools/scripts/run-stage2-preview.sh <slug>` produces `preview.mp4` such that:

1. `master.mp4` plays as the talking-head track.
2. Captions are present and synced to `master/bundle.json` words within ±1 frame.
3. On exactly one synthetic non-`head` seam, a bespoke sub-composition appears with the text "6A WIRING OK" on a frosted-glass plate, fades in on `data-start`, fades out on `data-end`. CSS comes from `DESIGN.md`-derived variables.
4. Other non-`head` seams render as plain talking-head — they have no `compositions/seam-<id>.html` file. **This is a feature of 6a, not a bug.**
5. `npx hyperframes lint`, `validate`, `inspect`, and `animation-map` (run via `tools/hyperframes-skills/hyperframes/scripts/animation-map.mjs`) are all green. Any `paced-fast` / `paced-slow` / `collision` flags from `animation-map` are explicitly justified or absent.
6. No reference to `tokens.json` remains in the repo. No reference to the deprecated component files remains.

The pilot's pre-6a output is **not** a reference for visual comparison. Phase 4 deliberately did not publish it; there is no canonical output to preserve. Acceptance is structural and functional, not visual-equivalence.

## Architecture decisions (locked)

These were settled during the 2026-04-28 brainstorming. Do not relitigate when implementing:

1. **HF-native sub-composition model.** Root `index.html` + `compositions/<name>.html` per HF skill convention (`<template>`, `data-composition-id`, scoped styles, registered `window.__timelines[id]`). No more inline monolithic `composition.html`.
2. **Layout responsibility split: C-уточнённый.** For `split` and `overlay` scene modes, brand-level layout will live in dedicated layout-shell sub-compositions (`split-frame`, `overlay-plate`) that hold a content slot for bespoke per-seam fills. **Building these shells is deferred to 6b** — the 6a smoke test uses a `broll` seam which needs no shell. For `broll`, bespoke sub-comp is full-canvas (1440×2560) and owns the whole frame.
3. **`DESIGN.md` is the single source of truth for the visual contract.** `tokens.json` is deleted. The compositor parses a fenced JSON block inside `DESIGN.md` and emits `:root` CSS variables directly into `index.html`.
4. **One project-level `DESIGN.md`** at the repo root. Brand identity persists across episodes. No per-episode override in 6a.
5. **HF skills are vendored** read-only into the repo at `tools/hyperframes-skills/`, version-pinned. A sync script refreshes them from the npm tarball on demand. Subagents in 6b read from this directory; no reliance on `npx hyperframes skills` at agent runtime.
6. **Captions migrate to HF's `references/captions.md` pattern**, packaged as a sub-composition. `standards/captions.md` remains as the editorial layer; HF references provide the technical implementation patterns.
7. **6a's compositor still has `seam-plan.md` `graphic:` lines empty/`none`.** Filling them is 6b's job. The compositor wires a per-seam sub-composition only if the file `compositions/seam-<id>.html` exists; otherwise the seam renders as plain head.

## Artifacts

### Created

- `DESIGN.md` (repo root). Sections:
  - `## Style Prompt` — one-paragraph narrative of the channel's visual identity.
  - `## Colors` — prose of role names plus a fenced ` ```json hyperframes-tokens` block holding the structured map: `{ "color": { "<role>": "#<hex>", ... }, "blur": {...}, "spacing": {...}, "radius": {...} }`. The fenced JSON block is the **only** machine-parsed region; everything else is for human and subagent reading.
  - `## Typography` — 1–2 font families with usage guidance.
  - `## Motion` — signature easings, default durations, brand motion rules.
  - `## What NOT to Do` — 3–5 anti-patterns specific to this channel's aesthetic.
- `episodes/<slug>/stage-2-composite/index.html` — root composition emitted by the rewritten compositor (replaces today's `composition.html`).
- `episodes/<slug>/stage-2-composite/compositions/captions.html` — captions as HF sub-composition.
- `episodes/<slug>/stage-2-composite/compositions/seam-<id>.html` — bespoke per-seam sub-composition. In 6a, exactly one synthetic file is committed (or generated by the smoke-test fixture) for the smoke test.
- `tools/hyperframes-skills/` — vendored read-only copy of HF skills, version-pinned in `VERSION`. Directory layout mirrors the npm tarball: `tools/hyperframes-skills/{hyperframes,hyperframes-cli,gsap}/SKILL.md` plus references/scripts/palettes per skill. Sync script extracts `package/dist/skills/*` from `npm view hyperframes dist.tarball` and copies it verbatim.
- `tools/scripts/sync-hf-skills.sh` — refreshes the vendored skills from the latest npm tarball; writes the resolved version into `tools/hyperframes-skills/VERSION`.

### Modified

- `tools/compositor/src/index.ts` — rewritten to: parse `DESIGN.md` → emit `index.html` with CSS variables, master video/audio tracks, captions sub-composition, and per-seam sub-compositions discovered by file existence.
- `tools/scripts/run-stage2-compose.sh` — drops the `hf-project/` staging step (no more `sed`-rename of `composition.html` → `index.html`); calls `lint` + `validate` + `inspect` + `animation-map` against the episode dir directly.
- `tools/scripts/run-stage2-preview.sh` — points `hyperframes render` at the episode dir (whose root composition is now `index.html` directly).
- `tools/scripts/render-final.sh` — adapt path to new compositor output.
- `standards/motion-graphics.md` — WATCH catalog rewritten under HF registry names + `bespoke` markers; obsolete catalog removed.
- `standards/pipeline-contracts.md` — Stage 2 output contract updated: `index.html` (HF-canonical), not `composition.html`.
- `standards/captions.md` — adds a reference to HF `references/captions.md` as the technical implementation layer.
- `standards/retro-changelog.md` — append 2026-04-28 entry: "Phase 6a HF-native foundation".
- `AGENTS.md` — file-location quick map updates: tokens path removed, HF skills location added, compositor output filename change.

### Deleted

- `design-system/tokens/tokens.json` — content migrated into `DESIGN.md`'s fenced JSON block.
- `design-system/components/glass-card.html`
- `design-system/components/title-card.html`
- `design-system/components/overlay-plate.html` — will be re-authored in 6b as an HF-canonical layout-shell; the current file is not salvageable.
- `design-system/components/fullscreen-broll.html`
- `design-system/components/caption-karaoke.html` — replaced by `compositions/captions.html` per-episode.
- `design-system/components/_base.css` — content audited during implementation: any CSS-variable declarations move into the compositor's emit-from-`DESIGN.md` path; any shared base styles (reset, base typography) move into a `<style>` block inside the root `index.html` emitted by the compositor; if the file holds nothing else, delete it.

### Not touched

- `master/bundle.json` contract (Phase 5).
- `seam-plan.md` format — `graphic:` lines remain empty/`none` in 6a.
- `tools/scripts/run-stage1.sh` and Stage 1 in general.
- Music-merge in `render-final.sh` ffmpeg pass.
- Retro discipline, CP protocol, episode-folder layout above `stage-2-composite/`.

## Compositor flow (rewritten)

`tools/compositor/src/index.ts` exposes the same subcommands (`seam-plan`, `compose`) called from `run-stage2-compose.sh`. The `compose` subcommand changes:

**Inputs:**
- `<repo-root>/DESIGN.md` — fenced JSON block parsed; prose ignored at compositor level.
- `episodes/<slug>/master/bundle.json` — words, seams, totalMs.
- `episodes/<slug>/stage-2-composite/seam-plan.md` — seam list with `at`, `scene_mode`. `graphic:` lines ignored in 6a.
- `episodes/<slug>/stage-2-composite/compositions/seam-<id>.html` — discovered by file existence per seam.

**Output (`episodes/<slug>/stage-2-composite/index.html`):**
- Root `<div data-composition-id="root" data-width="1440" data-height="2560" data-start="0" data-duration="<bundle.totalMs/1000>">`.
- `<style>` injecting `:root { --color-<role>: <hex>; --blur-<role>: <px>; --spacing-<role>: <px>; --radius-<role>: <px>; }` from the parsed JSON block.
- `<video>` track-0, `src="../stage-1-cut/master.mp4"`, `muted`, `playsinline`, full canvas.
- `<audio>` track-2, same source, `data-volume="1"`.
- `<div data-composition-src="compositions/captions.html" data-start="0" data-duration="<totalSeconds>" data-track-index="1">`.
- For each seam where `compositions/seam-<id>.html` exists: `<div data-composition-src="compositions/seam-<id>.html" data-start="<atMs/1000>" data-duration="<(endsAtMs-atMs)/1000>" data-track-index="<3+offset>">`.
- No `<template>` wrapper on root (`index.html` is standalone per HF skill).

**Validation pass (still inside `compose`):**
- `npx hyperframes lint <episode-dir>` — fail on errors.
- `npx hyperframes validate <episode-dir>` — fail on errors.
- `npx hyperframes inspect <episode-dir>` — fail on errors.
- `node tools/hyperframes-skills/hyperframes/scripts/animation-map.mjs <episode-dir> --out <episode-dir>/.hyperframes/anim-map` — informational, surface flags.

If any of `lint`/`validate`/`inspect` fail, abort the compose step and surface the JSON output. CP2.5 still happens after `seam-plan.md` is written; CP3 still happens after `final.mp4` is rendered. Validation runs before CP3, not before CP2.5.

## DESIGN.md authoring

In 6a, Claude generates a draft `DESIGN.md` from existing material:
- Palette + blur + spacing + radius values from `design-system/tokens/tokens.json`.
- Motion rules from `standards/motion-graphics.md` (transition matrix, "head visibly shrinks/disappears" rule).
- Caption typography from `standards/captions.md`.
- Style Prompt and What NOT to Do drafted by inspection of pilot composition + frosted-glass aesthetic visible in current components.

Host reviews the draft, edits Style Prompt and What NOT to Do specifically, approves. Only after approval does the rest of 6a proceed (the compositor rewrite depends on DESIGN.md being canonical).

## Captions migration

`design-system/components/caption-karaoke.html` is replaced by per-episode `compositions/captions.html`, written by the compositor's existing word-rendering logic but emitting an HF sub-composition shape:

- `<template id="captions-template">` wrapper.
- `<div data-composition-id="captions" data-width="1440" data-height="2560">`.
- Scoped styles inside the `[data-composition-id="captions"]` selector, using CSS variables from root.
- GSAP timeline paused, registered as `window.__timelines["captions"]`.
- Per-word entrance + exit guarantees from HF `references/captions.md` (the agent reads the references file when implementing this).
- Same word-list and timings as today, sourced from `master/bundle.json`. Per-frame drift up to ±1 frame is acceptable per acceptance criterion.

`standards/captions.md` (typography, position, karaoke timing rules) is not rewritten; it gets a single new line referencing HF's technical implementation patterns.

## Standards updates

### `standards/motion-graphics.md`

The section "Scene-mode → component catalog (WATCH)" is rewritten to:

| Scene mode | Allowed sources                                                                                  |
|---|---|
| `head`     | (none — talking-head only)                                                                        |
| `split`    | `bespoke` via `split-frame` shell (shell ships in 6b; not available in 6a)                       |
| `broll`    | `bespoke` ∪ catalog: `data-chart`, `flowchart`, `logo-outro`, `app-showcase`, `ui-3d-reveal`     |
| `overlay`  | `bespoke` via `overlay-plate` shell (shell ships in 6b) ∪ catalog: `yt-lower-third`, `instagram-follow`, `tiktok-follow`, `x-post`, `reddit-post`, `spotify-card`, `macos-notification` |

The list is the working set as of 2026-04-28. It is not frozen — Phase 6b will refine based on real seam-by-seam tests; further additions/removals are normal retro outcomes. The previous aspirational catalog (`side-figure`, `code-block`, `chart`, `quote-card`, `lower-third`, `subscribe-cta`, `name-plate`, `full-bleed-figure`, `b-roll-clip`) is removed.

### `standards/pipeline-contracts.md`

Add a section: Stage 2 emits an HF-canonical project rooted at `episodes/<slug>/stage-2-composite/index.html`, with sub-compositions under `compositions/`. The previous `hf-project/` staging directory is removed; the compositor writes the canonical layout directly.

### `standards/captions.md`

Add one bullet under "Implementation": "Technical implementation follows HyperFrames' `references/captions.md` pattern (per-word entrance/exit guarantees, tone-adaptive styling, overflow prevention). This standard remains the editorial layer (typography, position, karaoke timing rules); HF references handle the rendering mechanics."

### `standards/retro-changelog.md`

Append a 2026-04-28 entry: "Phase 6a HF-native foundation: project moved onto HyperFrames-canonical sub-composition model; `tokens.json` superseded by `DESIGN.md`; captions migrated to HF pattern; placeholder homemade components deprecated; `validate`/`inspect`/`animation-map` wired into Stage 2."

## Sequence of work

1. **Generate DESIGN.md draft** from existing material; host reviews and approves.
2. **Vendor HF skills.** `tools/scripts/sync-hf-skills.sh` runs once; `tools/hyperframes-skills/` lands in repo with pinned `VERSION`.
3. **Rewrite WATCH catalog** in `standards/motion-graphics.md`; update other standards.
4. **Compositor rewrite.** Parser for `DESIGN.md` JSON block. Emit root `index.html` with tracks. Discover per-seam sub-compositions by file existence.
5. **Captions migration.** Emit `compositions/captions.html` as HF sub-composition; delete `caption-karaoke.html`.
6. **Delete dead components.** `glass-card.html`, `title-card.html`, `overlay-plate.html`, `fullscreen-broll.html`, `_base.css`.
7. **Delete `tokens.json`.**
8. **Adapt scripts.** `run-stage2-compose.sh` (drop `hf-project/` staging, add validate/inspect/animation-map), `run-stage2-preview.sh`, `render-final.sh`.
9. **Smoke fixture.** Create copy of pilot at, e.g., `episodes/2026-04-28-test-fixture-6a/` (or use next real episode); commit a synthetic `compositions/seam-<id>.html` with "6A WIRING OK" text.
10. **Run smoke test.** `run-stage2-compose.sh` + `run-stage2-preview.sh` against the fixture; verify acceptance criteria 1–6.
11. **Commit and tag** `phase-6a-hf-native-foundation`.

Each numbered item is one logical step in the implementation plan. Step 1 (DESIGN.md generation + approval) is a hard gate before any other step starts.

## Risks

- **Captions tone-adaptive styling drift.** HF's `references/captions.md` may produce per-word entrance animations that differ subtly from today's karaoke approach. Mitigation: acceptance allows ±1 frame drift; CP3 ear-checks the result.
- **Sub-composition overhead.** Each `data-composition-src` triggers a fetch + parse + timeline registration. For 8-seam pilot this is trivial; for longer episodes (30+ seams) we should benchmark in 6b before committing to per-seam architecture for everything.
- **HF skill version drift.** A future `hyperframes` upgrade could change skill conventions. Pinning + vendored copy mitigates; sync script makes refresh explicit.
- **`render-final.sh` music-merge interaction.** Today's music merge runs after `hyperframes render`. New compositor output is structurally different but final video format should be identical. Smoke test must verify final.mp4 still passes the 1440×2560 / 60fps / Rec.709 SDR / H.264 / AAC contract from AGENTS.md.

## Out of scope

- Agentic graphics planner (Phase 6b).
- `split-frame.html` and `overlay-plate.html` re-authoring as layout shells (Phase 6b).
- Catalog-block selection logic (Phase 6b).
- `hyperframes add` integration (Phase 6b).
- Per-seam coding subagent dispatch (Phase 6b).
- Retry-on-validation-failure loop (Phase 6b).
- DESIGN.md per-episode override (not planned; brand identity is project-level by 2026-04-28 decision).
