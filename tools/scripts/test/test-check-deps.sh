#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK="$SCRIPT_DIR/../check-deps.sh"

if [ ! -x "$CHECK" ]; then
  echo "FAIL: $CHECK is not executable"
  exit 1
fi

OUTPUT="$("$CHECK" 2>&1)" || { echo "FAIL: check-deps exited non-zero"; echo "$OUTPUT"; exit 1; }

for tool in ffmpeg node python uv git; do
  if ! echo "$OUTPUT" | grep -q "$tool"; then
    echo "FAIL: $tool not reported in output"
    echo "$OUTPUT"
    exit 1
  fi
done

echo "OK: check-deps reports all required tools"
