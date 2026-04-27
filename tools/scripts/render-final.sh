#!/usr/bin/env bash
set -euo pipefail

# Stage 2 final render: composes the stage-1 master.mp4 with the HyperFrames
# overlay layer (rendered as transparent .mov via --format mov) and the music
# sidecar from library/music/<file>.mp3 into final.mp4.
#
# Audio per standards/audio.md: voice (master) at full level, music ducked
# 6 dB lower (loudnorm to -20 LUFS, weighted 0.5 in amix).
#
# Usage: tools/scripts/render-final.sh <slug>

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <slug>"
  exit 1
fi

SLUG="$1"
REPO_ROOT="$(pwd)"
EP="$REPO_ROOT/episodes/$SLUG"
COMPOSITE_DIR="$EP/stage-2-composite"
COMPOSITION="$COMPOSITE_DIR/composition.html"
MASTER="$EP/stage-1-cut/master.mp4"
META="$EP/meta.yaml"
FINAL="$COMPOSITE_DIR/final.mp4"
HF_PROJ="$COMPOSITE_DIR/hf-project"

[ -f "$COMPOSITION" ] || { echo "ERROR: composition.html missing — run run-stage2.sh first"; exit 1; }
[ -f "$MASTER" ]      || { echo "ERROR: master.mp4 missing"; exit 1; }
[ -f "$META" ]        || { echo "ERROR: meta.yaml missing"; exit 1; }
[ -d "$HF_PROJ" ]     || { echo "ERROR: hf-project/ missing — run run-stage2.sh first"; exit 1; }

# Extract music path from meta.yaml (supports quoted or unquoted).
MUSIC_REL="$(grep '^music:' "$META" | sed 's/^music:[[:space:]]*//;s/^"//;s/"$//')"
if [ -z "$MUSIC_REL" ]; then
  echo "ERROR: meta.yaml music: field is empty. Set it to library/music/<file>.mp3"
  exit 1
fi
MUSIC="$REPO_ROOT/$MUSIC_REL"
[ -f "$MUSIC" ] || { echo "ERROR: music file not found at $MUSIC"; exit 1; }

# Render overlays as MOV with alpha (HyperFrames: --format mov => transparent).
OVERLAYS_NAME="overlays.mov"
OVERLAYS="$COMPOSITE_DIR/$OVERLAYS_NAME"
rm -f "$OVERLAYS"
npx -y hyperframes render "$HF_PROJ" \
  -o "$OVERLAYS_NAME" \
  -f 60 \
  -q high \
  --format mov || { echo "ERROR: hyperframes final render failed"; exit 1; }

# Relocate output if HF placed it elsewhere (mirror run-stage2.sh fallback chain).
if [ ! -f "$OVERLAYS" ]; then
  if   [ -f "$HF_PROJ/$OVERLAYS_NAME" ]; then mv "$HF_PROJ/$OVERLAYS_NAME" "$OVERLAYS"
  elif [ -f "$REPO_ROOT/$OVERLAYS_NAME" ]; then mv "$REPO_ROOT/$OVERLAYS_NAME" "$OVERLAYS"
  elif ls "$HF_PROJ"/renders/*.mov >/dev/null 2>&1; then
    mv "$(ls -t "$HF_PROJ"/renders/*.mov | head -n1)" "$OVERLAYS"
  fi
fi
[ -f "$OVERLAYS" ] || { echo "ERROR: overlays.mov not produced"; exit 1; }

# ffmpeg merge: master video + overlays alpha + music sidecar.
# Audio per standards/audio.md: voice arrives from master at -14 LUFS (mastered
# upstream by video-use); music is loudnorm'd to -20 LUFS, which already bakes in
# the 6 dB gap below voice. amix weights are both 1 — no extra attenuation.
ffmpeg -y \
  -i "$MASTER" \
  -i "$OVERLAYS" \
  -i "$MUSIC" \
  -filter_complex "[0:v][1:v]overlay=0:0:format=auto[vout]; \
                   [2:a]loudnorm=I=-20:TP=-1:LRA=11[mloud]; \
                   [0:a][mloud]amix=inputs=2:duration=first:weights=1 1:normalize=0[aout]" \
  -map "[vout]" -map "[aout]" \
  -c:v libx264 -profile:v high -level 5.1 -pix_fmt yuv420p \
  -b:v 35M -maxrate 40M -bufsize 70M \
  -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
  -c:a aac -b:a 320k -ar 48000 -ac 2 \
  "$FINAL"

echo "Final render complete: $FINAL"
