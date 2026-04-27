#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cp -r "$REPO_ROOT" "$WORK/repo"
cd "$WORK/repo"
EP="$WORK/repo/episodes/2026-04-27-promote-test"
mkdir -p "$EP"

cat > "$EP/promote.txt" <<EOF
PROMOTE captions.md baseline 22%-from-bottom episode=2026-04-27-promote-test reason="overlap"
EOF

./tools/scripts/retro-promote.sh 2026-04-27-promote-test \
  || { echo "FAIL: retro-promote exited non-zero"; exit 1; }

grep -q "baseline 22%-from-bottom" standards/captions.md || { echo "FAIL: standards/captions.md not updated"; exit 1; }
grep -q "promote-test" standards/retro-changelog.md      || { echo "FAIL: changelog not appended"; exit 1; }
echo "OK"
