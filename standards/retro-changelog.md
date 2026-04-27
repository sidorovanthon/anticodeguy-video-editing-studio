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
