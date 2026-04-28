#!/usr/bin/env bash
set -euo pipefail

# Final render: HF renders the complete final.mp4 in one pass. Music has
# already been copied into stage-2-composite/assets/ by run-stage2-compose.sh,
# and index.html references it via data-volume=0.5 (music ducked 6 dB below
# voice). No ffmpeg post-processing.
#
# Usage: tools/scripts/render-final.sh <slug>

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <slug>"
  exit 1
fi

SLUG="$1"
REPO_ROOT="$(pwd)"
HF_BIN="$REPO_ROOT/tools/compositor/node_modules/.bin/hyperframes"
[ -x "$HF_BIN" ] || { echo "ERROR: pinned hyperframes binary not found at $HF_BIN — run 'cd tools/compositor && npm install'"; exit 1; }

# shellcheck source=tools/scripts/lib/preflight.sh
. "$(dirname "$0")/lib/preflight.sh"
hf_preflight || { echo "ERROR: doctor preflight failed; aborting final render"; exit 1; }
EP="$REPO_ROOT/episodes/$SLUG"
COMPOSITE_DIR="$EP/stage-2-composite"
HF_INDEX="$COMPOSITE_DIR/index.html"
FINAL="$COMPOSITE_DIR/final.mp4"

[ -f "$HF_INDEX" ]                          || { echo "ERROR: $HF_INDEX missing — run run-stage2-compose.sh first"; exit 1; }
[ -f "$COMPOSITE_DIR/assets/master.mp4" ]   || { echo "ERROR: assets/master.mp4 missing — run run-stage1.sh <slug> render first"; exit 1; }

HF_RENDER_MODE="${HF_RENDER_MODE:-docker}"
RENDER_FLAGS=()
if [ "$HF_RENDER_MODE" = "docker" ]; then
  RENDER_FLAGS+=(--docker)
elif [ "$HF_RENDER_MODE" != "local" ]; then
  echo "ERROR: HF_RENDER_MODE must be 'docker' or 'local' (got '$HF_RENDER_MODE')"
  exit 1
fi

rm -f "$FINAL"
"$HF_BIN" render "$COMPOSITE_DIR" \
  -o final.mp4 \
  -f 60 \
  -q high \
  --format mp4 \
  --workers 1 \
  --max-concurrent-renders 1 \
  "${RENDER_FLAGS[@]}" || { echo "ERROR: hyperframes render failed"; exit 1; }

# Relocate output if HF placed it in a renders/ subdir.
if [ ! -f "$FINAL" ]; then
  if   [ -f "$REPO_ROOT/final.mp4" ]; then mv "$REPO_ROOT/final.mp4" "$FINAL"
  elif ls "$COMPOSITE_DIR"/renders/*.mp4 >/dev/null 2>&1; then
    mv "$(ls -t "$COMPOSITE_DIR"/renders/*.mp4 | head -n1)" "$FINAL"
  fi
fi

[ -f "$FINAL" ] || { echo "ERROR: final.mp4 not produced"; exit 1; }
echo "Final render complete: $FINAL"
