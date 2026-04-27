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
