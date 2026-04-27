# Anticodeguy Video Editing Studio — Design

**Date:** 2026-04-27
**Status:** Approved design (pending final user review of this document)
**Owner:** Anticodeguy

## Goal

A repo that turns raw talking-head footage into polished vertical YouTube/TikTok shorts (1–3 min, 9:16, English) through an agent-driven, checkpoint-gated pipeline. Two external tools do the heavy lifting: **video-use** for transcript-driven cutting, audio cleanup, and color grading; **HyperFrames** for HTML-rendered captions, motion graphics, and split-screens. The system learns from every episode through a retrospective loop that feeds long-lived standards.

## Constraints

- Output: 9:16, 1440×2560, 60 fps, H.264 high profile, ~35 Mbps VBR (1-pass), Rec.709 SDR (gamma 2.4). Audio: AAC 320 kbps, 48 kHz stereo. EN captions, English brand assets.
- Source footage must be delivered in Rec.709 SDR. HDR/HLG sources are rejected at ingest; HDR support is a deferred separate track.
- All repo content (code, docs, standards, retros, file names, commit messages) is English.
- Chat communication with the user is Russian.
- No video brand identity yet — `design-system/` ships with placeholder iOS-18 frosted-glass tokens; later rebrand = swap `tokens.json` only.
- Pipeline runs in checkpoint mode initially. Autonomous mode is a later switch, not a near-term goal.
- ElevenLabs Scribe API is mandatory (used by video-use). User has Creator-tier subscription.

## Architecture: two-stage pipeline

Stage 1 — **video-use** — produces a post-production-ready visual master from raw footage: transcription, cut-list, cuts, 30 ms audio fades, auto color grade, vignette/contrast adjustments. Output is `master.mp4`: the talking-head as it should look in the final video, but with **no captions, no overlays, no music**.

Stage 2 — **HyperFrames-based compositor** (own code in `tools/compositor/`) — generates an HTML composition layered over `master.mp4`: per-word karaoke captions, motion-graphics overlays, split-screen frames, full-screen B-roll. Renders deterministically through HyperFrames, then ffmpeg-merges the result with the user-supplied music track.

Reasoning for two stages instead of letting video-use do everything: video-use's default captions (2-word UPPERCASE chunks) and overlay system (Manim/Remotion/PIL) don't fit the desired iOS frosted-glass aesthetic and karaoke caption style. Splitting at `master.mp4` gives a clean visual review checkpoint and full control over the visual layer without fighting video-use's defaults.

## Repository structure

```
anticodeguy-video-editing-studio/
├── AGENTS.md                      # Master agent contract, English-only, loaded each session
├── README.md
├── .gitignore
├── .env.example                   # ELEVENLABS_API_KEY=
│
├── standards/                     # Long-lived rules, evolved through retro loop
│   ├── editing.md                 # cut philosophy, pacing, seam handling
│   ├── captions.md                # typography, position, karaoke timing
│   ├── motion-graphics.md         # 4-scene system, transition matrix
│   ├── audio.md                   # voice levels, music flat-background, no duck by default
│   ├── color.md                   # video-use grade settings, vignette, contrast
│   └── retro-changelog.md         # append-only history of standards changes
│
├── design-system/                 # Reusable HyperFrames building blocks
│   ├── tokens/tokens.json         # placeholder iOS frosted-glass tokens
│   ├── components/                # caption-karaoke, glass-card, split-frame,
│   │                              #   fullscreen-broll, overlay-plate, title-card
│   └── README.md                  # placeholder brand brief
│
├── library/
│   └── music/                     # royalty-free tracks, single source of truth
│
├── tools/
│   ├── video-use/                 # vendored clone of browser-use/video-use (gitignored)
│   ├── compositor/                # own code: seam-plan → composition.html → render
│   └── scripts/                   # new-episode, run-stage1, run-stage2,
│                                  #   render-final, retro-promote
│
├── incoming/                      # User drops raw.mp4 + optional notes.md here
│
├── docs/superpowers/specs/        # Specs, including this document
│
└── episodes/
    └── YYYY-MM-DD-slug/
        ├── source/raw.mp4         # gitignored
        ├── meta.yaml              # title, slug, duration, tags, music: <library path>
        ├── stage-1-cut/
        │   ├── project.md         # video-use session memory
        │   ├── transcript.json
        │   ├── cut-list.md        # ← CP1 artifact
        │   └── master.mp4         # ← CP2 artifact (gitignored)
        ├── stage-2-composite/
        │   ├── seam-plan.md       # ← CP2.5 artifact
        │   ├── composition.html
        │   ├── preview.mp4        # ← CP3 artifact (gitignored)
        │   └── final.mp4          # final output (gitignored)
        └── retro.md               # episode observations + proposed standard changes
```

Music never duplicates into episodes; `meta.yaml` references `library/music/<filename>.mp3` by relative path.

