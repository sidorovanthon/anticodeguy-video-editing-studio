#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
NEW_EPISODE="$REPO_ROOT/tools/scripts/new-episode.sh"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Build a fake repo layout inside $WORK
mkdir -p "$WORK/incoming" "$WORK/episodes" "$WORK/library/music"
ffmpeg -y -f lavfi -i "color=c=blue:s=1440x2560:r=60:d=1" \
  -c:v libx264 -pix_fmt yuv420p -profile:v high -colorspace bt709 \
  -color_primaries bt709 -color_trc bt709 \
  "$WORK/incoming/raw.mp4" >/dev/null 2>&1
echo "" > "$WORK/library/music/test-track.mp3"

# Write incoming/script.txt with a UTF-8 BOM (mirrors the real file).
printf '\xEF\xBB\xBFDesktop software licensing, it turns out, is also a whole story.\n\nMore lines.\n' \
  > "$WORK/incoming/script.txt"

# Run the script with NO args
( cd "$WORK" && "$NEW_EPISODE" ) || { echo "FAIL: script exited non-zero"; exit 1; }

EXPECTED_SLUG="desktop-software-licensing-it-turns-out"
EPISODE_DIR="$(ls -d "$WORK"/episodes/*-"$EXPECTED_SLUG" 2>/dev/null | head -n1)"
if [ -z "$EPISODE_DIR" ]; then
  echo "FAIL: no episode directory matching *-$EXPECTED_SLUG created"
  ls -d "$WORK"/episodes/* 2>/dev/null || true
  exit 1
fi

for path in source/raw.mp4 stage-1-cut stage-2-composite meta.yaml; do
  if [ ! -e "$EPISODE_DIR/$path" ]; then
    echo "FAIL: $path not produced inside $EPISODE_DIR"
    exit 1
  fi
done

if ! grep -q "slug: $EXPECTED_SLUG" "$EPISODE_DIR/meta.yaml"; then
  echo "FAIL: meta.yaml missing slug: $EXPECTED_SLUG"
  cat "$EPISODE_DIR/meta.yaml"
  exit 1
fi

# --- Second case: missing script.txt AND no slug arg => non-zero exit, mentions script.txt ---
WORK2="$(mktemp -d)"
trap 'rm -rf "$WORK" "$WORK2"' EXIT
mkdir -p "$WORK2/incoming" "$WORK2/episodes" "$WORK2/library/music"
ffmpeg -y -f lavfi -i "color=c=blue:s=1440x2560:r=60:d=1" \
  -c:v libx264 -pix_fmt yuv420p -profile:v high -colorspace bt709 \
  -color_primaries bt709 -color_trc bt709 \
  "$WORK2/incoming/raw.mp4" >/dev/null 2>&1

set +e
OUT="$( cd "$WORK2" && "$NEW_EPISODE" 2>&1 )"
RC=$?
set -e
if [ "$RC" -eq 0 ]; then
  echo "FAIL: expected non-zero exit when script.txt missing and no slug arg"
  exit 1
fi
if ! echo "$OUT" | grep -q "script.txt"; then
  echo "FAIL: expected error to mention script.txt; got: $OUT"
  exit 1
fi

echo "OK: new-episode.sh auto-slug behavior"
