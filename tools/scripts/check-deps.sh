#!/usr/bin/env bash
set -euo pipefail

# Verify all tools required by the pipeline are installed and report versions.
# Exit non-zero if any tool is missing.

declare -A REQUIRED=(
  [ffmpeg]="ffmpeg -version | head -n1"
  [node]="node --version"
  [python]="python --version"
  [uv]="uv --version"
  [git]="git --version"
)

MISSING=()
for tool in "${!REQUIRED[@]}"; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    MISSING+=("$tool")
    echo "MISSING $tool"
  else
    VER="$(eval "${REQUIRED[$tool]}" 2>&1 | head -n1)"
    echo "OK      $tool — $VER"
  fi
done

if [ "${#MISSING[@]}" -gt 0 ]; then
  echo
  echo "Missing tools: ${MISSING[*]}"
  exit 1
fi
