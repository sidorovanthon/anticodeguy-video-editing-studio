#!/usr/bin/env bash
set -euo pipefail

# Stage 2 of the pipeline: produce seam-plan (CP2.5), composition.html, and
# preview.mp4 (CP3) for a given episode slug.
#
# Usage: tools/scripts/run-stage2.sh <slug>

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <slug>"
  exit 1
fi

SLUG="$1"
REPO_ROOT="$(pwd)"
EPISODE="$REPO_ROOT/episodes/$SLUG"
COMPOSITE_DIR="$EPISODE/stage-2-composite"

[ -d "$EPISODE" ]                              || { echo "ERROR: $EPISODE not found"; exit 1; }
[ -f "$EPISODE/stage-1-cut/master.mp4" ]       || { echo "ERROR: master.mp4 missing"; exit 1; }
[ -f "$EPISODE/stage-1-cut/transcript.json" ]  || { echo "ERROR: transcript.json missing"; exit 1; }
[ -f "$EPISODE/stage-1-cut/cut-list.md" ]      || { echo "ERROR: cut-list.md missing"; exit 1; }

mkdir -p "$COMPOSITE_DIR"

# Step 1: seam-plan (CP2.5)
REPO_ROOT="$REPO_ROOT" npx -y tsx tools/compositor/src/index.ts seam-plan --episode "$EPISODE"
echo "CP2.5 ready: $COMPOSITE_DIR/seam-plan.md. Awaiting review."

# Step 2: compose composition.html
REPO_ROOT="$REPO_ROOT" npx tsx tools/compositor/src/index.ts compose --episode "$EPISODE"

# Step 3: HyperFrames lint (mandatory per docs/notes/hyperframes-cli.md).
# HyperFrames consumes a project dir whose root composition is index.html.
# Our composer writes composition.html (the durable artifact). Stage a
# sibling project dir HF_PROJ containing only index.html so HyperFrames
# does not flag "multiple_root_compositions" against composition.html.
HF_PROJ="$COMPOSITE_DIR/hf-project"
rm -rf "$HF_PROJ"
mkdir -p "$HF_PROJ"
# Copy composition.html into the HF project as index.html. The composer
# emits the master.mp4 src relative to composition.html (one level above
# hf-project), so prepend "../" to keep that reference resolvable when the
# renderer loads index.html from inside hf-project.
sed -E 's#(src=")(\.\./)#\1../\2#g' \
  "$COMPOSITE_DIR/composition.html" > "$HF_PROJ/index.html"

npx -y hyperframes lint "$HF_PROJ" || { echo "ERROR: hyperframes lint failed"; exit 1; }

# Step 4: render preview.mp4. Resolution lives on the root <div data-width=1440
# data-height=2560>; the CLI only sets fps + format + quality + output.
HF_OUT="$COMPOSITE_DIR/preview.mp4"
rm -f "$HF_OUT"
npx -y hyperframes render "$HF_PROJ" \
  -o preview.mp4 \
  -f 60 \
  -q high \
  --format mp4 || { echo "ERROR: hyperframes render failed"; exit 1; }

# `-o` may be interpreted relative to the project dir or to cwd, or HF may
# place it in the default renders/<name>_<ts>.mp4 location. Relocate to $HF_OUT.
if [ ! -f "$HF_OUT" ]; then
  if [ -f "$HF_PROJ/preview.mp4" ]; then
    mv "$HF_PROJ/preview.mp4" "$HF_OUT"
  elif [ -f "$REPO_ROOT/preview.mp4" ]; then
    mv "$REPO_ROOT/preview.mp4" "$HF_OUT"
  elif ls "$HF_PROJ"/renders/*.mp4 >/dev/null 2>&1; then
    mv "$(ls -t "$HF_PROJ"/renders/*.mp4 | head -n1)" "$HF_OUT"
  fi
fi

[ -f "$HF_OUT" ] || { echo "ERROR: preview.mp4 not produced"; exit 1; }
echo "CP3 ready: $HF_OUT. Awaiting review."
