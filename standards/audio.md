# Audio standards

## Purpose
Voice levels, music handling, and final audio specification for shorts.

## Voice
- Target loudness: −16 LUFS integrated, true peak < −1 dBTP.
- video-use applies 30 ms audio fades at every cut to avoid pops. Do not disable.
- Voice cleanup (denoise / dereverb) handled by video-use's audio stage. If output still has audible noise, log in `retro.md`.

## Music
- Music plays at a flat background level for the entire duration of the video.
- **No ducking by default.** Ducking only when the user explicitly requests it for a specific episode.
- Music level: −22 LUFS (integrated), 6 dB below voice.
- Music file lives only in `library/music/`. Never duplicate into episode folders. Episodes reference it via the `music:` field in `meta.yaml`.

## Final mix
- AAC 320 kbps, 48 kHz, stereo.
- Voice on both channels (mono summed). Music stereo unchanged.
- Final mix happens in `tools/scripts/render-final.sh` via ffmpeg `amix` with weights tuned to the levels above.

## Hard rules
- Music level is constant across the full video unless ducking is explicitly requested.
- Voice never exceeds −1 dBTP true peak.
- No music file ever lives outside `library/music/`.