## Pipeline stages and checkpoints

```
incoming/  ──► new-episode.sh ──►  episodes/<slug>/source/raw.mp4 + meta.yaml
                                            │
                                            ▼
   ┌─────────────────────── Stage 1 (video-use) ─────────────────────────┐
   │  1.1  ElevenLabs Scribe transcription → transcript.json              │
   │  1.2  Cut analysis (silence, fillers, mistakes) → cut-list.md        │
   │  ─────────────────  CP1: cut-list review  ────────────────────────── │
   │  1.3  Apply cuts + 30 ms audio fades + auto color grade + vignette   │
   │  1.4  Write master.mp4  (post-prod-ready talking-head, no overlays)  │
   │  ─────────────────  CP2: visual master review  ────────────────────  │
   └──────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
   ┌──────────────────── Stage 2 (compositor + HyperFrames) ─────────────┐
   │  2.1  Build seam-plan.md from transcript + cut-list:                 │
   │         per-seam scene choice (a/b/c/d) + graphic content            │
   │  ─────────────────  CP2.5: seam-plan review  ──────────────────────  │
   │  2.2  Generate composition.html → npx hyperframes preview → preview.mp4 │
   │  ─────────────────  CP3: preview review  ──────────────────────────  │
   │  2.3  npx hyperframes render → composite + ffmpeg merge with music   │
   │       → final.mp4                                                    │
   └──────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
                       retro.md ──► macro-retro ──► standards/ + retro-changelog.md
```

Between checkpoints the agent runs autonomously. At each checkpoint it posts `CP<N> ready: <artifact path>. Awaiting review.` and stops until the user says `go` or supplies edits. Edits → re-run → re-checkpoint. Loop until `go`.

## Scene system and seam transitions

Every cut in `master.mp4` is a "seam." The compositor decides which of four scenes runs on each side of every seam:

- **(a) plain talking-head** — head at full frame, no overlay
- **(b) split-screen** — head reduced, frosted-glass graphic alongside
- **(c) full-screen B-roll** — head hidden, motion-graphics fills frame
- **(d) talking-head + overlay** — head at full frame, frosted-glass info-plate floating over it

**Core rule:** across each seam, the talking-head must visibly **shrink, disappear, or return from a smaller/hidden state**. If the head stays full-frame on both sides of the seam, the cut is exposed regardless of any overlay.

**Transition matrix:**

| from ↓ \ to → | (a) head | (b) split | (c) full | (d) head+overlay |
|---|---|---|---|---|
| (a) head             | ✗ | ✓ | ✓ | ✗ |
| (b) split            | ✓ | ✓ if different graphic | ✓ | ✓ |
| (c) full             | ✓ | ✓ | ✓ if different graphic | ✓ |
| (d) head+overlay     | ✗ | ✓ | ✓ | ✗ |

**Scene length** is bounded by phrase boundaries, not arbitrary timers. A scene runs from one seam to the next regardless of duration.

## Captions

- Style: pure typography. No background plate, no glass — captions never sit on frosted glass.
- Single line, ≤3 words on screen at once.
- Per-word karaoke highlight: active word in `tokens.color.caption.active`, surrounding words in `tokens.color.caption.inactive`.
- Baseline raised above the platform safe zone (`tokens.safezone.bottom`, default 22% from bottom) so TikTok/YouTube UI overlays never cover them.
- Always rendered on top, independent of scene mode.

## Audio

- Voice level normalization handled by video-use during stage 1.
- Music: flat background level for the full duration of the video. **No ducking by default.** Ducking only on explicit user request per episode.
- Music file lives only in `library/music/`; episodes reference it via `meta.yaml`.

## Color

- Stage 1 produces a visually finished talking-head. Stage 2 never touches color.
- Default approach: trust video-use auto-grade. If insufficient (low contrast, no vignette), add a stage-1.5 ffmpeg pass with parameters defined in `standards/color.md`.
- No Premiere Pro pre-pass.

## Retro / feedback loop

- **Micro-retro** runs after each checkpoint that received user edits. The agent appends 2–3 lines to `episodes/<slug>/retro.md`: what was proposed → what user changed → why (if known). One observation per change, plus one proposed standards rule.
- **Macro-retro** runs after CP3 final acceptance. The agent reviews the full `retro.md`, groups patterns, and produces a list of proposed standard changes tagged `WATCH`, `CONFIRM`, or `PROMOTE`.
- The user reviews the macro-retro list and selects which proposals to promote. This is effectively a fourth checkpoint.
- Promoted changes update `standards/*.md` and append an entry to `standards/retro-changelog.md` (date, file, change, source episode, reason).
- A proposal needs at least one confirmation across two episodes (or an explicit `PROMOTE` from the user) before reaching `standards/`.
- **Removal:** outdated rules are deleted from `standards/` outright. The deletion is logged in `retro-changelog.md` with reason; old rule text is not archived.

