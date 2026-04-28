# Pipeline contracts

## Purpose
Normative shape of data crossing the Stage 1 → Stage 2 boundary. Stage 1 is the
sole producer of master-aligned artifacts; Stage 2 reads those and never
re-derives timing from raw-timeline sources.

## The master-aligned rule
After Stage 1, every timestamp Stage 2 sees must refer to `master.mp4`'s
post-EDL timeline, not the raw recording timeline. Raw-timeline data
(`transcript.json` as emitted by ElevenLabs Scribe, `audio_duration_secs`,
unmapped word `start`/`end`) never crosses the seam unmodified.

Stage 1 is responsible for the remap. Stage 2 trusts the master-aligned bundle
without recomputing.

## Canonical sources

| Question                                  | Authoritative source                       |
|---|---|
| Master duration                           | ffprobe on `master.mp4` (or EDL cumulative)|
| Per-word caption timing                   | `transcript.json` after `remapWordsToMaster` (master-aligned, ms) |
| Seam boundaries (`at_ms`)                 | `edl.json` cumulative range lengths        |
| Human-readable cut summary                | `cut-list.md` — display only, not parsed   |
| Scene-mode and graphic spec per seam      | `seam-plan.md` (one entry per seam)        |

`cut-list.md` is human-only. Stage 2 must not parse it for timing. If Stage 2
needs a seam timestamp, the source is `edl.json`.

## Field-naming contract
- All durations and timestamps that cross the seam are in **milliseconds**, suffix `_ms`.
- Caption components consume `start_ms` / `end_ms` only. The compositor
  normalizes any upstream variant before serialization. Components must not
  assume any other field naming.

## Observed drifts (2026-04-27 pilot)
Five drifts caught on the first real episode. Recorded here as a normative
example so future Stage 2 work can self-check against this list:

1. `transcript.audio_duration_secs` (sec) ↔ compositor expected `duration_ms` (ms).
2. `cut-list.md` parsed for `at_ms=` markers Stage 1 never wrote.
3. `transcript.duration_ms` (≈ raw recording length) used as master duration
   (real `master.mp4` is post-EDL, ~25% shorter).
4. Word-timing field-name drift: `start`/`end` (sec) ↔ `start_ms`/`end_ms`.
5. Word timings in raw timeline used directly, without remap through EDL gaps.

Root pattern: Stage 2 assumes master-aligned input; Stage 1 emitted raw-aligned.
Phase 3 fixtures masked all five because they were minimal and pre-aligned.

## Hard rules
- Stage 2 never reads `transcript.json` raw-timeline fields directly; it reads
  the master-aligned bundle Stage 1 produced.
- Stage 2 never parses `cut-list.md` for timing. `edl.json` is the seam source.
- Master duration comes from ffprobe on `master.mp4` (or EDL cumulative), never
  from the transcript.
- Any new field crossing the seam carries an explicit unit suffix (`_ms`,
  `_secs`) — no bare `duration`, `start`, `end`.

## CP1.5 contract gate (planned)
A lightweight validator runnable as part of `run-stage1.sh` that asserts the
shape Stage 2 expects (master-aligned words[], master duration, EDL-derived
seam boundaries). Catches drift at Stage 1 instead of crashing Stage 2.
Status: not yet implemented; tracked for Phase 5.

### Stage 2 output (post Phase 6a)
Stage 2 emits a HyperFrames-canonical project rooted at
`episodes/<slug>/stage-2-composite/index.html`, with sub-compositions
under `episodes/<slug>/stage-2-composite/compositions/`. The previous
`hf-project/` staging directory is removed; `index.html` is the
canonical entry consumed directly by `npx hyperframes lint /
validate / inspect / render`. Captions live at
`compositions/captions.html`; per-seam bespoke graphics (when present,
Phase 6b onward) live at `compositions/seam-<id>.html`.

> **FROZEN pilot caveat.** `episodes/2026-04-27-desktop-software-licensing-it-turns-out/stage-2-composite/` is non-canonical (predates Phase 6a; uses `composition.html` + `hf-project/`). The canonical contract below is what `run-stage2-compose.sh` emits today: `index.html`, `compositions/captions.html`, `compositions/transitions.html`, `compositions/seam-<id>.html`, `hyperframes.json`, `meta.json`, `seam-plan.md`.

### Asset locations (post 6a-aftermath)

`stage-2-composite/` is a self-contained HF project. All assets HF needs to render the final video live inside it:

- `assets/master.mp4` — Stage 1's final talking-head + voice artifact. Stage 1 writes here directly. Do NOT keep a copy under `stage-1-cut/master.mp4`.
- `assets/music.<ext>` — staged at compose time by `run-stage2-compose.sh` from `library/music/<file>` per `meta.yaml`'s `music:` field. Skipped if the field is absent.
- `compositions/*.html` — sub-compositions emitted by the compositor.

`stage-1-cut/` retains the intermediate Stage 1 artifacts (`raw.mp4`, `transcript.json`, `edl.json`, `cut-list.md`, optional `script-diff.{md,json}`). Master.mp4 is no longer here.

### Audio mixing (post 6a-aftermath)

HF renders the final audio mix natively via `data-volume` attributes on `<audio>` clips. Voice (master) at `data-volume="1"` (full); music at `data-volume="0.5"` (~-6 dB ducked below voice). Music in `library/music/` is professionally pre-mastered — no `loudnorm` step is applied during render. The previous ffmpeg `loudnorm`/`amix` pipeline in `render-final.sh` is removed.
