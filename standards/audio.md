# Audio standards

## Purpose
Voice levels, music handling, and final audio specification for shorts.

## Voice
- Target loudness: −14 LUFS integrated, true peak < −1 dBTP.
- video-use applies 30 ms audio fades at every cut to avoid pops. Do not disable.
- Voice cleanup (denoise / dereverb) handled by video-use's audio stage. If output still has audible noise, log in `retro.md`.

## Music
- Music plays at a flat background level for the entire duration of the video.
- **No ducking by default.** Ducking only when the user explicitly requests it for a specific episode.
- Music level: −20 LUFS (integrated), 6 dB below voice.
- Music file lives only in `library/music/`. Never duplicate into episode folders. Episodes reference it via the `music:` field in `meta.yaml`.

## Final mix
- AAC 320 kbps, 48 kHz, stereo.
- Voice on both channels (mono summed). Music stereo unchanged.
- Final mix is produced natively by HyperFrames in `render-final.sh`. See **Mixing implementation** section below for details. ffmpeg is no longer used for Stage 2 audio mixing.

## Hard rules
- Music level is constant across the full video unless ducking is explicitly requested.
- Voice never exceeds −1 dBTP true peak.
- No music file is committed into episode folders. `run-stage2-compose.sh` copies from `library/music/` into `stage-2-composite/assets/` at compose time (gitignored). `library/music/` is the authoritative source.

## Promoted 2026-04-27
- loudnorm-mode two-pass-with-measured (episode 2026-04-27-desktop-software-licensing-it-turns-out; single-pass introduces 2-3s PTS desync at start)

## Promoted 2026-04-27
- no-fades hard-cuts (episode 2026-04-27-desktop-software-licensing-it-turns-out; host preference; video-use fade injection bypassed by direct ffmpeg render anyway)

## Mixing implementation (post 6a-aftermath)

HF renders the final audio mix natively. Voice and music are emitted as separate `<audio>` clips inside the root `index.html` with `data-volume` attributes:

- Voice (master.mp4 audio track): `data-volume="1"` — full level.
- Music (music.<ext> from library/music/): `data-volume="0.5"` — ducked ~6 dB below voice.

No `loudnorm` step is applied during render. Tracks placed in `library/music/` MUST be professionally pre-mastered (target loudness around -16 to -20 LUFS). If a candidate track is too loud or unmastered, master it once during library curation, not per-episode.
