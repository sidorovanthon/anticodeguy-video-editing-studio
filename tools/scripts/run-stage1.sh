#!/usr/bin/env bash
set -euo pipefail

# Stage 1 of the pipeline:
#   default mode: transcribe → pack → author edl.json (subagent) → CP1
#   render mode:  ffmpeg-based render from edl.json → master.mp4 → CP2
#
# Usage: tools/scripts/run-stage1.sh <slug> [render]
#   slug = directory name under episodes/, e.g. 2026-04-27-using-claude-skills

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "Usage: $0 <slug> [render]"
  exit 1
fi

SLUG="$1"
MODE="${2:-cp1}"
case "$MODE" in
  cp1|render) ;;
  *) echo "ERROR: second argument must be 'render' or omitted"; exit 1 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(pwd)"
EPISODE="$REPO_ROOT/episodes/$SLUG"
STAGE1="$EPISODE/stage-1-cut"
SOURCE_RAW="$EPISODE/source/raw.mp4"
ENV_FILE="$REPO_ROOT/.env"

[ -d "$EPISODE" ]    || { echo "ERROR: $EPISODE not found"; exit 1; }
[ -f "$SOURCE_RAW" ] || { echo "ERROR: $SOURCE_RAW not found"; exit 1; }
[ -f "$ENV_FILE" ]   || { echo "ERROR: $ENV_FILE missing (copy .env.example to .env)"; exit 1; }

# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

mkdir -p "$STAGE1"

if [ "$MODE" = "render" ]; then
  # ============== RENDER MODE (CP2) ==============
  EDL="$STAGE1/edl.json"
  MASTER="$STAGE1/master.mp4"
  GRADE_JSON="$REPO_ROOT/tools/compositor/grade.json"

  [ -f "$EDL" ]        || { echo "ERROR: $EDL not found — run CP1 first"; exit 1; }
  [ -f "$GRADE_JSON" ] || { echo "ERROR: $GRADE_JSON missing"; exit 1; }

  if [ -f "$MASTER" ] && [ "${FORCE:-0}" != "1" ]; then
    echo "ERROR: $MASTER already exists. Set FORCE=1 to overwrite."
    exit 1
  fi

  python "$SCRIPT_DIR/_render_edl.py" \
    --edl "$EDL" \
    --grade "$GRADE_JSON" \
    --output "$MASTER"

  echo
  echo "CP2 ready: $MASTER. Awaiting review."
  exit 0
fi

# ============== CP1 MODE (default) ==============
[ -n "${ELEVENLABS_API_KEY:-}" ] || { echo "ERROR: ELEVENLABS_API_KEY empty in .env"; exit 1; }

# Stage raw.mp4 inside stage-1-cut/ as a relative copy/symlink so video-use
# helpers produce their `edit/` workspace under stage-1-cut/edit/.
STAGED_RAW="$STAGE1/raw.mp4"
if [ ! -e "$STAGED_RAW" ]; then
  # Use ln -s when supported; fall back to copy on Windows where symlinks need privileges.
  ln -sf "$SOURCE_RAW" "$STAGED_RAW" 2>/dev/null || cp "$SOURCE_RAW" "$STAGED_RAW"
fi

VIDEO_USE="$REPO_ROOT/tools/video-use"
TRANSCRIPT_JSON="$STAGE1/edit/transcripts/raw.json"
TAKES_PACKED="$STAGE1/edit/takes_packed.md"

# 1. Transcribe (Scribe API). Cached.
if [ -f "$TRANSCRIPT_JSON" ]; then
  echo "Cached transcript present, skipping Scribe call."
else
  echo "Running transcribe.py (Scribe API)..."
  ( cd "$VIDEO_USE" && \
    PYTHONUTF8=1 ELEVENLABS_API_KEY="$ELEVENLABS_API_KEY" \
    uv run python helpers/transcribe.py "$STAGED_RAW" )
fi
[ -f "$TRANSCRIPT_JSON" ] || { echo "ERROR: transcribe.py did not produce $TRANSCRIPT_JSON"; exit 1; }

# 2. Pack. Cached.
if [ -f "$TAKES_PACKED" ]; then
  echo "Cached packed transcript present, skipping pack."
