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
cp "$REPO_ROOT/tools/compositor/grade.json" "$WORK/tools/compositor/"
cp "$REPO_ROOT/tools/scripts/new-episode.sh" "$WORK/tools/scripts/"
cp "$REPO_ROOT/tools/scripts/run-stage1.sh" "$WORK/tools/scripts/"
cp "$REPO_ROOT/tools/scripts/_render_edl.py" "$WORK/tools/scripts/"
chmod +x "$WORK/tools/scripts/new-episode.sh" "$WORK/tools/scripts/run-stage1.sh" "$WORK/tools/scripts/_render_edl.py"

# Use the smoke clip as our raw input
cp "$SMOKE/raw.mp4" "$WORK/incoming/raw.mp4"

# Create the episode skeleton via new-episode.sh
( cd "$WORK" && ./tools/scripts/new-episode.sh smoke )
EPISODE="$(ls -d "$WORK"/episodes/*-smoke | head -n1)"
SLUG="$(basename "$EPISODE")"

# Pre-place a hand-crafted edl.json so the test exercises the render path only.
# raw.mp4 is ~4.2s long; pick two ranges that fit.
RAW_ABS="$EPISODE/source/raw.mp4"
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
