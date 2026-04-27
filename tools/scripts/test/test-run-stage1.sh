#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# We need a real raw.mp4 for ffmpeg to extract segments from.
# Reuse the Phase 2 Task 3 smoke clip if present; otherwise fail with a clear message.
SMOKE=/tmp/video-use-smoke
[ -f "$SMOKE/raw.mp4" ] || { echo "FAIL: $SMOKE/raw.mp4 missing — re-run Phase 2 Task 3 smoke first"; exit 1; }

# Build a fake repo layout in a temp dir
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$WORK/incoming" "$WORK/episodes" "$WORK/library/music" "$WORK/standards" "$WORK/tools/compositor" "$WORK/tools/scripts" "$WORK/docs/notes"
# Copy what the script needs from the real repo
cp "$REPO_ROOT/.env" "$WORK/.env"
cp -r "$REPO_ROOT/standards/." "$WORK/standards/"
# Copy compositor source so the bundle-write step can run via tsx.
cp -r "$REPO_ROOT/tools/compositor/." "$WORK/tools/compositor/"
cp "$REPO_ROOT/tools/scripts/new-episode.sh" "$WORK/tools/scripts/"
cp "$REPO_ROOT/tools/scripts/run-stage1.sh" "$WORK/tools/scripts/"
cp "$REPO_ROOT/tools/scripts/_render_edl.py" "$WORK/tools/scripts/"
cp "$REPO_ROOT/tools/scripts/script-diff.py" "$WORK/tools/scripts/"
cp -r "$REPO_ROOT/tools/scripts/script_diff" "$WORK/tools/scripts/script_diff"
chmod +x "$WORK/tools/scripts/new-episode.sh" "$WORK/tools/scripts/run-stage1.sh" "$WORK/tools/scripts/_render_edl.py"

# Use the smoke clip as our raw input
cp "$SMOKE/raw.mp4" "$WORK/incoming/raw.mp4"

# Create the episode skeleton via new-episode.sh
( cd "$WORK" && ./tools/scripts/new-episode.sh smoke )
EPISODE="$(ls -d "$WORK"/episodes/*-smoke | head -n1)"
SLUG="$(basename "$EPISODE")"

# ============== CP1 MODE TEST ==============
# Pre-seed all cached artifacts so no network calls are made.
EP="$EPISODE"
RAW_ABS="$EPISODE/source/raw.mp4"
mkdir -p "$EP/source" "$EP/stage-1-cut/edit/transcripts"

# Scribe-shaped raw.json (type: "word" entries required by script-diff.py)
cat > "$EP/stage-1-cut/edit/transcripts/raw.json" <<'JSON'
{
  "language_code": "en",
  "audio_duration_secs": 3.5,
  "words": [
    {"type": "word", "text": "hello",    "start": 0.00, "end": 0.30},
    {"type": "word", "text": "world",    "start": 0.35, "end": 0.70},
    {"type": "word", "text": "today",    "start": 0.75, "end": 1.10},
    {"type": "word", "text": "we",       "start": 1.15, "end": 1.30},
    {"type": "word", "text": "are",      "start": 1.32, "end": 1.50},
    {"type": "word", "text": "talking",  "start": 1.55, "end": 2.00},
    {"type": "word", "text": "about",    "start": 2.05, "end": 2.30},
    {"type": "word", "text": "script",   "start": 2.35, "end": 2.80},
    {"type": "word", "text": "fidelity", "start": 2.85, "end": 3.40}
  ]
}
JSON

# EDL covering the full word range
cat > "$EP/stage-1-cut/edl.json" <<'JSON'
{
  "version": 1,
  "sources": {"raw": "/fake/raw.mp4"},
  "ranges": [{"source": "raw", "start": 0.00, "end": 3.50, "beat": "all"}],
  "grade": "none",
  "overlays": [],
  "subtitles": null
}
JSON

# Minimal takes_packed.md to satisfy the cached-check guard
cat > "$EP/stage-1-cut/edit/takes_packed.md" <<'MD'
[0.00-3.50] hello world today we are talking about script fidelity
MD
# Promise-named symlinks the script also creates (pre-create to avoid ln errors)
ln -sf "$EP/stage-1-cut/edit/transcripts/raw.json" "$EP/stage-1-cut/transcript.json" 2>/dev/null || true
ln -sf "$EP/stage-1-cut/edit/takes_packed.md" "$EP/stage-1-cut/cut-list.md" 2>/dev/null || true

# Drop a verbatim script that matches the seeded raw.json content
echo "hello world today we are talking about script fidelity" \
  > "$EP/source/script.txt"

# Run CP1 mode; capture output for annotation check
CP1_OUT="$(cd "$WORK" && ./tools/scripts/run-stage1.sh "$SLUG" 2>&1)" \
  || { echo "FAIL: run-stage1.sh CP1 exited non-zero"; echo "$CP1_OUT"; exit 1; }
echo "$CP1_OUT"

# Assert script-diff.md was produced
if [ ! -f "$EP/stage-1-cut/script-diff.md" ]; then
  echo "FAIL: script-diff.md not produced when script.txt present"
  exit 1
