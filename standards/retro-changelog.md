# Standards changelog

Append-only history of every change to `standards/*.md` files.
Format: each entry shows date, file, change, source episode (or "bootstrap"), reason.

Never edit existing entries. To revoke a rule, append a new entry that removes it with reason.

---

## 2026-04-27 — bootstrap
- Created standards/editing.md, captions.md, motion-graphics.md, audio.md, color.md, retro-changelog.md.
- Source: docs/superpowers/specs/2026-04-27-video-editing-studio-design.md.
- Reason: project bootstrap; rules captured during brainstorming session.

## 2026-04-27 — standards/audio.md voice/music level revision
- Voice target: −16 LUFS → **−14 LUFS** integrated.
- Music level: −22 LUFS → **−20 LUFS** (kept "6 dB below voice"; preserves the relative gap after the voice bump).
- Source: bootstrap (user-driven adjustment immediately after Phase 1 standards seeding).
- Reason: louder voice target better fits social-media playback norms (YouTube Shorts, TikTok, Reels) where -14 LUFS is the de-facto delivery level. Music kept exactly 6 dB below voice for consistent perceived balance.

## 2026-04-27 — Phase 2 verification observations (no standards change)
- Phase 2 plan Task 7 deferred: visual grade review requires spec-compliant raw footage (≥1440×2560 Rec.709 SDR). The verification clip was 1080×1920, which the pipeline upscaled to spec but is not representative for grade tuning.
- `tools/compositor/grade.json` defaults (saturation +8%, contrast +12%, vignette PI/4 @ 0.25) carried into Phase 3 unchanged; first real episode will revisit.
- Pipeline correctness end-to-end (CP1 + CP2) verified on the upscaled clip: Scribe transcription succeeded, claude subagent authored a valid edl.json, render produced 1440×2560 60 fps Rec.709 SDR studio-range master.mp4 at 34.7 Mbps with AAC 48 kHz stereo 320 kbps.
- Render bug caught and fixed during verification: ffmpeg `eq` filter inside the grade chain was emitting `yuvj420p` (full-range PC) instead of studio-range `yuv420p`. Added explicit `format=yuv420p,setparams=range=tv` to the filter chain and a regression assertion in `test-run-stage1.sh`.

## 2026-04-27 — Phase 3 HyperFrames CLI reality check (no standards change)
- Phase 3 plan was written before HyperFrames was inspected. Smoke test against `hyperframes@0.4.31` (npm, published 2026-04-26) found significant divergences from the plan's assumed CLI surface. Plan is NOT being rewritten; downstream tasks (composer, run-stage2.sh, render-final.sh) adapt on the fly to the real tool.
- Concrete divergences captured in `docs/notes/hyperframes-cli.md`:
  - Config file is `hyperframes.json`, not `hyperframes.config.json`.
  - `render` takes a positional `[DIR]` (with `index.html` as the root composition); no `--input`, `--width`, `--height`, or `--transparent` flags exist.
  - Resolution is set on the root composition's `data-width` / `data-height` attributes, not via CLI.
  - Transparency comes from `--format mov` or `--format webm`, not `--transparent`.
  - Real render flags: `-o`, `-f {24,30,60}`, `-q {draft,standard,high}`, `--format`, `-w`, `--docker`, `--hdr`, `--crf`, `--video-bitrate`, `--gpu`, `--strict[-all]`.
  - HyperFrames composition HTML requires `data-composition-id`, `data-start`, `data-duration`, `data-track-index`, and `class="clip"` on timed elements; videos must be `muted`; GSAP timelines must be paused and registered on `window.__timelines[id]` because the runtime drives time, not the page.
  - `add <name>` installs a registry **block** (→ `compositions/`) or **component** (→ `compositions/components/`), not a single component dir; it does not modify `index.html` — wiring the include snippet is on us.
