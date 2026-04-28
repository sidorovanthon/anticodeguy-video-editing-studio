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
