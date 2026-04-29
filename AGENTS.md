# AGENTS.md — Anticodeguy Video Editing Studio

## TL;DR
You edit YouTube/TikTok shorts (1–3 min, 9:16, EN). Raw footage arrives in `incoming/`.
Final output is `episodes/<slug>/stage-2-composite/final.mp4`. The pipeline runs in
**checkpoint mode** — between checkpoints you work autonomously; on a checkpoint you
stop and wait for explicit user approval.

## Inputs you can expect
- `incoming/raw.mp4` — talking-head footage, English, scripted, with mistakes and pauses.
- `incoming/notes.md` (optional) — episode topic, do-not-cut spans, special instructions.
- `incoming/script.txt` (optional) — verbatim plain-text script of what was read on camera.
  Enables the script-fidelity report at CP1.
- A music file already present in `library/music/`. Episode `meta.yaml` will reference it.

## Pipeline (read in order)
1. **new-episode** — `tools/scripts/new-episode.sh <slug>` creates `episodes/<YYYY-MM-DD>-<slug>/`,
   moves `incoming/raw.mp4` into `source/`, writes a starter `meta.yaml`.
2. **Stage 1 — video-use** — produces post-production-ready talking-head master.
   - 1.1 ElevenLabs Scribe transcription → `stage-1-cut/transcript.json`
   - 1.2 Cut analysis → `stage-1-cut/cut-list.md` → **⏸ CP1**
   - 1.2a (optional, if `source/script.txt` present) Script fidelity check
     → `stage-1-cut/script-diff.md` and `script-diff.json`
   - 1.3 Apply cuts + audio fades + grade + vignette → `stage-2-composite/assets/master.mp4` → **⏸ CP2**
3. **Stage 2 — compositor** — overlays captions, motion graphics, music.
   - 2.1 Generate `stage-2-composite/seam-plan.md` → **⏸ CP2.5**
   - 2.2 Build `index.html`, render `preview.mp4` → **⏸ CP3**
   - 2.3 Final render via hyperframes (HF mixes voice + music natively per data-volume) → `final.mp4`
4. **Retro** — fill `episodes/<slug>/retro.md`, run macro-retro, propose standards
   updates as `WATCH` / `CONFIRM` / `PROMOTE`. User selects which to promote.

> **FROZEN pilot caveat.** `episodes/2026-04-27-desktop-software-licensing-it-turns-out/` predates Phase 6a and ships a non-canonical Stage 2 layout (`composition.html`, `hf-project/` staging dir, no `hyperframes.json`/`meta.json`). Do not use it as a reference for compositor output, lint settings, or directory structure. The smoke-test fixture `episodes/2026-04-28-phase-6a-smoke-test/` is the canonical example.

## Standards (load before working on the matching stage)
- `standards/editing.md`         — cut philosophy, what to keep
- `standards/color.md`           — grade settings, source rejection rules
- `standards/audio.md`           — voice levels, music flat-background, no duck by default
- `standards/captions.md`        — typography, position, karaoke timing
- `standards/motion-graphics.md` — 4-scene system, transition matrix
- `standards/pipeline-contracts.md` — Stage 1 → Stage 2 contract (master-aligned rule)
- `standards/retro-changelog.md` — append-only history; never edit existing entries

## Checkpoint protocol
At a checkpoint, post a single message:
```
CP<N> ready: <artifact path>. Awaiting review.
```
Then **stop**. Do not continue until the user replies `go` or supplies edits.
If edits are supplied, apply them and re-run the same checkpoint. Loop until `go`.

## Retro discipline
`episodes/<slug>/retro.md` records **only deltas**: what you proposed, what the user
changed, why if known. Each delta yields at most one proposed rule change tagged
`WATCH`, `CONFIRM`, or `PROMOTE`. Do not summarize the episode narratively.

## Hard rules
- Never edit `standards/*.md` outside macro-retro with explicit user `PROMOTE`.
- Never edit `standards/retro-changelog.md` historically — append only.
- Never commit music files into episode folders — `run-stage2-compose.sh` copies them into `stage-2-composite/assets/` at compose time (gitignored). The authoritative source is always `library/music/`.
- Never skip a checkpoint. A checkpoint without stop is a bug.
- Run `run-stage2-preview.sh` and `render-final.sh` only on hosts with sufficient free RAM. The wrapper's local-mode defaults (`--workers 1 --quality draft --max-concurrent-renders 1`) keep peak combined RSS at ~1.3 GB on full 1440×2560 compositions (per `docs/operations/render-oom/findings.md`, 2026-04-29). The original Phase 6a OOM was caused by host-side memory pressure (~45 background `chrome.exe` instances), not by HF itself. Discipline: close memory-hungry apps before rendering; the wrapper emits a stderr warning if you try to render a >30 s episode in local mode without `--draft`. On hosts without RAM headroom, run the command via `run_in_background: true` or hand it to the user. Docker remains required for byte-identical production-final renders, not as a memory-safety guard.
- Never produce a seam transition forbidden by the matrix in `standards/motion-graphics.md`
  (`head↔head`, `head↔overlay`, `overlay↔overlay`, same-graphic `split→split` or `full→full`;
  alias form: `a↔a`, `a↔d`, `d↔d`, `b→b`, `c→c`).
