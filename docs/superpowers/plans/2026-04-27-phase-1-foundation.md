# Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up the empty repo as a tracked, navigable project with all long-lived rules, agent contract, design tokens, dependency checks, and the `new-episode.sh` script that creates a valid episode skeleton.

**Architecture:** Pure scaffolding. No external tools yet — only filesystem layout, markdown standards, JSON tokens, two shell scripts. All work is local; no network calls.

**Tech Stack:** Bash (POSIX), JSON, Markdown, Git. Spec at `docs/superpowers/specs/2026-04-27-video-editing-studio-design.md`.

---

## File structure produced by this phase

```
.gitignore
.env.example
README.md
AGENTS.md
docs/superpowers/specs/2026-04-27-video-editing-studio-design.md   (already exists)
standards/editing.md
standards/captions.md
standards/motion-graphics.md
standards/audio.md
standards/color.md
standards/retro-changelog.md
design-system/tokens/tokens.json
design-system/README.md
design-system/components/.gitkeep
library/music/.gitkeep
incoming/.gitkeep
episodes/.gitkeep
tools/scripts/check-deps.sh
tools/scripts/new-episode.sh
tools/scripts/test/test-new-episode.sh
```

---

### Task 1: Initialize git and write `.gitignore`

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Initialize git repository**

```bash
cd /c/Users/sidor/repos/anticodeguy-video-editing-studio
git init -b main
```

Expected: `Initialized empty Git repository in .../anticodeguy-video-editing-studio/.git/`

- [ ] **Step 2: Write `.gitignore`**

```
# Secrets
.env

# Tool installs
tools/video-use/
node_modules/
.venv/
__pycache__/
*.pyc

# Heavy media — kept out of repo
incoming/*
!incoming/.gitkeep

library/music/*
!library/music/.gitkeep

episodes/*/source/*
!episodes/*/source/.gitkeep
episodes/*/stage-1-cut/master.mp4
episodes/*/stage-1-cut/transcript.json
episodes/*/stage-2-composite/preview.mp4
episodes/*/stage-2-composite/final.mp4

# OS / editor
.DS_Store
Thumbs.db
.vscode/
.idea/
```

- [ ] **Step 3: Verify**

```bash
test -f .gitignore && echo OK
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore: initial gitignore"
```

---

### Task 2: Write `.env.example` and `README.md`

**Files:**
- Create: `.env.example`
- Create: `README.md`

- [ ] **Step 1: Write `.env.example`**

```
# ElevenLabs Scribe API key — required by video-use for transcription.
# Plan must be Creator tier or higher.
ELEVENLABS_API_KEY=
```

- [ ] **Step 2: Write `README.md`**

```markdown
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
```

- [ ] **Step 3: Verify**

```bash
test -f .env.example && test -f README.md && echo OK
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add .env.example README.md
git commit -m "docs: add README and env template"
```

---

### Task 3: Create directory skeleton with `.gitkeep` markers

**Files:**
- Create: `standards/.gitkeep`, `library/music/.gitkeep`, `incoming/.gitkeep`, `episodes/.gitkeep`, `design-system/components/.gitkeep`, `design-system/tokens/.gitkeep`, `tools/scripts/.gitkeep`, `tools/scripts/test/.gitkeep`

- [ ] **Step 1: Create directories and gitkeep files**

```bash
mkdir -p standards library/music incoming episodes
mkdir -p design-system/tokens design-system/components
mkdir -p tools/scripts/test tools/compositor

touch standards/.gitkeep library/music/.gitkeep incoming/.gitkeep episodes/.gitkeep
touch design-system/tokens/.gitkeep design-system/components/.gitkeep
touch tools/scripts/.gitkeep tools/scripts/test/.gitkeep tools/compositor/.gitkeep
```

- [ ] **Step 2: Verify**

```bash
ls standards library incoming episodes design-system/tokens design-system/components tools/scripts tools/compositor
```

Expected: each directory listed without errors.

- [ ] **Step 3: Commit**

```bash
git add standards library incoming episodes design-system tools
git commit -m "chore: scaffold directory layout"
```

---

### Task 4: Move existing spec into git tracking

The spec already exists at `docs/superpowers/specs/2026-04-27-video-editing-studio-design.md` from the brainstorming session. Add it to the first commit that includes design content.

