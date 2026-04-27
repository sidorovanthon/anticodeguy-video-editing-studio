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
