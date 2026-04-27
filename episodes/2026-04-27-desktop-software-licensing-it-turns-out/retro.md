## CP1

EDL: 6 ranges, 52.54s (raw 64.9s). Editorial call — aborted restart at 36.70 cut, successful retake at 43.00–49.78 kept. Approved as-is.

Script-fidelity: coverage 96.2%, 0 dropped, 0 ad-libs, 1 retake. Two Scribe transcription errors detected:
- script "query a database" → transcript "require a database"
- script "hardware protection keys" → transcript "hardware production keys"

Audio is correct (host said the right words); only the transcript text is wrong. Today this means Stage 2 captions will display the wrong words verbatim from `transcript.json`.

**WATCH** — proposal for follow-up phase: at captions step in Stage 2, when `source/script.txt` exists, use it as ground-truth and rewrite transcript words to script words where script-diff alignment shows a substitution, preserving transcript timings. Building blocks already exist in `tools/scripts/script_diff/align.py`. Defer for now; revisit after observing 1–2 more episodes to confirm the pattern (Scribe mishears on technical terms) is consistent.

## CP2

Heavy iteration. Captured deltas across grade, encoder, and audio.

### Grade

Initial render shipped almost-black picture. Root cause: `_render_edl.py` had `format=yuv420p,setparams=range=tv` which only updates metadata; pixel values stayed full-range (yuvj420p source, 0–255) but were tagged tv-range, so players crushed shadows/highlights. Fix: explicit `scale=...:in_range=auto:out_range=tv` performs the actual data remap. **PROMOTE** to standards/color.md.

Initial grade chain `eq=saturation=1.08:contrast=1.12,vignette=PI/4:eval=init` was too crude. Translated host's Premiere Lumetri reference (Temp +21.7 / Tint +8.3 / Exposure +0.6 / Contrast +7.2 / Highlights −26.5 / Whites +12.3 / Saturation 95.4 / mild S-curve) to a layered ffmpeg chain:
```
colorbalance=rm=0.05:gm=-0.01:bm=-0.03,
eq=brightness=0.05:saturation=0.98,
curves=master='0/0 0.25/0.20 0.5/0.55 0.75/0.78 1/0.95',
vignette=PI/4:eval=init
```
Two iterations: first warmth pass `rm=0.10` was too orange; halving worked. **PROMOTE** the colorbalance + curves + eq.brightness fields as the canonical `grade.json` schema (drop `eq.contrast` — S-curve handles it).

Frame extraction via `ffmpeg -ss <t> -frames:v 1` + reading the PNG into the agent context is a tight feedback loop for grade tuning. Took 3 grade iterations to converge; without per-iteration visual the loop would have required user playback every time. **PROMOTE** auto-extracting 2–3 sample frames to `stage-1-cut/preview-frames/` after each render so the agent can self-review before posting CP2.

### Encoder / playback

Reproducible video stutter for first 2–3 seconds in MPC-HC + LAV (also in WMP). Tried: `-g 60` (keyframe per second) and `-tune fastdecode` (CABAC off, lighter B-pyramid). Neither helped on its own. Both kept anyway — they don't hurt and make seekability + decoder load saner. **PROMOTE** `-g 60` and `-tune fastdecode` to standards/color.md as render defaults.

Real root cause of stutter was audio (see below).

### Audio

`standards/audio.md` says video-use applies 30 ms fades at cuts. But `_render_edl.py` renders directly via ffmpeg, bypassing video-use, so fades were never applied. Host preference is **hard cuts** anyway. **PROMOTE** drop the fade requirement from standards/audio.md.

Adding `loudnorm=I=-14:TP=-1.0:LRA=11` (single-pass) introduced PTS desync at the start: video plays normally, audio clock freezes for 2–3 s, then catches up. This is loudnorm's lookahead/buffering in single-pass mode. Symptom presented as a video stutter to the host because MPC-HC drives its time display from audio PTS.