- [ ] **Step 1: Verify file exists**

```bash
test -f docs/superpowers/specs/2026-04-27-video-editing-studio-design.md && echo OK
```

Expected: `OK`

- [ ] **Step 2: Commit**

```bash
git add docs/
git commit -m "docs: design spec for video editing studio"
```

---

### Task 5: Write `tools/scripts/check-deps.sh`

**Files:**
- Create: `tools/scripts/check-deps.sh`
- Create: `tools/scripts/test/test-check-deps.sh`

- [ ] **Step 1: Write failing test**

`tools/scripts/test/test-check-deps.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK="$SCRIPT_DIR/../check-deps.sh"

if [ ! -x "$CHECK" ]; then
  echo "FAIL: $CHECK is not executable"
  exit 1
fi

OUTPUT="$("$CHECK" 2>&1)" || { echo "FAIL: check-deps exited non-zero"; echo "$OUTPUT"; exit 1; }

for tool in ffmpeg node python uv git; do
  if ! echo "$OUTPUT" | grep -q "$tool"; then
    echo "FAIL: $tool not reported in output"
    echo "$OUTPUT"
    exit 1
  fi
done

echo "OK: check-deps reports all required tools"
```

- [ ] **Step 2: Run test, expect failure**

```bash
chmod +x tools/scripts/test/test-check-deps.sh
tools/scripts/test/test-check-deps.sh
```