- Never let raw-timeline data cross the Stage 1 → Stage 2 seam. See
  `standards/pipeline-contracts.md` for the master-aligned rule.
- Never accept HDR/HLG source. Reject at `new-episode.sh` with a clear error.
- **No preview or final render runs without HF gates green: `lint` (no errors) + `validate` (no errors) + `inspect --strict` (no warnings).** The compose wrapper enforces this; do not bypass by editing the wrapper unless you have a written justification in the run log and explicit user approval. `lint`/`validate` carry `--strict-all` for forward-compatibility with future HF versions, but in HF v0.4.x only `inspect --strict` actually fails on warnings. See `tools/scripts/run-stage2-compose.sh`.
- All repo content (code, docs, file names, commit messages, retros) is **English**.
- All chat communication with the user is **Russian**, including checkpoint summaries.
- Final `final.mp4` must be 1440×2560, 60 fps, Rec.709 SDR, H.264 high, AAC 320 kbps,
  ~35 Mbps VBR. Validate before declaring CP3 done.

## Communication
- All repo content is English.
- All chat replies, checkpoint summaries, retros explanations, error messages to the user — **Russian**.
- Talking-head video content (audio, captions, transcripts) is English.

## Tooling
- Verify environment: `tools/scripts/check-deps.sh`
- New episode: `tools/scripts/new-episode.sh <slug>`
- Stage 1 (added in Phase 2): `tools/scripts/run-stage1.sh <slug>`
- Stage 2 compose (added in Phase 3): `tools/scripts/run-stage2-compose.sh <slug>`
- Stage 2 preview (added in Phase 3): `tools/scripts/run-stage2-preview.sh <slug>`
- Final render (added in Phase 3): `tools/scripts/render-final.sh <slug>`
- Script fidelity check (added in Phase 3.5): `tools/scripts/script-diff.py --episode <path>`
- Retro promotion (added in Phase 4): `tools/scripts/retro-promote.sh <slug>`

## File-location quick map
- Sources                → `incoming/`, then `episodes/<slug>/source/`
- Music                  → `library/music/` only — never copied
- Visual contract         → `DESIGN.md` (repo root; fenced `hyperframes-tokens` JSON block is the only machine-parsed region)
- HF skills (vendored)    → `tools/hyperframes-skills/` (refresh via `tools/scripts/sync-hf-skills.sh`; self-contained subproject — `npm install` here on fresh checkout to provide `@hyperframes/producer` to the helper scripts)
- Layout shells           → `design-system/components/` (currently empty in 6a; populated in 6b)
- Per-episode artifacts  → `episodes/<slug>/`
  - `source/raw.mp4`           — incoming footage (from `incoming/`)
  - `stage-1-cut/`             — Stage 1 intermediates (transcript.json, edl.json, raw.mp4 staging)
  - `stage-2-composite/`       — HF project root (self-contained)
    - `assets/master.mp4`      — Stage 1 final artifact (talking-head + voice); written here directly by `run-stage1.sh ... render`
    - `assets/music.<ext>`     — staged at compose time from `library/music/`
    - `index.html`             — HF project entry
    - `compositions/`          — sub-compositions (captions, transitions, per-seam)
- Long-lived rules       → `standards/`
- Scripts                → `tools/scripts/`

## Environment
- `ELEVENLABS_API_KEY` is required (Scribe API). Plan must be Creator tier or higher.
- ffmpeg, node 20+, python 3.11+ with uv, git — all in PATH. Verify with `check-deps.sh`.

## Render modes

Default is `HF_RENDER_MODE=local` — `hyperframes render` runs directly. Empirically the wrapper's local-mode defaults (`--workers 1 --quality draft --max-concurrent-renders 1`) keep peak combined RSS at ~1.3 GB on full 1440×2560 compositions on a 32 GB host (see `docs/operations/render-oom/findings.md`). Do not change these knobs without re-measuring on a memory-pressured host.

Docker mode (`HF_RENDER_MODE=docker tools/scripts/run-stage2-preview.sh <slug>`) is opt-in and exists for byte-identical reproducibility across hosts — not a memory-safety requirement. We have no current use case for it; it remains supported for operators who do.