else
  echo "Running pack_transcripts.py..."
  ( cd "$VIDEO_USE" && \
    PYTHONUTF8=1 \
    uv run python helpers/pack_transcripts.py --edit-dir "$STAGE1/edit" )
fi
[ -f "$TAKES_PACKED" ] || { echo "ERROR: pack_transcripts.py did not produce $TAKES_PACKED"; exit 1; }

# 3. Promise-named symlinks expected by AGENTS.md and downstream tooling.
ln -sf "$TRANSCRIPT_JSON" "$STAGE1/transcript.json"
ln -sf "$TAKES_PACKED"    "$STAGE1/cut-list.md"

# 4. Author edl.json via Claude subagent. Cached.
EDL="$STAGE1/edl.json"
if [ -f "$EDL" ]; then
  echo "Cached edl.json present, skipping subagent."
else
  echo "Dispatching Claude subagent to author edl.json..."

  RAW_ABS="$STAGED_RAW"
  EDITING_RULES="$REPO_ROOT/standards/editing.md"
  EDL_SCHEMA="$REPO_ROOT/docs/notes/video-use-cli.md"

  # Construct the prompt with all paths resolved.
  PROMPT=$(cat <<EOF
You are authoring an EDL (edit decision list) for stage 1 of a YouTube short.

## Inputs (read these files first)
- Phrase-level packed transcript: ${TAKES_PACKED}
- Cut philosophy and rules:        ${EDITING_RULES}
- EDL schema documentation:        ${EDL_SCHEMA} (look for the "EDL schema" section)

## Source video
Absolute path: ${RAW_ABS}

## Output
Write a single file: ${EDL}

The JSON must be valid against the schema documented in the EDL schema section. Use:
- "version": 1
- "sources": { "raw": "${RAW_ABS}" }
- "ranges": array of non-overlapping {source, start, end, beat} entries in increasing start time
- "grade": "none"
- "overlays": []
- "subtitles": null

## Procedure
1. Read all three input files.
2. Identify ranges to KEEP (not cut) following standards/editing.md rules:
   - keep deliberate pauses > 300 ms followed by tonal shift
   - cut filler words, restarts, repeated phrase starts, audible breaths > 400 ms
3. Express ranges in decimal seconds, taken from the [start-end] markers in takes_packed.md
   for the phrases you keep. You can also split a phrase if it contains an internal cut.
4. Output non-overlapping ranges in order of increasing start time.
5. Write valid JSON. Verify it parses before finishing.
6. Print one line to stdout: "EDL: N ranges, total Xs"

Do not modify any other file. Do not call any external API.
EOF
  )

  # Invoke claude in non-interactive headless mode.
  # --add-dir grants read/write under the repo root.
  claude -p "$PROMPT" --add-dir "$REPO_ROOT" --output-format text || {
    echo "ERROR: claude subagent failed. You can hand-author $EDL and re-run with the same command."
    exit 1
  }
fi

[ -f "$EDL" ] || { echo "ERROR: subagent did not produce $EDL"; exit 1; }

# 5. Validate edl.json structure.
python - "$EDL" "$RAW_ABS" <<'PY'
import json, sys, os
edl_path, raw_abs = sys.argv[1], sys.argv[2]
with open(edl_path) as f:
    edl = json.load(f)
required = {"version","sources","ranges"}
missing = required - edl.keys()
if missing:
    sys.exit(f"FAIL: edl.json missing keys: {missing}")
if not isinstance(edl["ranges"], list) or not edl["ranges"]:
    sys.exit("FAIL: edl.json ranges is empty or not a list")
for i,r in enumerate(edl["ranges"]):
    for k in ("source","start","end"):
        if k not in r: sys.exit(f"FAIL: range {i} missing {k}")
    if r["end"] <= r["start"]: sys.exit(f"FAIL: range {i} end <= start")
    if r["source"] not in edl["sources"]: sys.exit(f"FAIL: range {i} unknown source {r['source']}")
print(f"edl.json valid: {len(edl['ranges'])} ranges")
PY

echo
echo "CP1 ready: $EDL. Awaiting review."
echo "After approval, run: tools/scripts/run-stage1.sh $SLUG render"
