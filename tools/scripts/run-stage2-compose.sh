#!/usr/bin/env bash
set -euo pipefail

# Stage 2a: produce seam-plan.md (CP2.5), composition.html, and a staged
# hf-project/ for a given episode slug. Does NOT render preview.mp4.
#
# Usage: tools/scripts/run-stage2-compose.sh <slug>

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

echo "Compose ready: $COMPOSITE_DIR/seam-plan.md and composition.html. Run run-stage2-preview.sh next."
