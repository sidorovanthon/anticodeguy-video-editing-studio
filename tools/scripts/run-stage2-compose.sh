#!/usr/bin/env bash
set -euo pipefail

# Stage 2a: produce seam-plan.md (CP2.5), root index.html, and the
# captions sub-composition for a given episode slug. Does NOT render
# preview.mp4.
#
# Usage: tools/scripts/run-stage2-compose.sh <slug>

# shellcheck source=tools/scripts/lib/preflight.sh
. "$(dirname "$0")/lib/preflight.sh"
hf_preflight || { echo "ERROR: doctor preflight failed; aborting compose"; exit 1; }

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
npx hyperframes validate "$COMPOSITE_DIR" || { echo "ERROR: hyperframes validate failed"; exit 1; }
npx hyperframes inspect "$COMPOSITE_DIR" --json > "$COMPOSITE_DIR/.inspect.json" || {
  echo "ERROR: hyperframes inspect failed; see $COMPOSITE_DIR/.inspect.json"
  echo "       annotate intentional overflow with data-layout-allow-overflow / data-layout-ignore"
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

# Captured-element guard: shader-compat rule forbids var() in inline styles
# and class rules consumed by html2canvas. The :root { --… } docs are fine.
if grep -REn 'style="[^"]*var\(--' "$COMPOSITE_DIR/index.html" "$COMPOSITE_DIR/compositions"/*.html >/dev/null; then
  echo "ERROR: var(--…) found in inline style attribute on a captured element."
  echo "       Resolve via designMd.resolveToken at compose time; see DESIGN.md 'What NOT to Do' #6."
  grep -REn 'style="[^"]*var\(--' "$COMPOSITE_DIR/index.html" "$COMPOSITE_DIR/compositions"/*.html
  exit 1
fi

echo "Compose ready: $COMPOSITE_DIR/index.html. Run run-stage2-preview.sh next."
