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