fi

# Assert the CP1 ready line includes the diff annotation
echo "$CP1_OUT" | grep -q "script-diff.md" \
  || { echo "FAIL: CP1 ready line missing script-diff.md annotation"; echo "$CP1_OUT"; exit 1; }

echo "OK: run-stage1.sh CP1 produced script-diff.md and annotated ready line"

# ============== RENDER MODE TEST ==============
# Overwrite edl.json with real source paths for ffmpeg render.
# raw.mp4 is ~4.2s long; pick two ranges that fit.
mkdir -p "$EPISODE/stage-1-cut"
cat > "$EPISODE/stage-1-cut/edl.json" <<EOF
{
  "version": 1,
  "sources": { "raw": "$RAW_ABS" },
  "ranges": [
    { "source": "raw", "start": 0.10, "end": 1.50, "beat": "intro" },
    { "source": "raw", "start": 2.00, "end": 3.50, "beat": "outro" }
  ],
  "grade": "none",
  "overlays": [],
  "subtitles": null
}
EOF
# Remove master.mp4 if it somehow exists from a prior run
rm -f "$EPISODE/stage-1-cut/master.mp4"

# Run stage 1 in render mode
( cd "$WORK" && ./tools/scripts/run-stage1.sh "$SLUG" render ) \
  || { echo "FAIL: run-stage1.sh render exited non-zero"; exit 1; }

# Required outputs
[ -f "$EPISODE/stage-1-cut/master.mp4" ] || { echo "FAIL: master.mp4 not produced"; exit 1; }

# master.mp4 must be 1440x2560 60fps Rec.709 SDR H.264
RES="$(ffprobe -v error -select_streams v:0 \
       -show_entries stream=width,height,r_frame_rate,codec_name,profile,pix_fmt,color_space,color_transfer,color_primaries \
       -of default=nw=1 "$EPISODE/stage-1-cut/master.mp4")"
echo "$RES" | grep -q "width=1440"          || { echo "FAIL: width != 1440";   echo "$RES"; exit 1; }
echo "$RES" | grep -q "height=2560"         || { echo "FAIL: height != 2560";  echo "$RES"; exit 1; }
echo "$RES" | grep -qE "r_frame_rate=60(/1)?" || { echo "FAIL: fps != 60";      echo "$RES"; exit 1; }
echo "$RES" | grep -q "codec_name=h264"     || { echo "FAIL: codec != h264";   echo "$RES"; exit 1; }
echo "$RES" | grep -q "color_transfer=bt709" || { echo "FAIL: trc != bt709";    echo "$RES"; exit 1; }
echo "$RES" | grep -q "pix_fmt=yuv420p"       || { echo "FAIL: pix_fmt != yuv420p (must be studio-range, not yuvj420p)"; echo "$RES"; exit 1; }

# Audio must be AAC 48kHz stereo
ARES="$(ffprobe -v error -select_streams a:0 \
       -show_entries stream=codec_name,sample_rate,channels,bit_rate \
       -of default=nw=1 "$EPISODE/stage-1-cut/master.mp4")"
echo "$ARES" | grep -q "codec_name=aac"     || { echo "FAIL: audio not AAC";   echo "$ARES"; exit 1; }
echo "$ARES" | grep -q "sample_rate=48000"  || { echo "FAIL: sample_rate != 48000"; echo "$ARES"; exit 1; }

# Duration should be ~2.9s (sum of (1.5-0.10) + (3.5-2.0) = 1.4 + 1.5 = 2.9). Allow ±0.5s tolerance.
DUR="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$EPISODE/stage-1-cut/master.mp4")"
python -c "import sys; d=float('$DUR'); sys.exit(0 if 2.4 <= d <= 3.4 else 1)" \
  || { echo "FAIL: duration $DUR out of expected 2.4..3.4 range"; exit 1; }

echo "OK: run-stage1.sh render produced spec-compliant master.mp4 from edl.json"

# Bundle assertions
BUNDLE_PATH="$EPISODE/master/bundle.json"
[ -f "$BUNDLE_PATH" ] || { echo "FAIL: master/bundle.json missing"; exit 1; }
# Convert to a Windows-native path so Node.js (win32) can open it.
BUNDLE_PATH_WIN="$(cygpath -w "$BUNDLE_PATH" 2>/dev/null || echo "$BUNDLE_PATH")"
node -e "
const b = JSON.parse(require('fs').readFileSync(process.argv[1],'utf8'));
if (b.schemaVersion !== 1) throw new Error('schemaVersion');
if (typeof b.master.durationMs !== 'number') throw new Error('master.durationMs');
if (!Array.isArray(b.boundaries) || b.boundaries.length < 2) throw new Error('boundaries');
if (!Array.isArray(b.transcript.words)) throw new Error('transcript.words');
" -- "$BUNDLE_PATH_WIN" || { echo "FAIL: bundle.json shape invalid"; exit 1; }
echo "OK: master/bundle.json produced and valid"