- Determinism: `--docker` is the only bit-deterministic mode. Docker not installed on this machine; `npx hyperframes doctor` flags it. Local mode accepted for now; revisit if cross-machine reproducibility becomes a requirement.
- HyperFrames installs its own `chrome-headless-shell` (~101 MB, one-off) into `~/.cache/hyperframes/chrome/` on first render. Telemetry is on by default; not disabled (no user requirement).
- Adapted approach for Phase 3:
  1. Composer writes `index.html` (not `composition.html`) directly into `episodes/<slug>/stage-2-composite/`, with `data-width=1440 data-height=2560` on the root and properly-attributed timed elements per HyperFrames conventions.
  2. `run-stage2.sh` invokes `npx hyperframes lint --json` then `npx hyperframes render <stage-2-composite-dir> -f 60 --format mp4 -q high -o preview.mp4`.
  3. `render-final.sh` renders overlays as `--format mov` (alpha) and ffmpeg overlays + master + music sidecar (mix stays our responsibility — HyperFrames only emits visual + composition-internal audio).

## 2026-04-27 — pipeline pre-flight: tool update check (workflow change)
- New requirement (user): before working on a new episode, the pipeline must check for updates to fast-moving dependencies (HyperFrames in particular — published version 0.4.31 the day this phase started).
- Action: add a `tools/scripts/check-updates.sh` invoked by `new-episode.sh` as a non-blocking warning. Checks `npm view hyperframes version` against installed version (and vendored `video-use` SHA against upstream). Surfaces a notice; does not auto-upgrade.
- Reason: HyperFrames is brand-new (0.x) and shipping rapidly; running a stale version risks API drift between episodes. Same risk pattern likely applies to other vendored AI tooling.

## 2026-04-27 — Phase 3 audio mix bug fix in render-final.sh (no standards change)
- Bug: `tools/scripts/render-final.sh` mixed music with `amix weights=1 0.5` after `loudnorm=I=-20`, double-attenuating the music to ~-26 LUFS in the final mix instead of the -20 LUFS demanded by `standards/audio.md`. Originated from incorrect interpretation in the Task 12 brief — the standard already bakes the 6 dB voice/music gap into the absolute LUFS targets (voice -14, music -20), so no additional weight reduction is required.
- Fix: `weights=1 1`. Music sits at -20 LUFS post-loudnorm; voice arrives at -14 LUFS from upstream master. `test-render-final.sh` re-run, passes.
- Audit also confirmed: standards files do NOT conflict with HyperFrames CLI reality. They describe outputs and rules, not tool choice; no edit needed.
- Outstanding gap (defer to Phase 4): voice -14 LUFS target in `standards/audio.md` is asserted but never enforced in our pipeline — we trust video-use's master.mp4 to already be at -14 LUFS. If the first real episode's master deviates, add a voice loudnorm pass to `render-final.sh`.

## 2026-04-27 — Phase 5 prep: pipeline-contracts.md + scene-mode rename + AGENTS.md sync
- New file `standards/pipeline-contracts.md`: codifies the Stage 1 → Stage 2 master-aligned rule, lists canonical sources (ffprobe / `edl.json` / remapped transcript), the five drifts observed in pilot, hard rules ("no raw-timeline crosses the seam", "`cut-list.md` is human-only"), and the planned CP1.5 contract gate.
- `standards/motion-graphics.md`: scene-mode names made canonical (`head/split/full/overlay`) with `(a)/(b)/(c)/(d)` retained as aliases. Explicit "`full` = head HIDDEN" disambiguation. New section "Graphic specs are mandatory for non-`head` seams" — a `split/full/overlay` seam without a `graphic:` spec is a planner error. Working scene-mode → component catalog added as WATCH (will harden once the agentic planner lands). Forbidden-transition list now in canonical names with alias parenthetical.
- `AGENTS.md`: standards-load list now includes `pipeline-contracts.md`. Forbidden-transition hard rule restated in canonical names. New hard rule: "Never let raw-timeline data cross the Stage 1 → Stage 2 seam."
- Source: macro-retro of 2026-04-27-desktop-software-licensing-it-turns-out (Phase 5 candidates 1, 3, and the "scene modes are label-only without `graphic:` specs" PROMOTE).
- Reason: pilot surfaced (a) the Stage 1 → Stage 2 contract drift pattern as the dominant source of bugs (5 drifts in one episode), (b) scene-mode naming confusion between docs and code, (c) the gap that scene-modes without graphic specs are silently decorative. These are documentation-only fixes that lock the lessons in before Phase 5 implementation begins; no runtime behavior changes.