Resolved by switching to a non-lookahead pipeline:
1. **ElevenLabs `/v1/audio-isolation`** — sent the master's audio track (52 s WAV) to `https://api.elevenlabs.io/v1/audio-isolation`; got back a clean mono 320 kbps MP3. Voice stripped of room tone and HVAC noise. No level normalization from the API — output is at the source's nominal level. (Noted: API key needs the `audio_isolation` permission scope — Scribe-only keys return `401 missing_permissions`.)
2. **dynaudnorm** for per-frame compression+normalization (no lookahead, no PTS issue), then **two-pass loudnorm** with measured values (also no lookahead because the measurements are pre-computed). Final settled chain: `dynaudnorm=p=0.79:m=10:g=15:s=12,loudnorm=I=-14:TP=-1.5:LRA=11:measured_*=…`. Output: −15.2 LUFS, peak −1.5 dBTP, LRA 1.9 LU. Slightly under the −14 spec because TP cap binds, but clean and audibly loud.

For this pilot episode the audio chain was applied **manually** post-render: extract → curl Audio Isolation → dynaudnorm+loudnorm → re-mux. `_render_edl.py` was reverted to a pipeline-friendly stopgap (`dynaudnorm` only, no Audio Isolator) so future episodes don't break. Full integration is the headline retro item.

**PROMOTE** to audio.md: never use single-pass loudnorm; use two-pass with measured values, or dynaudnorm. **PROMOTE** integrating Audio Isolator into Stage 1 before transcribe so:
- Scribe transcribes a clean signal (likely fewer mishears like the Scribe `query→require` / `protection→production` errors observed at CP1).
- Render uses the cleaned audio directly, no manual step.
- Architectural sketch: new helper `tools/scripts/audio_clean.py` that POSTs raw audio to `/v1/audio-isolation` and writes `source/voice-clean.wav`; `run-stage1.sh` muxes original video + cleaned audio into `raw-clean.mp4` (cached); transcribe + EDL + render all reference `raw-clean.mp4`.

### Approval

CP2 approved by host: grade, exposure, color temperature, audio loudness and cleanliness all acceptable.

## CP2.5

