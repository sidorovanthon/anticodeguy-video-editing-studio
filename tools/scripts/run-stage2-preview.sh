#!/usr/bin/env bash
set -euo pipefail

# Stage 2b: render preview.mp4 from the stage-2-composite/ project produced
# by run-stage2-compose.sh (HF reads index.html directly under that dir).
#
# Usage: tools/scripts/run-stage2-preview.sh <slug> [--workers N] [--fps N] [--quality Q] [--draft]
#
# Resolution is ALWAYS native 1440x2560 — stage-2-composite/index.html is
# not mutated. RAM/CPU is throttled instead via fewer Chromium workers,
# a lower fps, and a lower encoder quality for previews. Final renders
# should be invoked separately (e.g. render-final.sh) without this
# throttling.
#
# Defaults: --workers 1 --fps 30 --quality standard (cheap-and-survivable
# on dev machines). --draft is a shortcut for --quality draft and is
# strongly recommended for smoke tests on memory-pressured hosts.
# hyperframes' --workers flag launches a separate Chrome process per
# worker (~256 MB RAM each); 1 worker keeps RAM bounded for 1440x2560.
# We also pin --max-concurrent-renders to 1 so HF's producer server
# does not double-spawn Chrome instances behind our back.

usage() {
  echo "Usage: $0 <slug> [--workers N] [--fps N] [--quality Q] [--draft]"
  echo "  --workers N    Parallel Chromium render workers (default: 1)"
  echo "  --fps N        Frame rate: 24, 30, or 60 (default: 30)"
  echo "  --quality Q    HF encoder quality: draft, standard, high (default: standard)"
  echo "  --draft        Shortcut for --quality draft. Recommended for smoke tests."
}

if [ "$#" -lt 1 ]; then
  usage
  exit 1
fi

SLUG=""
WORKERS=1
FPS=30
QUALITY=standard

while [ "$#" -gt 0 ]; do
  case "$1" in
    --workers)
      [ "$#" -ge 2 ] || { echo "ERROR: --workers requires a value"; exit 1; }
      WORKERS="$2"; shift 2 ;;
    --workers=*)
      WORKERS="${1#--workers=}"; shift ;;
    --fps)
      [ "$#" -ge 2 ] || { echo "ERROR: --fps requires a value"; exit 1; }
      FPS="$2"; shift 2 ;;
    --fps=*)
      FPS="${1#--fps=}"; shift ;;
    --quality)
      [ "$#" -ge 2 ] || { echo "ERROR: --quality requires a value"; exit 1; }
      QUALITY="$2"; shift 2 ;;
    --quality=*)
      QUALITY="${1#--quality=}"; shift ;;
    --draft)
      QUALITY=draft; shift ;;
    -h|--help)
      usage; exit 0 ;;
    -*)
      echo "ERROR: unknown flag '$1'"; usage; exit 1 ;;
    *)
      if [ -z "$SLUG" ]; then SLUG="$1"; shift
      else echo "ERROR: unexpected positional arg '$1'"; usage; exit 1
      fi ;;
  esac
done

[ -n "$SLUG" ] || { echo "ERROR: <slug> required"; usage; exit 1; }
case "$WORKERS" in ''|*[!0-9]*) echo "ERROR: --workers must be a positive integer"; exit 1 ;; esac
[ "$WORKERS" -ge 1 ] || { echo "ERROR: --workers must be >= 1"; exit 1; }
case "$FPS" in ''|*[!0-9]*) echo "ERROR: --fps must be a positive integer"; exit 1 ;; esac
[ "$FPS" -ge 1 ] || { echo "ERROR: --fps must be >= 1"; exit 1; }
case "$QUALITY" in draft|standard|high) ;; *) echo "ERROR: --quality must be draft|standard|high"; exit 1 ;; esac

# shellcheck source=tools/scripts/lib/preflight.sh
. "$(dirname "$0")/lib/preflight.sh"
hf_preflight || { echo "ERROR: doctor preflight failed; aborting preview"; exit 1; }

HF_RENDER_MODE="${HF_RENDER_MODE:-docker}"
RENDER_FLAGS=()
if [ "$HF_RENDER_MODE" = "docker" ]; then
  RENDER_FLAGS+=(--docker)
elif [ "$HF_RENDER_MODE" = "local" ]; then
  WORKERS=1
  QUALITY=draft
else
  echo "ERROR: HF_RENDER_MODE must be 'docker' or 'local' (got '$HF_RENDER_MODE')"
  exit 1
fi

REPO_ROOT="$(pwd)"
EPISODE="$REPO_ROOT/episodes/$SLUG"
COMPOSITE_DIR="$EPISODE/stage-2-composite"
HF_INDEX="$COMPOSITE_DIR/index.html"

[ -f "$HF_INDEX" ] || { echo "ERROR: $HF_INDEX missing — run run-stage2-compose.sh first"; exit 1; }

HF_OUT="$COMPOSITE_DIR/preview.mp4"
rm -f "$HF_OUT"
npx -y hyperframes render "$COMPOSITE_DIR" \
  -o preview.mp4 \
  -f "$FPS" \
  -q "$QUALITY" \
  --format mp4 \
  --workers "$WORKERS" \
  --max-concurrent-renders 1 \
  "${RENDER_FLAGS[@]}" || { echo "ERROR: hyperframes render failed"; exit 1; }

# `-o` may be interpreted relative to the project dir or to cwd, or HF may
# place it in the default renders/<name>_<ts>.mp4 location. Relocate to $HF_OUT.
if [ ! -f "$HF_OUT" ]; then
  if [ -f "$REPO_ROOT/preview.mp4" ]; then
    mv "$REPO_ROOT/preview.mp4" "$HF_OUT"
  elif ls "$COMPOSITE_DIR"/renders/*.mp4 >/dev/null 2>&1; then
    mv "$(ls -t "$COMPOSITE_DIR"/renders/*.mp4 | head -n1)" "$HF_OUT"
  fi
fi

[ -f "$HF_OUT" ] || { echo "ERROR: preview.mp4 not produced"; exit 1; }
echo "Preview ready: $HF_OUT (workers=$WORKERS fps=$FPS). Awaiting CP3 review."
