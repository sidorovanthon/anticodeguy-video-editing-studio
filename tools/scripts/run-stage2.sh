#!/usr/bin/env bash
set -euo pipefail
# Wrapper retained for backward compatibility (e.g. test-run-stage2.sh).
# Defaults preview to 1 worker / 30 fps to avoid OOM on dev machines (see
# run-stage2-preview.sh). For explicit final-quality rendering, call the
# two scripts directly.
#
# The compose script accepts only <slug>; the preview script accepts
# <slug> [--workers N] [--fps N]. We forward the slug to compose and the
# full arg list to preview.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <slug> [--workers N] [--fps N]"
  exit 1
fi
SLUG="$1"

"$SCRIPT_DIR/run-stage2-compose.sh" "$SLUG"
"$SCRIPT_DIR/run-stage2-preview.sh" "$@"