- **Stage 1 → Stage 2 transcript contract mismatch.** Stage 1 writer emits ElevenLabs-native `audio_duration_secs` (sec); compositor required `duration_ms` (ms). Phase 3 fixtures masked this. Patched compositor to accept both with `duration_ms` canonical. Follow-up: normalize at Stage 1 writer so the contract is one-way. Candidate `PROMOTE` line for `standards/transcript.md` (or wherever transcript schema lives — check) once confirmed.
- **Propose CP1.5 contract validation.** A lightweight check after Stage 1 that asserts the transcript shape Stage 2 expects (words[] non-empty, a duration field present in either form). Catches schema drift at Stage 1 instead of crashing Stage 2. Tag `WATCH` for now — promote after a second episode confirms it's worth the gate.
- **Stage 1 → Stage 2 cut-list contract drift.** `cut-list.md` is human-readable phrase markdown; compositor parses it for `at_ms=` markers that Stage 1 never writes. Phase 3 fixture (`test-run-stage2.sh`) happened to contain `at_ms=` lines so the test passed but the contract was never validated against real Stage 1 output. For this episode, patched `cut-list.md` by hand from `edl.json` cumulative range lengths. Tag `CONFIRM` — second episode confirms → PROMOTE: make `edl.json` the canonical seam-timestamp source for Stage 2; cut-list.md remains human-only.
- **transcript.duration_ms ≠ master.mp4 duration.** Compositor uses `transcript.duration_ms` (≈ raw recording length, 69909 ms) as `master_duration_ms`. Real `master.mp4` after EDL is ~52700 ms (ffprobe). Last seam in seam-plan.md ends past master end; harmless if host manually corrects `ends_at_ms` on the final seam at CP2.5. Tag `CONFIRM` — root cause: master duration should come from ffprobe on master.mp4 (or from EDL cumulative), not from transcript. Promote to PROMOTE on next episode → fix in compositor.
- **Editorial scene plan applied (8 scenes from 6 seams).** Sub-split WORKER and OFFLINE at meaning boundaries (Cloudflare Workers reveal; crypto/HW/time list). Custom mode map: HOOK=full, SETUP=head, WORKER-A=full, WORKER-B=overlay, CAVEAT=split, OFFLINE-A=full, OFFLINE-B=overlay, OUTRO=full. Default `pickScene` rotation produced different (mechanically-balanced) modes; editorial intent overrode. Tag `WATCH` — observe whether pickScene needs a "respect explicit mode hints" mechanism so we don't have to hand-edit seam-plan.md every episode.
- **OUTRO=overlay+subscribe rule established.** Host promoted: every episode's OUTRO scene is `overlay` with a subscribe call-to-action graphic. This pilot demoted OFFLINE-B from `overlay` to `split` to free the adjacent `overlay` slot for OUTRO (overlay>overlay forbidden by `seamPlanner.ts:5-12`). Tag `PROMOTE` — candidate for `standards/motion-graphics.md` (or wherever beat→scene rules live): rule "OUTRO scene must be overlay; if preceding scene is overlay, demote it to split". Future compositor: `pickScene` should know about beat→scene affinities or accept hints, eliminating manual seam-plan rewrites per episode.
- **Captions invisible: word timing field-name drift.** `caption-karaoke.html` filtered on `start_ms`/`end_ms`; ElevenLabs transcript uses `start`/`end` (seconds). `findIndex` always returned -1 → the caption layer rendered empty for the whole episode. Phase 3 caption fixture must have used `_ms` fields, masking this. Fixed in compositor: words normalized to `{text, start_ms, end_ms}` before serialization into `composition.html`; the component contract stays narrow. Tag `PROMOTE` — candidate `standards/captions.md` (or wherever caption rules live): "caption components consume `start_ms`/`end_ms`; compositor normalizes; component must not assume any other field naming." Plus follow-up: a Stage 1→Stage 2 transcript schema check (CP1.5) would have caught this and the earlier `duration_ms` and `at_ms=` drifts on the same run — three contract drifts on one episode is a strong signal that the gate is overdue.
- **Scene modes are label-only without `graphic:` specs.** `composer.ts:renderSeamFragment` only emits a clip when a seam carries `{component, data}`. Hand-written editorial seam-plans (CP2.5) naturally omit `graphic:` lines → no overlay/split/head visible content; `scene` becomes a decorative label. Pilot ran with no graphics; preview shows talking head + captions only. Tag `PROMOTE` (large) — Phase 5 work: define a `standards/motion-graphics.md` catalog `scene_mode → allowed_components` (e.g. `overlay → [lower-third, subscribe-cta]`, `split → [side-figure, code-block]`, `head → [name-plate]`, `full → [title-card, full-bleed-figure]`); extend the seam-plan format to allow per-mode default graphics OR require an editorial graphic spec on every non-`full` seam; add a compositor lint that warns when a `split`/`overlay`/`head` seam has no graphic. This is the single biggest gap surfaced by the pilot — without it, scene-mode editorial decisions don't survive to the screen.
- **Preview strategy reversal: workers+fps instead of resolution.** Original `--quality=low` shrunk root `data-width`/`data-height` to 720×1280, but inner `<video>` and absolute-positioned children stayed at 1440×2560 → the captured frame showed only the top-left corner of the layout (black + speaker bottom-right of crop). Replaced with `--workers N --fps N` (default 1 worker, 30 fps) at native 1440×2560. hyperframes' `-w/--workers` flag launches a separate Chrome process per worker (~256 MB RAM each per `--help`); 1 worker keeps RAM bounded at the cost of wall time. Tag `WATCH` — confirm on next episode that 1 worker + 30 fps preview is fast-enough-and-safe; promote to default if so. Long-term: the right way to "low-quality preview" is hyperframes-side downscale (DPR < 1) or a coordinated CSS `transform: scale` with paired layout adjustments — not data-attribute patching.

## Macro-retro

### Headline finding

The missing agentic graphics planner is THE core gap. The compositor is a renderer; the system was designed to have something — a coding agent dispatched in-pipeline — generate per-seam graphic specs (component + data) from spoken text + scene mode + standards catalog. That something does not exist. Without it, scene modes are decorative labels; preview/final shows talking head + captions only. Phase 5 must build it (decision: agentic, not LLM-API).