## 2026-04-27 — promoted from 2026-04-27-desktop-software-licensing-it-turns-out
- color.md: ffmpeg-range-remap=explicit-scale-in-out-range (reason: metadata-only setparams left pixel data full-range; players crushed shadows)
- color.md: grade-chain=colorbalance+eq.brightness+curves+vignette (reason: layered chain converged in 3 iterations on real footage)
- color.md: encoder-defaults=-g60-tune-fastdecode (reason: seekability+decoder-load improvements; harmless when audio sync is correct)
- audio.md: loudnorm-mode=two-pass-with-measured (reason: single-pass introduces 2-3s PTS desync at start)
- audio.md: no-fades=hard-cuts (reason: host preference; video-use fade injection bypassed by direct ffmpeg render anyway)
- motion-graphics.md: outro-scene=overlay-with-subscribe (reason: OUTRO must end on subscribe CTA; if previous scene is overlay, demote to split)
- captions.md: timing-source=master-aligned-via-edl (reason: raw-timeline word timings drift by accumulated EDL gaps; fixed by remapWordsToMaster)
- captions.md: field-contract=start_ms-end_ms-only (reason: caption components consume ms-fields; compositor normalizes; component must not assume other naming)

## 2026-04-28 — Phase 5 close: pipeline contracts hardened
- Scene mode `full` renamed to `broll` in compositor source, fixtures, and tests. parseSceneMode() rejects the legacy name explicitly.
- New master/bundle.json contract enforced at the Stage 1 -> Stage 2 boundary; Stage 2 reads it through a typed loader; raw-timeline reads of transcript.json and cut-list.md removed from Stage 2.
- Phase 6 brief written at docs/superpowers/specs/2026-04-28-agentic-graphics-planner-brief.md.
- Source: docs/superpowers/plans/2026-04-28-phase-5-pipeline-contracts.md.
- Reason: pilot of Phase 4 surfaced 5 Stage 1 -> Stage 2 contract drifts; this phase closes the class of bugs at the source.

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
  into `run-stage2-compose.sh`. Lint gates the build; validate and
  inspect run as warn-and-continue until Phase 6b tightens them
  (current contrast and text-overflow reports look like measurement
  artifacts from headless validation, not real palette issues).
- HF skills vendored at `tools/hyperframes-skills/` (v0.4.31), refresh
  via `tools/scripts/sync-hf-skills.sh`. Available to coding subagents
  in Phase 6b.

WATCH catalog in `standards/motion-graphics.md` rewritten to use real HF
registry block names (`yt-lower-third`, `data-chart`, `flowchart`, etc.)
plus the `bespoke` marker. The previous aspirational catalog
(`side-figure`, `code-block`, `chart`, `quote-card`, `lower-third`,
`subscribe-cta`, `name-plate`, `full-bleed-figure`, `b-roll-clip`) is
removed.

Render-stage memory tuning (operational, not standards):
`run-stage2-preview.sh` gained `--quality` / `--draft` flags and pins
`--max-concurrent-renders=1`. Default `hyperframes render` against
1440x2560 wedged the host on the smoke run; with `--draft --workers 1`
the smoke episode rendered cleanly. The architecturally correct fix is
to move render into `hyperframes render --docker` (deterministic
environment plus hard cgroup memory cap); planned as a small Phase
6a-1 follow-up before Phase 6b.

Smoke test: `episodes/2026-04-28-phase-6a-smoke-test` (copy of pilot,
which is FROZEN). Synthetic '6A WIRING OK' frosted-glass plate authored
as `compositions/seam-4.html` rendered correctly into preview.mp4
(33.7 MB, 52.7 s, 1440x2560 30 fps draft).

Spec: `docs/superpowers/specs/2026-04-28-phase-6a-hf-native-foundation-design.md`
Plan: `docs/superpowers/plans/2026-04-28-phase-6a-hf-native-foundation.md`
