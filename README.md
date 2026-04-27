# Anticodeguy Video Editing Studio

Agent-driven pipeline that turns raw talking-head footage into polished
vertical YouTube/TikTok shorts (1440×2560, 60 fps, Rec.709 SDR, EN).

## Quickstart for new agent sessions
1. Read `AGENTS.md` end-to-end.
2. Read the relevant standards in `standards/` for the stage you are working on.
3. Look in `incoming/` for new raw footage. If found, run `tools/scripts/new-episode.sh <slug>`.
4. Operate in checkpoint mode. Stop and wait for user approval at every checkpoint.

## Design
The full design lives at `docs/superpowers/specs/2026-04-27-video-editing-studio-design.md`.

## Setup
1. Copy `.env.example` to `.env` and fill in `ELEVENLABS_API_KEY`.
2. Run `tools/scripts/check-deps.sh` to verify all required tools are installed.
3. Phase-specific setup (video-use, HyperFrames) lives in their respective phase plans.

## Communication
Repo content is English. Chat communication with the user is Russian.