Expected: `FAIL: ... check-deps.sh is not executable` (script doesn't exist yet).

- [ ] **Step 3: Write `check-deps.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

# Verify all tools required by the pipeline are installed and report versions.
# Exit non-zero if any tool is missing.

declare -A REQUIRED=(
  [ffmpeg]="ffmpeg -version | head -n1"
  [node]="node --version"
  [python]="python --version"
  [uv]="uv --version"
  [git]="git --version"
)

MISSING=()
for tool in "${!REQUIRED[@]}"; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    MISSING+=("$tool")
    echo "MISSING $tool"
  else
    VER="$(eval "${REQUIRED[$tool]}" 2>&1 | head -n1)"
    echo "OK      $tool — $VER"
  fi
done

if [ "${#MISSING[@]}" -gt 0 ]; then
  echo
  echo "Missing tools: ${MISSING[*]}"
  exit 1
fi
```

- [ ] **Step 4: Make executable, run test, expect pass**

```bash
chmod +x tools/scripts/check-deps.sh
tools/scripts/test/test-check-deps.sh
```

Expected: `OK: check-deps reports all required tools`.

- [ ] **Step 5: Run check-deps directly to capture environment baseline**

```bash
tools/scripts/check-deps.sh
```

Expected: 5 `OK` lines (ffmpeg, node, python, uv, git) with versions.

- [ ] **Step 6: Commit**

```bash
git add tools/scripts/check-deps.sh tools/scripts/test/test-check-deps.sh
git commit -m "feat: add dependency checker script"
```

---

### Task 6: Write `standards/editing.md`

**Files:**
- Create: `standards/editing.md`

- [ ] **Step 1: Write the file**

```markdown
# Editing standards

## Purpose
Defines what to cut, what to keep, and the philosophy behind pacing for shorts.

## Pacing target
- Shorts run 1–3 minutes total. Aim for high density — every second earns its place.
- Remove silences > 250 ms unless they sit on a deliberate rhetorical pause.
- Remove filler words ("um", "uh", "you know", "like" used as filler) unless they precede a deliberate beat.
- Remove stumbles, restarts, and aborted sentences. Keep only the take that the speaker repeated successfully.

## Cut detection responsibility
- video-use produces the initial `cut-list.md`. The agent does not invent cuts outside what video-use proposes.
- The agent may *suppress* cuts (mark "keep") that video-use proposed if a rule below applies.

## Always-keep rules
- Pause > 300 ms when followed by a tonal shift (drop or rise) — likely deliberate.
- Filler word "you know" when followed by a question form — usually rhetorical.
- The very first 200 ms after the speaker takes a breath at start of a phrase.

## Always-cut rules
- Repeated word at phrase start ("the the", "I I") — keep the second instance.
- Restart of a sentence ("So I — so I think") — keep only the final attempt.
- Audible breath cluster > 400 ms with no speech.

## Seam handling
The visual seam handling rules live in `standards/motion-graphics.md`. This file only governs which cuts to make, not how to mask them.
```

- [ ] **Step 2: Commit**

```bash
git add standards/editing.md
git commit -m "docs(standards): editing rules"
```

---

### Task 7: Write `standards/captions.md`

**Files:**
- Create: `standards/captions.md`

- [ ] **Step 1: Write the file**

```markdown
# Caption standards

## Purpose
Typography and timing rules for per-word karaoke captions burned into the final video.

## Style
- Pure typography. **No background plate, no glass surface, no drop shadow** — captions never sit on glass.
- Single line on screen at any moment. **Maximum 3 words visible at once.**
- Per-word karaoke: the active word renders in `tokens.color.caption.active`; surrounding (already-spoken or upcoming) words in `tokens.color.caption.inactive`.

## Layout
- Baseline position: `tokens.safezone.bottom` (default 22% of frame height from bottom).
- Horizontal centering, no left-aligned captions.
- Font: `tokens.type.family.caption`. Weight: `tokens.type.weight.bold` for active, `regular` for inactive.
- Size: `tokens.type.size.caption`.

## Timing
- Word visibility window starts at the word's `start_ms` from `transcript.json` and ends at `end_ms`.
- Active-word highlight duration matches `[start_ms, end_ms]` of that word.
- The visible 3-word window slides forward word-by-word; never wraps to a second line.

## Hard rules
- Never sit on a glass surface or any motion-graphics element.
- Never wrap to two lines.
- Never go below the safe-zone baseline.
- Never display more than 3 words simultaneously.
```

- [ ] **Step 2: Commit**

```bash
git add standards/captions.md
git commit -m "docs(standards): caption rules"
```

---

### Task 8: Write `standards/motion-graphics.md`

**Files:**
- Create: `standards/motion-graphics.md`

- [ ] **Step 1: Write the file**

```markdown
# Motion graphics standards

## Purpose
The four-scene system, transition matrix at seams, and visual language for motion graphics overlays.

## Scenes
- **(a) plain talking-head** — head fills frame, no overlay.
- **(b) split-screen** — head reduced to one half, frosted-glass graphic on the other.
- **(c) full-screen B-roll** — head hidden, motion graphics fills the frame.
- **(d) talking-head + overlay** — head fills frame, frosted-glass info plate floats over it.

## Core rule
Across each seam, the talking-head must visibly **shrink, disappear, or return from a smaller/hidden state**. If the head stays full-frame on both sides of the seam, the cut is exposed regardless of overlay content.

## Transition matrix

|  from \ to    | (a) head | (b) split | (c) full | (d) head+overlay |
|---|---|---|---|---|
| (a) head             | ✗ | ✓ | ✓ | ✗ |
| (b) split            | ✓ | ✓ if different graphic | ✓ | ✓ |
| (c) full             | ✓ | ✓ | ✓ if different graphic | ✓ |
| (d) head+overlay     | ✗ | ✓ | ✓ | ✗ |

Forbidden transitions: `a↔a`, `a↔d`, `d↔d`, same-graphic `b→b`, same-graphic `c→c`.

## Scene length
Bounded by phrase boundaries, not arbitrary timers. A scene runs from one seam to the next regardless of resulting duration.

## Visual language
- Frosted glass surfaces use `tokens.color.glass.fill`, `tokens.blur.*`, `tokens.color.glass.stroke`, `tokens.color.glass.shadow`.
- Corners use `tokens.radius.*`.
- Padding inside glass surfaces: at least `tokens.spacing.md`.
- Captions never sit on these surfaces — see `standards/captions.md`.

## Hard rules
- Every seam must produce a scene transition that satisfies the matrix.
- Scene-mode metadata travels in `seam-plan.md`, one entry per seam.
- Components live in `design-system/components/`. Never inline raw HTML in `composition.html` — always reference a component template.
- All component styling reads from `design-system/tokens/tokens.json` via CSS variables. No hardcoded color/size/blur values.
```

- [ ] **Step 2: Commit**

```bash
git add standards/motion-graphics.md
git commit -m "docs(standards): motion graphics rules"
```

---

### Task 9: Write `standards/audio.md`

**Files:**
- Create: `standards/audio.md`

- [ ] **Step 1: Write the file**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add standards/audio.md
git commit -m "docs(standards): audio rules"
```

---

### Task 10: Write `standards/color.md`

**Files:**
- Create: `standards/color.md`

- [ ] **Step 1: Write the file**

```markdown
# Color standards

## Purpose
Color grading parameters for stage 1, plus what we reject at ingest.

## Source format requirements
Source footage in `incoming/raw.mp4` must be:
- Container: MP4 / MOV
- Codec: H.264 or H.265
- Color space: **Rec.709 SDR (gamma 2.4)**. HDR/HLG sources are rejected at ingest.
- Resolution: at least 1440×2560 (higher OK; downscaled at output).
- Frame rate: 60 fps preferred; 30 fps acceptable (output upsampled to 60 fps with frame doubling — log warning in retro).

## Stage 1 grade (applied by video-use)
Defaults below are starting values. Adjust through retro loop.

- Auto color grading: enabled.
- Saturation bump: +8%.
- Contrast: +12 (Premiere-style scale).
- Vignette: intensity 0.25, feather 0.6, midpoint 0.5.
- Sharpening: disabled (already crisp from source).

If video-use's auto grade does not yield the above, an additional `stage-1.5` ffmpeg pass with explicit `eq` and `vignette` filters is added. The pass parameters live in `tools/compositor/grade.json` (created in Phase 2).

## Output format (set in compositor + render-final.sh)
- Resolution: 1440×2560
- Frame rate: 60 fps
- Codec: H.264 high profile, level 5.1
- Bitrate: ~35 Mbps VBR (1-pass)
- Color: Rec.709 SDR (gamma 2.4)

## Hard rules
- No HDR/HLG source accepted. Reject at `new-episode.sh` with clear error.
- Final `final.mp4` must validate as 1440×2560, 60 fps, Rec.709, AAC 320k 48kHz before declaring CP3 done.
```

- [ ] **Step 2: Commit**

```bash
git add standards/color.md
git commit -m "docs(standards): color rules"
```

---

### Task 11: Initialize `standards/retro-changelog.md`

**Files:**
- Create: `standards/retro-changelog.md`

- [ ] **Step 1: Write seed entry**

```markdown
# Standards changelog

Append-only history of every change to `standards/*.md` files.
Format: each entry shows date, file, change, source episode (or "bootstrap"), reason.

Never edit existing entries. To revoke a rule, append a new entry that removes it with reason.

---

## 2026-04-27 — bootstrap
- Created standards/editing.md, captions.md, motion-graphics.md, audio.md, color.md, retro-changelog.md.
- Source: docs/superpowers/specs/2026-04-27-video-editing-studio-design.md.
- Reason: project bootstrap; rules captured during brainstorming session.
```

- [ ] **Step 2: Commit**

```bash
git add standards/retro-changelog.md
git commit -m "docs(standards): seed retro changelog"
```

---

### Task 12: Write `design-system/tokens/tokens.json`

**Files:**
- Create: `design-system/tokens/tokens.json`

- [ ] **Step 1: Write the file**

```json
{
  "color": {
    "bg":    { "transparent": "rgba(0,0,0,0)" },
    "glass": {
      "fill":   "rgba(255,255,255,0.18)",
      "stroke": "rgba(255,255,255,0.32)",
      "shadow": "rgba(0,0,0,0.35)"
    },
    "text": {
      "primary":   "#FFFFFF",
      "secondary": "rgba(255,255,255,0.72)",
      "accent":    "#7CC4FF"
    },
    "caption": {
      "active":   "#FFFFFF",
      "inactive": "rgba(255,255,255,0.55)"
    }
  },
  "type": {
    "family": {
      "caption": "'Inter', system-ui, sans-serif",
      "display": "'Inter Display', 'Inter', sans-serif"
    },
    "weight": { "regular": 500, "bold": 700, "black": 900 },
    "size":   { "caption": "64px", "title": "96px", "body": "44px" }
  },
  "blur":    { "glass-sm": "16px", "glass-md": "24px", "glass-lg": "40px" },
  "radius":  { "sm": "16px", "md": "28px", "lg": "44px", "pill": "9999px" },
  "spacing": { "xs": "8px", "sm": "16px", "md": "24px", "lg": "40px", "xl": "64px" },
  "safezone":{ "top": "8%", "bottom": "22%", "side": "6%" },
  "video":   { "width": 1440, "height": 2560, "fps": 60, "color": "rec709-sdr" }
}
```

- [ ] **Step 2: Validate JSON**

```bash
python -c "import json; json.load(open('design-system/tokens/tokens.json'))" && echo OK
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add design-system/tokens/tokens.json
git commit -m "feat(design-system): placeholder tokens"
```

---

### Task 13: Write `design-system/README.md`

**Files:**
- Create: `design-system/README.md`

- [ ] **Step 1: Write the file**

```markdown
# Design system

Status: **PLACEHOLDER**. Visual brand to be designed later. Current values
are working defaults inspired by iOS 18 frosted-glass aesthetic. Do not
treat current tokens as final brand decisions.

## Aesthetic direction (working)
- iOS 18 frosted-glass / liquid-glass surfaces.
- High contrast, white-dominant typography over colorful backdrops.
- Soft shadows, generous radii, ample padding.
- Captions are pure typography — no glass behind, no drop-shadow.

## Layout
- `tokens/tokens.json` — single source of truth for all visual values.
- `components/` — reusable HTML templates (added in Phase 3).

## When the brand is finalized
1. Update `tokens/tokens.json`. That is the only file you should need to touch.
2. Components must read tokens through CSS variables. They never hardcode color, size, or blur.
3. `standards/captions.md` and `standards/motion-graphics.md` may reference token *names* but never their *values*.
```

- [ ] **Step 2: Commit**

```bash
git add design-system/README.md
git commit -m "docs(design-system): placeholder brand brief"
```

---

### Task 14: Write `AGENTS.md`

**Files:**
- Create: `AGENTS.md`

- [ ] **Step 1: Write the file**

```markdown
# AGENTS.md — Anticodeguy Video Editing Studio

## TL;DR
You edit YouTube/TikTok shorts (1–3 min, 9:16, EN). Raw footage arrives in `incoming/`.
Final output is `episodes/<slug>/stage-2-composite/final.mp4`. The pipeline runs in
**checkpoint mode** — between checkpoints you work autonomously; on a checkpoint you
stop and wait for explicit user approval.

## Inputs you can expect
- `incoming/raw.mp4` — talking-head footage, English, scripted, with mistakes and pauses.
- `incoming/notes.md` (optional) — episode topic, do-not-cut spans, special instructions.
- A music file already present in `library/music/`. Episode `meta.yaml` will reference it.

## Pipeline (read in order)
1. **new-episode** — `tools/scripts/new-episode.sh <slug>` creates `episodes/<YYYY-MM-DD>-<slug>/`,
   moves `incoming/raw.mp4` into `source/`, writes a starter `meta.yaml`.
2. **Stage 1 — video-use** — produces post-production-ready talking-head master.
   - 1.1 ElevenLabs Scribe transcription → `stage-1-cut/transcript.json`
   - 1.2 Cut analysis → `stage-1-cut/cut-list.md` → **⏸ CP1**
   - 1.3 Apply cuts + audio fades + grade + vignette → `stage-1-cut/master.mp4` → **⏸ CP2**
3. **Stage 2 — compositor** — overlays captions, motion graphics, music.
   - 2.1 Generate `stage-2-composite/seam-plan.md` → **⏸ CP2.5**
   - 2.2 Build `composition.html`, render `preview.mp4` → **⏸ CP3**
   - 2.3 Final render + ffmpeg merge with `library/music/<track>.mp3` → `final.mp4`
4. **Retro** — fill `episodes/<slug>/retro.md`, run macro-retro, propose standards
   updates as `WATCH` / `CONFIRM` / `PROMOTE`. User selects which to promote.

## Standards (load before working on the matching stage)
- `standards/editing.md`         — cut philosophy, what to keep
- `standards/color.md`           — grade settings, source rejection rules
- `standards/audio.md`           — voice levels, music flat-background, no duck by default
- `standards/captions.md`        — typography, position, karaoke timing
- `standards/motion-graphics.md` — 4-scene system, transition matrix
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
- Never duplicate `music.mp3` into episode folders — always reference `library/music/`.
- Never skip a checkpoint. A checkpoint without stop is a bug.
- Never produce a seam transition forbidden by the matrix in `standards/motion-graphics.md`
  (`a↔a`, `a↔d`, `d↔d`, same-graphic `b→b` or `c→c`).
- Never accept HDR/HLG source. Reject at `new-episode.sh` with a clear error.
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
- Stage 2 (added in Phase 3): `tools/scripts/run-stage2.sh <slug>`
- Final render (added in Phase 3): `tools/scripts/render-final.sh <slug>`
- Retro promotion (added in Phase 4): `tools/scripts/retro-promote.sh <slug>`

## File-location quick map
- Sources                → `incoming/`, then `episodes/<slug>/source/`
- Music                  → `library/music/` only — never copied
- Brand tokens           → `design-system/tokens/tokens.json`
- Reusable HF components → `design-system/components/`
- Per-episode artifacts  → `episodes/<slug>/`
- Long-lived rules       → `standards/`
- Scripts                → `tools/scripts/`

## Environment
- `ELEVENLABS_API_KEY` is required (Scribe API). Plan must be Creator tier or higher.
- ffmpeg, node 20+, python 3.11+ with uv, git — all in PATH. Verify with `check-deps.sh`.
```

- [ ] **Step 2: Verify line count under target**

```bash
wc -l AGENTS.md
```

Expected: under 200 lines. (If over, surplus must migrate to `standards/`.)

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs: agent contract"
```

---

### Task 15: Write `tools/scripts/new-episode.sh` test (failing)

**Files:**
- Create: `tools/scripts/test/test-new-episode.sh`

- [ ] **Step 1: Write the test**

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
NEW_EPISODE="$REPO_ROOT/tools/scripts/new-episode.sh"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Build a fake repo layout inside $WORK
mkdir -p "$WORK/incoming" "$WORK/episodes" "$WORK/library/music"
# Use ffmpeg to synthesize a 1-second 1440x2560 60fps Rec.709 SDR test clip
ffmpeg -y -f lavfi -i "color=c=blue:s=1440x2560:r=60:d=1" \
  -c:v libx264 -pix_fmt yuv420p -profile:v high -colorspace bt709 \
  -color_primaries bt709 -color_trc bt709 \
  "$WORK/incoming/raw.mp4" >/dev/null 2>&1
echo "" > "$WORK/library/music/test-track.mp3"

# Run the script in the fake repo
( cd "$WORK" && "$NEW_EPISODE" my-test-slug ) || { echo "FAIL: script exited non-zero"; exit 1; }

# Find the produced episode directory
EPISODE_DIR="$(ls -d "$WORK"/episodes/*-my-test-slug 2>/dev/null | head -n1)"
if [ -z "$EPISODE_DIR" ]; then
  echo "FAIL: no episode directory matching *-my-test-slug created"
  exit 1
fi

# Required structure
for path in source/raw.mp4 stage-1-cut stage-2-composite meta.yaml; do
  if [ ! -e "$EPISODE_DIR/$path" ]; then
    echo "FAIL: $path not produced inside $EPISODE_DIR"
    exit 1
  fi
done

# raw.mp4 should have moved out of incoming/
if [ -e "$WORK/incoming/raw.mp4" ]; then
  echo "FAIL: raw.mp4 still in incoming/, should have been moved"
  exit 1
fi

# meta.yaml must contain slug
if ! grep -q "slug: my-test-slug" "$EPISODE_DIR/meta.yaml"; then
  echo "FAIL: meta.yaml missing slug"
  exit 1
fi

echo "OK: new-episode.sh produced expected structure"
```

- [ ] **Step 2: Run, expect failure**

```bash
chmod +x tools/scripts/test/test-new-episode.sh
tools/scripts/test/test-new-episode.sh
```

Expected: failure (script does not exist yet).

---

### Task 16: Implement `tools/scripts/new-episode.sh`

**Files:**
- Create: `tools/scripts/new-episode.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
set -euo pipefail

# Create a new episode directory from incoming/raw.mp4.
# Usage: tools/scripts/new-episode.sh <slug>

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <slug>"
  exit 1
fi

SLUG="$1"
if ! [[ "$SLUG" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "ERROR: slug must be lowercase alphanumeric with dashes (got: $SLUG)"
  exit 1
fi

REPO_ROOT="$(pwd)"
INCOMING="$REPO_ROOT/incoming"
EPISODES="$REPO_ROOT/episodes"
RAW="$INCOMING/raw.mp4"

if [ ! -f "$RAW" ]; then
  echo "ERROR: $RAW not found. Drop your raw footage there first."
  exit 1
fi

# Reject HDR/HLG sources. Probe color transfer characteristics with ffprobe.
TRC="$(ffprobe -v error -select_streams v:0 -show_entries stream=color_transfer \
       -of default=nw=1:nk=1 "$RAW" 2>/dev/null || true)"
case "$TRC" in
  smpte2084|arib-std-b67|smpte428|bt2020-10|bt2020-12)
    echo "ERROR: source uses HDR/HLG transfer ($TRC). Re-export as Rec.709 SDR (gamma 2.4)."
    echo "See standards/color.md for source format requirements."
    exit 1
    ;;
esac

DATE="$(date +%Y-%m-%d)"
DIR="$EPISODES/${DATE}-${SLUG}"

if [ -e "$DIR" ]; then
  echo "ERROR: $DIR already exists"
  exit 1
fi

mkdir -p "$DIR/source" "$DIR/stage-1-cut" "$DIR/stage-2-composite"
mv "$RAW" "$DIR/source/raw.mp4"

# Optional notes file
if [ -f "$INCOMING/notes.md" ]; then
  mv "$INCOMING/notes.md" "$DIR/notes.md"
fi

# Probe basic metadata for meta.yaml
DURATION="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 \
            "$DIR/source/raw.mp4" 2>/dev/null || echo "0")"

cat > "$DIR/meta.yaml" <<EOF
title: ""
slug: ${SLUG}
date: ${DATE}
duration_seconds: ${DURATION}
tags: []
targets:
  - youtube-shorts
  - tiktok
music: ""  # Fill with relative path: library/music/<filename>.mp3
EOF

# Empty retro file ready for the episode
: > "$DIR/retro.md"

echo "Created $DIR"
echo "Next steps:"
echo "  1. Edit $DIR/meta.yaml (title, music, tags)."
echo "  2. Run: tools/scripts/run-stage1.sh ${DATE}-${SLUG}"
```

- [ ] **Step 2: Make executable**

```bash
chmod +x tools/scripts/new-episode.sh
```

- [ ] **Step 3: Run test, expect pass**

```bash
tools/scripts/test/test-new-episode.sh
```

Expected: `OK: new-episode.sh produced expected structure`

- [ ] **Step 4: Commit**

```bash
git add tools/scripts/new-episode.sh tools/scripts/test/test-new-episode.sh
git commit -m "feat: new-episode.sh creates episode skeleton with HDR rejection"
```

---

### Task 17: Final phase verification

- [ ] **Step 1: Confirm all expected paths exist**

```bash
for p in \
  .gitignore .env.example README.md AGENTS.md \
  standards/editing.md standards/captions.md standards/motion-graphics.md \
  standards/audio.md standards/color.md standards/retro-changelog.md \
  design-system/tokens/tokens.json design-system/README.md \
  tools/scripts/check-deps.sh tools/scripts/new-episode.sh \
  tools/scripts/test/test-check-deps.sh tools/scripts/test/test-new-episode.sh \
  docs/superpowers/specs/2026-04-27-video-editing-studio-design.md \
  docs/superpowers/plans/2026-04-27-phase-1-foundation.md ; do
  [ -e "$p" ] || { echo "MISSING: $p"; exit 1; }
done
echo "OK: phase 1 layout complete"
```

Expected: `OK: phase 1 layout complete`

- [ ] **Step 2: Run all tests**

```bash
tools/scripts/test/test-check-deps.sh
tools/scripts/test/test-new-episode.sh
```

Expected: both report `OK`.

- [ ] **Step 3: Confirm clean working tree**

```bash
git status
```

Expected: `nothing to commit, working tree clean`.

- [ ] **Step 4: Tag the phase**

```bash
git tag phase-1-foundation
```

---

## Phase 1 done. Next: `2026-04-27-phase-2-stage-1-video-use.md`.
