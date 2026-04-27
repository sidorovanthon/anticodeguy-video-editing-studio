# Phase 2 — Stage 1 (video-use) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vendor `browser-use/video-use`, hook it up with the user's ElevenLabs API key, and produce `tools/scripts/run-stage1.sh` such that for an episode with `source/raw.mp4` it produces `stage-1-cut/transcript.json`, `stage-1-cut/cut-list.md` (CP1), and `stage-1-cut/master.mp4` (CP2) — a post-production-ready talking-head with cuts, audio fades, color grade, and vignette burned in. **No captions, no overlays, no music** — those are Phase 3.

**Architecture:** video-use is a Python CLI that operates on a directory containing video and uses an internal LLM-driven loop. Our `run-stage1.sh` wrapper sets the working directory to `episodes/<slug>/stage-1-cut/`, copies/symlinks the raw source there, sets `ELEVENLABS_API_KEY` in environment, invokes video-use, and surfaces the artifacts back to the agent. If video-use's auto-grade is insufficient, an optional `stage-1.5` ffmpeg pass applies an explicit `eq` + `vignette` filter chain.

**Tech Stack:** Python 3.11+ via uv, video-use (https://github.com/browser-use/video-use), ffmpeg, ElevenLabs Scribe API (paid, Creator+).

**Prerequisite:** Phase 1 complete. `phase-1-foundation` git tag exists. `.env` exists with `ELEVENLABS_API_KEY` filled in.

---

## File structure produced by this phase

```
.env                                 (user-edited; gitignored)
tools/video-use/                     (vendored, gitignored)
tools/scripts/run-stage1.sh
tools/scripts/test/test-run-stage1.sh
tools/compositor/grade.json          (parameters for stage-1.5 ffmpeg pass)
docs/notes/video-use-cli.md          (captured CLI reference, since upstream README evolves)
```

Plus updates to: `standards/color.md`, `standards/audio.md`, `standards/retro-changelog.md`.

---

### Task 1: Vendor video-use

- [ ] **Step 1: Clone**

```bash
git clone https://github.com/browser-use/video-use tools/video-use
```

Expected: clone succeeds, `tools/video-use/README.md` exists.

- [ ] **Step 2: Pin to a known commit**

```bash
cd tools/video-use && git rev-parse HEAD > ../../docs/notes/video-use-pinned-sha.txt && cd -
```

Expected: file contains a 40-char SHA.

- [ ] **Step 3: Run uv sync**

```bash
cd tools/video-use && uv sync && cd -
```

Expected: `Resolved` and `Installed` lines, no errors.

- [ ] **Step 4: Confirm gitignore covers it**

```bash
git status --ignored | grep -q "tools/video-use" && echo OK
```

Expected: `OK`.

- [ ] **Step 5: Commit the SHA reference**

```bash
git add docs/notes/video-use-pinned-sha.txt
git commit -m "chore(video-use): pin upstream commit"
```

---

### Task 2: Capture video-use CLI reference

video-use's exact CLI evolves. Capture the version we vendored so future plan tasks reference reality, not invention.

**Files:**
- Create: `docs/notes/video-use-cli.md`

- [ ] **Step 1: Read the upstream README**

```bash
cat tools/video-use/README.md
```

- [ ] **Step 2: Inspect entry points**

```bash
ls tools/video-use/src 2>/dev/null || ls tools/video-use/
cat tools/video-use/pyproject.toml | grep -A5 'project.scripts\|entry-points' || true
```

- [ ] **Step 3: Test the CLI on `--help`**

```bash
cd tools/video-use && uv run python -m video_use --help 2>&1 | head -40 || \
  uv run video-use --help 2>&1 | head -40
cd -
```

Capture whichever invocation succeeds. If neither does, fall back to inspecting `tools/video-use/README.md` for the documented usage.

- [ ] **Step 4: Write `docs/notes/video-use-cli.md`**

The file should document, based on what was discovered in steps 1–3:
- exact invocation (e.g. `uv run video-use ...` or `uv run python -m video_use ...`)
- input expectations (working directory layout, where raw video must live)
- output expectations (`final.mp4` location, transcript file, project.md memory file)
- environment variables required (`ELEVENLABS_API_KEY` at minimum)
- how to disable burned-in subtitles (search README/source for `subtitle`, `caption`, `--no-subs`)
- how to disable overlay generation (search for `overlay`, `manim`, `remotion`, `pil`)
- how to control color grading (search for `grade`, `color`, `lut`)

If a flag does not exist for "disable subtitles" or "disable overlays," document that fact and we will instead post-process — extract the cleaned audio + cut decisions from `project.md` and re-render the master ourselves with ffmpeg in stage 1.4.

- [ ] **Step 5: Commit**

```bash
git add docs/notes/video-use-cli.md
git commit -m "docs(video-use): capture CLI reference for vendored version"
```

---

### Task 3: Smoke-test video-use end-to-end on a tiny clip

Before writing the wrapper, prove the tool runs on this machine with the user's API key.

- [ ] **Step 1: Verify `.env` has ElevenLabs key**

```bash
grep -q "^ELEVENLABS_API_KEY=.\\+" .env && echo OK
```

Expected: `OK`. If it fails, ask the user to fill in `.env`.

- [ ] **Step 2: Generate a tiny test clip with synthetic speech**

Use ElevenLabs TTS via curl to make 5 seconds of clean speech, then mux to a 1440×2560 video:

```bash
mkdir -p /tmp/video-use-smoke && cd /tmp/video-use-smoke

# Generate 5s of clean speech using ElevenLabs TTS API
source "$OLDPWD/.env"
curl -sS -X POST "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM" \
  -H "xi-api-key: $ELEVENLABS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello this is a smoke test for video use. Lets see what happens.","model_id":"eleven_turbo_v2"}' \
  --output speech.mp3

# Build a 1440x2560 video with the speech
ffmpeg -y -f lavfi -i "color=c=blue:s=1440x2560:r=60:d=6" -i speech.mp3 \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 320k -shortest \
  raw.mp4

cd "$OLDPWD"
```

Expected: `/tmp/video-use-smoke/raw.mp4` is a valid mp4. `ffprobe /tmp/video-use-smoke/raw.mp4` shows a video stream and an audio stream.

- [ ] **Step 3: Run video-use against the smoke directory**

Use the exact invocation captured in `docs/notes/video-use-cli.md`. For example:

```bash
cd /tmp/video-use-smoke
ELEVENLABS_API_KEY=$(grep ^ELEVENLABS_API_KEY= "$OLDPWD/.env" | cut -d= -f2) \
  "$OLDPWD/tools/video-use/.venv/bin/python" -m video_use --prompt "edit this into a clean clip"
cd "$OLDPWD"
```

(Adjust path to the venv interpreter and the module/script per what `docs/notes/video-use-cli.md` documented.)

Expected: a `final.mp4` (or whatever the documented output filename is) appears in the working directory, plus a transcript file and `project.md`. Note the exact paths produced.

- [ ] **Step 4: Record observed outputs in CLI doc**

Append to `docs/notes/video-use-cli.md`:

```markdown
## Observed smoke test (2026-04-27)
Working dir: /tmp/video-use-smoke
Inputs: raw.mp4 (6s, 1440x2560 60fps, blue background, ElevenLabs-generated speech)
Outputs produced:
- <list each file the tool wrote, with size and a one-line description>
Transcript schema: <paste a 10-line snippet of the transcript JSON, fields it has>
```

- [ ] **Step 5: Commit**

```bash
git add docs/notes/video-use-cli.md
git commit -m "docs(video-use): record smoke test results"
```

---

### Task 4: Write `run-stage1.sh` test (failing)

**Files:**
- Create: `tools/scripts/test/test-run-stage1.sh`

- [ ] **Step 1: Write the test**

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Use the smoke clip prepared in Task 3
SMOKE=/tmp/video-use-smoke
[ -f "$SMOKE/raw.mp4" ] || { echo "FAIL: smoke clip missing — re-run Task 3"; exit 1; }

# Set up a fake episode using new-episode.sh
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cp -r "$REPO_ROOT/.env" "$REPO_ROOT/standards" "$REPO_ROOT/tools" "$WORK/"
mkdir -p "$WORK/incoming" "$WORK/episodes"
cp "$SMOKE/raw.mp4" "$WORK/incoming/raw.mp4"

cd "$WORK" && tools/scripts/new-episode.sh smoke && cd "$OLDPWD"
EPISODE="$(ls -d "$WORK"/episodes/*-smoke | head -n1)"
SLUG="$(basename "$EPISODE")"

# Run stage 1
( cd "$WORK" && "$REPO_ROOT/tools/scripts/run-stage1.sh" "$SLUG" ) \
  || { echo "FAIL: run-stage1.sh exited non-zero"; exit 1; }

# Required outputs
for path in stage-1-cut/transcript.json stage-1-cut/cut-list.md stage-1-cut/master.mp4; do
  [ -f "$EPISODE/$path" ] || { echo "FAIL: $path not produced"; exit 1; }
done

# master.mp4 must be 1440x2560 60fps Rec.709 SDR
RES="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,color_transfer \
       -of default=nw=1 "$EPISODE/stage-1-cut/master.mp4")"
echo "$RES" | grep -q "width=1440" || { echo "FAIL: width != 1440"; echo "$RES"; exit 1; }
echo "$RES" | grep -q "height=2560" || { echo "FAIL: height != 2560"; echo "$RES"; exit 1; }
echo "$RES" | grep -qE "r_frame_rate=60(/1)?" || { echo "FAIL: fps != 60"; echo "$RES"; exit 1; }

echo "OK: run-stage1.sh produced transcript, cut-list, and 1440x2560 60fps master"
```

- [ ] **Step 2: Run, expect failure**

```bash
chmod +x tools/scripts/test/test-run-stage1.sh
tools/scripts/test/test-run-stage1.sh
```

Expected: failure (script does not exist yet).

---

### Task 5: Write `tools/compositor/grade.json`

This is consumed by an optional stage-1.5 ffmpeg pass. We commit it now so `run-stage1.sh` can reference it deterministically.

**Files:**
- Create: `tools/compositor/grade.json`

- [ ] **Step 1: Write the file**

```json
{
  "eq": {
    "saturation": 1.08,
    "contrast":   1.12,
    "gamma":      1.0,
    "brightness": 0.0
  },
  "vignette": {
    "angle": "PI/4",
    "x0":    "w/2",
    "y0":    "h/2"
  },
  "vignette_scale": 0.25,
  "ffmpeg_filter_chain": "eq=saturation=1.08:contrast=1.12,vignette=PI/4:eval=init"
}
```

- [ ] **Step 2: Commit**

```bash
git add tools/compositor/grade.json
git commit -m "feat(compositor): seed grade.json for stage-1.5"
```

---

### Task 6: Implement `tools/scripts/run-stage1.sh`

**Files:**
- Create: `tools/scripts/run-stage1.sh`

The script must:
1. Load `.env`.
2. Validate the episode directory and `source/raw.mp4`.
3. Stage the raw clip into `stage-1-cut/` (symlink, not copy).
4. Invoke video-use using the exact command documented in `docs/notes/video-use-cli.md`, with appropriate flags to **disable burned-in captions and overlay generation** (or, if those flags don't exist, post-process to strip them).
5. Run a stage-1.5 ffmpeg pass applying `tools/compositor/grade.json`'s filter chain to the video-use output, producing `master.mp4`.
6. Re-encode `master.mp4` to spec: 1440×2560, 60 fps, H.264 high, ~35 Mbps VBR, AAC 320 kbps, Rec.709 SDR.
7. Write `cut-list.md` from the transcript and video-use's session memory (`project.md`).

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
set -euo pipefail

# Run Stage 1: transcribe → cut → grade → master.mp4
# Usage: tools/scripts/run-stage1.sh <slug>
#   slug = directory name under episodes/, e.g. 2026-04-27-using-claude-skills

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <slug>"
  exit 1
fi

SLUG="$1"
REPO_ROOT="$(pwd)"
EPISODE="$REPO_ROOT/episodes/$SLUG"
STAGE1="$EPISODE/stage-1-cut"
RAW="$EPISODE/source/raw.mp4"

[ -d "$EPISODE" ] || { echo "ERROR: $EPISODE not found"; exit 1; }
[ -f "$RAW" ]     || { echo "ERROR: $RAW not found"; exit 1; }
[ -f "$REPO_ROOT/.env" ] || { echo "ERROR: .env missing"; exit 1; }

# shellcheck disable=SC1091
set -a; source "$REPO_ROOT/.env"; set +a
[ -n "${ELEVENLABS_API_KEY:-}" ] || { echo "ERROR: ELEVENLABS_API_KEY empty"; exit 1; }

mkdir -p "$STAGE1"
ln -sf "$RAW" "$STAGE1/raw.mp4"

# 1. video-use
# Replace the line below with the exact command captured in docs/notes/video-use-cli.md.
# Pass flags that disable burned-in captions and overlays where supported.
VIDEO_USE="$REPO_ROOT/tools/video-use"
(
  cd "$STAGE1"
  "$VIDEO_USE/.venv/bin/python" -m video_use \
    --prompt "Edit this into a tight short. Remove fillers and silences. Do NOT burn in captions. Do NOT add overlays. Apply auto color grade only."
)

# Locate video-use's primary output. Adjust the glob if the documented filename differs.
VU_OUT="$(ls -1 "$STAGE1"/edit/final.mp4 "$STAGE1"/final.mp4 2>/dev/null | head -n1 || true)"
[ -n "$VU_OUT" ] || { echo "ERROR: video-use did not produce expected output"; exit 1; }

# 2. Stage 1.5 grade pass + spec re-encode → master.mp4
GRADE_FILTER="$(python -c "import json;print(json.load(open('$REPO_ROOT/tools/compositor/grade.json'))['ffmpeg_filter_chain'])")"
ffmpeg -y -i "$VU_OUT" \
  -vf "$GRADE_FILTER,scale=1440:2560:flags=lanczos,fps=60" \
  -c:v libx264 -profile:v high -level 5.1 -pix_fmt yuv420p \
  -b:v 35M -maxrate 40M -bufsize 70M \
  -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
  -c:a aac -b:a 320k -ar 48000 -ac 2 \
  "$STAGE1/master.mp4"

# 3. Build cut-list.md from transcript + project.md
TRANSCRIPT="$(ls -1 "$STAGE1"/transcript.json "$STAGE1"/edit/transcript.json 2>/dev/null | head -n1 || true)"
[ -n "$TRANSCRIPT" ] || { echo "ERROR: no transcript.json found"; exit 1; }
ln -sf "$TRANSCRIPT" "$STAGE1/transcript.json"

PROJECT_MD="$(ls -1 "$STAGE1"/project.md "$STAGE1"/edit/project.md 2>/dev/null | head -n1 || true)"
{
  echo "# Cut list for $SLUG"
  echo
  echo "Generated from video-use session memory."
  echo
  if [ -n "$PROJECT_MD" ]; then
    cat "$PROJECT_MD"
  else
    echo "(no project.md found; transcript-only)"
  fi
} > "$STAGE1/cut-list.md"

echo
echo "Stage 1 complete."
echo "  Transcript: $STAGE1/transcript.json"
echo "  Cut list:   $STAGE1/cut-list.md   <-- CP1 review artifact"
echo "  Master:     $STAGE1/master.mp4    <-- CP2 review artifact"
```

- [ ] **Step 2: Make executable**

```bash
chmod +x tools/scripts/run-stage1.sh
```

- [ ] **Step 3: Run test, expect pass**

```bash
tools/scripts/test/test-run-stage1.sh
```

Expected: `OK: run-stage1.sh produced transcript, cut-list, and 1440x2560 60fps master`. If `--prompt` invocation differs from what `docs/notes/video-use-cli.md` documented, fix the script and re-run.

- [ ] **Step 4: Commit**

```bash
git add tools/scripts/run-stage1.sh tools/scripts/test/test-run-stage1.sh
git commit -m "feat: run-stage1.sh wraps video-use and produces 1440x2560 master"
```

---

### Task 7: Manual review of smoke output and standards adjustment

The grade defaults in `standards/color.md` and `tools/compositor/grade.json` are guesses. Run the smoke through Stage 1, eyeball the master, and tune.

- [ ] **Step 1: Inspect master.mp4**

Open `/tmp/video-use-smoke-episode/.../stage-1-cut/master.mp4` (or rerun `test-run-stage1.sh` and inspect the produced file). Report observations against `standards/color.md` defaults: is contrast appropriate? vignette too strong / too weak? saturation correct?

- [ ] **Step 2: If adjustments needed, edit `tools/compositor/grade.json` and `standards/color.md`**

Update both files with new values. Append a record to `standards/retro-changelog.md`:

```markdown
## 2026-04-27 — color.md, grade.json
- Tuned contrast / saturation / vignette intensity based on smoke test.
- Source: phase 2 smoke test, /tmp/video-use-smoke.
- Reason: defaults were [too strong | too weak | correct]; new values [list].
```

- [ ] **Step 3: Commit**

```bash
git add standards/color.md standards/retro-changelog.md tools/compositor/grade.json
git commit -m "tune(stage1): adjust grade defaults from smoke observation"
```

If no adjustment was needed, skip Step 2–3 and note in the next task that defaults held.

---

### Task 8: Phase verification

- [ ] **Step 1: Run all tests from this and prior phases**

```bash
tools/scripts/test/test-check-deps.sh
tools/scripts/test/test-new-episode.sh
tools/scripts/test/test-run-stage1.sh
```

Expected: all three report `OK`.

- [ ] **Step 2: Confirm clean working tree**

```bash
git status
```

Expected: `nothing to commit, working tree clean`.

- [ ] **Step 3: Tag the phase**

```bash
git tag phase-2-stage-1
```

---

## Phase 2 done. Next: `2026-04-27-phase-3-stage-2-compositor.md`.
