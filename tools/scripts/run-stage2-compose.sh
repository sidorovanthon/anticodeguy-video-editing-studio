#!/usr/bin/env bash
set -euo pipefail

# Stage 2a: produce seam-plan.md (CP2.5), root index.html, and the
# captions sub-composition for a given episode slug. Does NOT render
# preview.mp4.
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
[ -f "$EPISODE/master/bundle.json" ]           || { echo "ERROR: master/bundle.json missing"; exit 1; }
[ -f "$REPO_ROOT/DESIGN.md" ]                  || { echo "ERROR: $REPO_ROOT/DESIGN.md missing"; exit 1; }

mkdir -p "$COMPOSITE_DIR"

# Step 1: seam-plan (CP2.5)
REPO_ROOT="$REPO_ROOT" npx -y tsx tools/compositor/src/index.ts seam-plan --episode "$EPISODE"
echo "CP2.5 ready: $COMPOSITE_DIR/seam-plan.md. Awaiting review."

# Step 2: emit root index.html + captions sub-composition + per-seam wires
REPO_ROOT="$REPO_ROOT" npx tsx tools/compositor/src/index.ts compose --episode "$EPISODE"

# Step 3: HyperFrames lint + validate + inspect against the canonical
# project (index.html lives directly under stage-2-composite/).
npx -y hyperframes lint "$COMPOSITE_DIR"      || { echo "ERROR: hyperframes lint failed"; exit 1; }
npx hyperframes validate "$COMPOSITE_DIR"     || { echo "ERROR: hyperframes validate failed"; exit 1; }
npx hyperframes inspect "$COMPOSITE_DIR" --json > "$COMPOSITE_DIR/.inspect.json" || {
  echo "ERROR: hyperframes inspect failed; see $COMPOSITE_DIR/.inspect.json"
  exit 1
}

# Step 4: animation-map (informational; does not gate). Outputs JSON for
# review during smoke tests and Phase 6b agent iteration.
ANIM_MAP_SCRIPT="$REPO_ROOT/tools/hyperframes-skills/hyperframes/scripts/animation-map.mjs"
if [ -f "$ANIM_MAP_SCRIPT" ]; then
  node "$ANIM_MAP_SCRIPT" "$COMPOSITE_DIR" --out "$COMPOSITE_DIR/.hyperframes/anim-map" || {
    echo "WARN: animation-map errored; continuing"
  }
fi

echo "Compose ready: $COMPOSITE_DIR/index.html. Run run-stage2-preview.sh next."
