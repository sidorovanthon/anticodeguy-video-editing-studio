#!/usr/bin/env bash
set -euo pipefail

# Stage 2a: produce enriched seam-plan.md from script.txt + transcript bundle
# + EDL. Output: episodes/<slug>/stage-2-composite/seam-plan.md
#
# Stops at CP2.5 implicitly — host reviews / edits before run-stage2-generate.
#
# Usage: tools/scripts/run-stage2-plan.sh <slug>

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <slug>"
  exit 1
fi

SLUG="$1"
REPO_ROOT="$(pwd)"
EP="$REPO_ROOT/episodes/$SLUG"

[ -d "$EP" ]                         || { echo "ERROR: episode dir missing: $EP"; exit 1; }
[ -f "$EP/master/bundle.json" ]      || { echo "ERROR: master/bundle.json missing"; exit 1; }
[ -f "$EP/source/script.txt" ]       || { echo "ERROR: source/script.txt required for planner"; exit 1; }
[ -f "$EP/stage-1-cut/edl.json" ]    || { echo "ERROR: stage-1-cut/edl.json missing"; exit 1; }

# shellcheck source=tools/scripts/lib/preflight.sh
. "$(dirname "$0")/lib/preflight.sh"
hf_preflight || { echo "ERROR: doctor preflight failed; aborting plan"; exit 1; }

TSX_BIN="$REPO_ROOT/tools/compositor/node_modules/.bin/tsx"
[ -x "$TSX_BIN" ] || { echo "ERROR: pinned tsx binary not found at $TSX_BIN — run 'cd tools/compositor && npm install'"; exit 1; }

REPO_ROOT="$REPO_ROOT" "$TSX_BIN" "$REPO_ROOT/tools/compositor/src/index.ts" plan --episode "$EP"

echo "CP2.5 ready: $EP/stage-2-composite/seam-plan.md. Awaiting review."
