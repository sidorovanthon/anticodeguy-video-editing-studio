# Phase 6a-aftermath Amendment 1 — HF-Self-Contained Final Render

**Date:** 2026-04-28
**Status:** Adopted
**Amends:** `docs/superpowers/specs/2026-04-28-phase-6a-aftermath-design.md`

---

## 1. Trigger — I1 Smoke Test Finding

During the I1 smoke-test run (`run-stage2-compose.sh 2026-04-28-phase-6a-smoke-test`), the
strict `hyperframes validate` step failed with a 404 on loading
`../stage-1-cut/master.mp4`. HyperFrames serves the project directory via a local HTTP
server; the `..` escape places the asset outside the project root, which the server
cannot resolve.

The root cause is architectural: `index.html` referenced an asset that lived outside the
HF project directory. Weakening validate (or splitting HF/ffmpeg rendering) would paper
over the problem. The correct fix is to ensure all assets HF renders are inside
`stage-2-composite/`.

---

## 2. Architectural Decision

**master.mp4 and music move inside `stage-2-composite/assets/`.
HF renders the complete final video in one pass. ffmpeg drops out of Stage 2.**

Concretely:

- `stage-2-composite/assets/master.mp4` — Stage 1's final talking-head + voice artifact.
  Stage 1 writes it here directly (was: `stage-1-cut/master.mp4`).
- `stage-2-composite/assets/music.<ext>` — staged at compose time by
  `run-stage2-compose.sh` from `library/music/<file>` per `meta.yaml`'s `music:` field.
  Skipped if the field is absent or the file is missing.
- `index.html` references both assets via local paths (`assets/master.mp4`,
  `assets/music.<ext>`), fully resolvable by HF's local server.
- `hyperframes render --format mp4 -q high -f 60` produces `final.mp4` in one pass.
  No ffmpeg post-processing step.

---

## 3. HF-Canonical References

These justify why HF can do what was previously delegated to ffmpeg:

| Capability | Source |
|---|---|
| `<video src="talking-head.mp4">` as a first-class HF clip | `tools/hyperframes-skills/hyperframes/patterns.md` (talking-head pattern) |
| `data-volume` attribute (0–1, default 1) on `<audio>` clips | `tools/hyperframes-skills/hyperframes/SKILL.md` line ~124 |
| `paths.assets: "assets"` already declared in HF project | `stage-2-composite/hyperframes.json` — we start using it |

HF supports video and audio clips natively. The "render overlays as transparent MOV,
merge in ffmpeg" approach was a workaround for a solved problem.

---

## 4. Pipeline Impact

### Stage 1 contract change
`run-stage1.sh render` now writes `master.mp4` to
`episodes/<slug>/stage-2-composite/assets/master.mp4` instead of
`episodes/<slug>/stage-1-cut/master.mp4`.

`stage-1-cut/` retains all intermediate artifacts (`raw.mp4`, `transcript.json`,
`edl.json`, `cut-list.md`, optional `script-diff.{md,json}`). Master.mp4 is no longer
stored there.

The `write-bundle` entrypoint in `tools/compositor/src/index.ts` is updated to read
`masterPath` from the new location.

### Compose step
`run-stage2-compose.sh` gains a music-copy block executed before seam-plan/index.html
generation. The block reads `meta.yaml`, copies the music file into `assets/`, and skips
if already up-to-date (mtime comparison). The compositor detects the file's presence and
emits the music audio clip; absent music = no clip.

The existing check `[ -f "$EPISODE/stage-1-cut/master.mp4" ]` in the compose script is
updated to `[ -f "$EPISODE/stage-2-composite/assets/master.mp4" ]`.

### render-final.sh
Becomes a thin wrapper: validates preconditions, then calls
`npx -y hyperframes render "$COMPOSITE_DIR" -o final.mp4 -f 60 -q high --format mp4`.
The ffmpeg `overlay + loudnorm + amix` pipeline is removed entirely.

---

## 5. Audio Mastering Simplification

The old pipeline applied `loudnorm` (two-pass) to the music sidecar and merged it via
`amix` with weighted normalization. This was necessary because ffmpeg operated on raw
audio streams without per-track volume metadata.

HF's compositor renders audio natively using `data-volume` attributes on `<audio>` clips:

- Voice (master.mp4 audio): `data-volume="1"` — full level.
- Music: `data-volume="0.5"` — attenuates by ~6 dB below voice.

Music files in `library/music/` are professionally pre-mastered (target −16 to −20 LUFS).
No per-episode loudnorm step is needed. If a candidate track is too loud or unmastered,
it is mastered once during library curation.

---

## 6. Migration

- **Smoke-test fixture** (`episodes/2026-04-28-phase-6a-smoke-test/`): `master.mp4` is
  moved from `stage-1-cut/` to `stage-2-composite/assets/` via `git mv`. Stale
  `.inspect.json` and `preview.mp4` are removed (regenerable). Music is NOT pre-committed;
  it is staged on the next compose run.
- **FROZEN pilot** (`episodes/2026-04-27-desktop-software-licensing-it-turns-out/`):
  Remains non-canonical and stays as-is. Already documented as a frozen artifact that
  must not be used as a reference.

---

## 7. Task Index (X2–X7)

| Task | Description |
|---|---|
| **X2** | `run-stage1.sh` + `index.ts` write `master.mp4` to `stage-2-composite/assets/` |
| **X3** | `run-stage2-compose.sh` copies music from `library/music/` into `assets/` at compose time |
| **X4** | Compositor emits `assets/master.mp4` refs and optional `TRACK_MUSIC=5` audio clip with `data-volume="0.5"` |
| **X5** | `render-final.sh` replaced with thin `hyperframes render` wrapper; ffmpeg removed |
| **X6** | Smoke-test fixture migrated: `master.mp4` moved into `assets/`; stale files cleaned |
| **X7** | `standards/pipeline-contracts.md`, `AGENTS.md`, `standards/audio.md` updated for new contract |
