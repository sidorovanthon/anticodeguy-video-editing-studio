#!/usr/bin/env bash
set -euo pipefail
# Wrapper retained for backward compatibility (e.g. test-run-stage2.sh).
# Defaults to low-quality preview to avoid OOM on dev machines.
# For explicit final-quality rendering, call the two scripts directly.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/run-stage2-compose.sh" "$@"
"$SCRIPT_DIR/run-stage2-preview.sh" "$@"
