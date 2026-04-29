#!/usr/bin/env bash
set -euo pipefail

# Stage 2b: read enriched seam-plan.md and dispatch parallel generative
# subagents to produce sub-compositions under stage-2-composite/compositions/.
#
# Usage: tools/scripts/run-stage2-generate.sh <slug>

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <slug>"
  exit 1
fi

SLUG="$1"
REPO_ROOT="$(pwd)"
EP="$REPO_ROOT/episodes/$SLUG"
PLAN="$EP/stage-2-composite/seam-plan.md"

[ -d "$EP" ]   || { echo "ERROR: episode dir missing: $EP"; exit 1; }
[ -f "$PLAN" ] || { echo "ERROR: $PLAN missing — run run-stage2-plan.sh first"; exit 1; }

# Allow operator to override default 4-minute per-scene timeout.
# Override is also picked up by realDispatcher.ts via opts.timeoutMs.
export HF_GENERATIVE_TIMEOUT_MS="${HF_GENERATIVE_TIMEOUT_MS:-}"

grep -q "^## Scene " "$PLAN" || { echo "ERROR: $PLAN is not in enriched format"; exit 1; }

# shellcheck source=tools/scripts/lib/preflight.sh
. "$(dirname "$0")/lib/preflight.sh"
hf_preflight || { echo "ERROR: doctor preflight failed; aborting generate"; exit 1; }
hf_upstream_shim_check

TSX_BIN="$REPO_ROOT/tools/compositor/node_modules/.bin/tsx"
[ -x "$TSX_BIN" ] || { echo "ERROR: pinned tsx binary not found at $TSX_BIN — run 'cd tools/compositor && npm install'"; exit 1; }

EPISODE_STATE_BIN="$REPO_ROOT/tools/compositor/dist/bin/episode-state.js"
if [ ! -f "$EPISODE_STATE_BIN" ]; then
  echo "error: $EPISODE_STATE_BIN not found; run 'npm run build' in tools/compositor" >&2
  exit 1
fi

if [ ! -f "$EP/state.json" ]; then
  node "$EPISODE_STATE_BIN" init --episode-dir "$EP" --slug "$SLUG"
fi

node "$EPISODE_STATE_BIN" mark-step-started --episode-dir "$EP" --step generate

REPO_ROOT="$REPO_ROOT" "$TSX_BIN" "$REPO_ROOT/tools/compositor/src/index.ts" generate --episode "$EP"

# State: mark generate step done (last successful action of the script)
node "$EPISODE_STATE_BIN" mark-step-done --episode-dir "$EP" --step generate --checkpoint CP2

echo "Generated sub-compositions in $EP/stage-2-composite/compositions/. Run run-stage2-compose.sh next."