### Pattern: Stage 1 → Stage 2 contract drift (×5 in one episode)

Five drifts caught on this run:
1. transcript `audio_duration_secs` (sec) vs compositor `duration_ms` (ms).
2. `cut-list.md` `at_ms=` markers absent (Stage 1 emits human phrase ranges only).
3. `transcript.duration_ms` (~raw recording) vs `master.mp4` actual duration (post-EDL).
4. transcript word `start`/`end` (sec) vs caption-karaoke `start_ms`/`end_ms`.
5. transcript words in raw timeline vs master timeline after EDL gaps.

Root pattern: Stage 2 assumes master-aligned input; Stage 1 emits raw-aligned. Phase 3 fixtures masked all five because they were minimal and pre-aligned.

Recommended structural fix (Phase 5 candidate, not promoted today): either (a) Stage 1 normalizer step that emits a single `master/` directory with master-aligned transcript + `at_ms` boundaries derived from EDL, OR (b) explicit CP1.5 contract validator that asserts the shape Stage 2 expects, runnable as part of `run-stage1.sh`. Lean (a) — cheaper at runtime, single source of truth.

### Other architectural findings

- **Scene-mode naming confusion.** Compositor uses `head/split/full/overlay`; `standards/motion-graphics.md` uses (a)/(b)/(c)/(d) where `full` means head HIDDEN behind broll. Easy to misread `full` as "talking-head full frame" (which is actually `head`). Phase 5 candidate: rename modes in compositor to match standard's intent (e.g. `head/split/broll/overlay`) and lock with a typed enum so misuses fail at compose time.
- **Preview render strategy reversal.** Resolution shrinking (data-width/height patching) clipped content because inner absolute layout didn't scale. Replaced with `--workers N --fps N` at native 1440×2560. 1 worker + 30 fps preview = ~6 minutes wall on a dev box; survives without killing the system. Final-quality render not yet attempted on a real episode.
- **Per-iteration grade preview frames.** Captured at CP2 — extracting 2–3 PNGs after each Stage 1 render gave the agent a tight visual feedback loop for grade tuning. Worth automating into Stage 1.

### What did NOT ship for this episode

- No `final.mp4` render (skipped — no graphics → not publishable; render-final postponed to next episode after planner exists).
- No motion graphics in `composition.html` (no `graphic:` specs in seam-plan → `renderSeamFragment` emits nothing).
- No automated audio post-processing (manual chain applied for this pilot; pipeline integration is a known TODO).

### What worked

- Stage 1 grade chain (commit 67c1a66): converged in 3 iterations with the per-iteration frame extraction pattern.
- EDL editorial decision (CP1): clean — host took the aborted-restart-then-retake cut without protest.
- Subagent-driven development as orchestration model: nine subagents dispatched across this session, each fresh context, each committed when done.
- Test-first contract fixes: each Stage 1 ↔ Stage 2 drift was caught + fixed + locked with a unit test in the same subagent turn.

### Phase 5 candidate scope (not committed; for next planning session)

1. Build agentic graphics planner: dispatch a coding subagent per seam (or batched), input = spoken text + scene mode + standards excerpt + component catalog with data shapes; output = `graphic:` and `data:` lines patched into seam-plan.md. Validation layer: enforce transition matrix and per-component data shape at write time.
2. Stage 1 → Stage 2 contract normalization. Emit a single master-aligned bundle from Stage 1 (transcript + boundaries + duration). Stage 2 reads that one source instead of cross-referencing `edl.json` + `transcript.json` + `cut-list.md`.
3. Scene-mode rename + typed enum.
4. Pipeline-integrated audio post-processing (ElevenLabs Audio Isolation + 2-pass loudnorm).
5. Final-quality render survival (workers/fps tuning at 1440×2560 @ 60 fps).
6. Captions: ground-truth rewrite from `source/script.txt` when present (already noted at CP1 as WATCH).
7. Per-iteration grade preview frames automation (CP2 finding).