`retro.md` discipline: record only **deltas** between proposed and accepted, not narrative summaries of the episode.

## AGENTS.md outline

The agent contract is English-only and lives at the repo root. Sections (in order):

- TL;DR — one paragraph: what to do, where input comes from, where output goes, checkpoint mode.
- Inputs — what shows up in `incoming/` and `meta.yaml`.
- Pipeline — numbered stages with file paths and checkpoint markers.
- Standards — list of `standards/*.md` files with one-line purpose each; "load before doing the corresponding stage."
- Checkpoint protocol — the stop-and-wait contract.
- Retro discipline — what `retro.md` is and is not.
- Hard rules — non-negotiable invariants:
  - Do not edit `standards/` without explicit user `PROMOTE` in macro-retro.
  - Do not edit `retro-changelog.md`; append-only.
  - Do not duplicate music files into episodes; always reference `library/music/`.
  - Do not skip a checkpoint. A checkpoint without stop is a bug.
  - Do not produce seams with disallowed transitions (`a↔a`, `a↔d`, `d↔d`, same-graphic `b→b`/`c→c`).
  - English in repo, Russian in chat — without exception.
  - `final.mp4` = 9:16, captions per `standards/captions.md`, music flat unless ducking explicitly requested.
- Communication — English in all repo artifacts; Russian in all chat replies and checkpoint summaries.
- Tooling commands — exact invocations for video-use, hyperframes, scripts.
- File-location quick map — sources, music, brand tokens, components, episodes, standards.
- Environment — required env vars and tool versions.

If `AGENTS.md` ever exceeds ~200 lines, the surplus migrates into `standards/` and `AGENTS.md` keeps only references.

## Design system

Placeholder, swap-out-ready. All visual values flow from one file.

- `design-system/tokens/tokens.json` defines color (glass, text, caption, accent), typography family/weight/size, blur radii, corner radii, spacing, safe-zone percentages, and video format constants (1440×2560, 60 fps, Rec.709 SDR).
- `design-system/components/` ships six starter HTML templates with data-attribute slots: `caption-karaoke`, `glass-card`, `split-frame`, `fullscreen-broll`, `overlay-plate`, `title-card`. All read tokens via CSS variables. None hardcode color, size, or blur values.
- `design-system/README.md` is a placeholder brand brief stating that current tokens are working defaults inspired by iOS 18 frosted-glass and not final brand decisions.
- Future rebrand procedure: update `tokens.json`. That's it.

## Setup and bootstrap order

ffmpeg, Node 20+, Python 3.11+ with uv, and Git are already installed on the user's system. Bootstrap step 0 is a verification pass (`ffmpeg -version`, `node --version`, `python --version`, `uv --version`, `git --version`) — installation is only triggered if a check fails.

Bootstrap sequence:

0. Verify required tools are installed and report versions.
1. `git init`, `.gitignore`, `README.md`, `.env.example`, base folder skeleton.
2. `AGENTS.md`.
3. Initial `standards/*.md` capturing all rules from this design.
4. `design-system/tokens/tokens.json` and placeholder `design-system/README.md`.
5. `tools/scripts/new-episode.sh` (minimal: creates episode skeleton).
6. Clone `video-use` into `tools/video-use/`, run `uv sync`, populate `.env` with ElevenLabs key.
7. HyperFrames smoke test: `npx hyperframes init` in a sandbox, render demo to confirm working CLI.
8. `design-system/components/*.html` — six starter components, each rendered standalone via HyperFrames preview as a self-test.
9. `tools/compositor/` — generator from `seam-plan.md` + `transcript.json` to `composition.html`.
10. `tools/scripts/run-stage1.sh`, `run-stage2.sh`, `render-final.sh`, `retro-promote.sh`.
11. First real episode end-to-end on actual user footage. First real `retro.md`.

Steps 1–5 have no external dependencies. Steps 6–7 require user's ElevenLabs API key. Step 11 is the integration test for the whole system.

## Gitignore policy

Heavy media stays out of git: `raw.mp4`, `master.mp4`, `preview.mp4`, `final.mp4`, anything under `incoming/`, `library/music/*.mp3`, `tools/video-use/`, `node_modules/`, `.venv/`, `.env`. Repo tracks code, standards, specs, retros, metadata, design system, and component templates only. Music versioning via Git LFS is deferred — revisit if the library grows or the user wants reproducible track history.

## Open items deferred past this spec

- Final brand identity and design system values.
- Autonomous mode (no checkpoints) — switched on once standards stabilize across multiple episodes.
- Horizontal-format support — currently shorts only.
- Music library versioning strategy (LFS vs external store).
- Whether `library/music/` itself should be committed (currently gitignored).
- HDR/HLG pipeline as a separate compositor track. Out of scope for the SDR-only first version.
