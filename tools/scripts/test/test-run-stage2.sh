#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cp -r "$REPO_ROOT" "$WORK/repo"
cd "$WORK/repo"
EP="$WORK/repo/episodes/2026-04-27-demo"
mkdir -p "$EP/stage-1-cut" "$EP/stage-2-composite"
cp tools/compositor/test/fixtures/transcript.sample.json "$EP/stage-1-cut/transcript.json"
printf "at_ms=0\nat_ms=500\nat_ms=1000\n" > "$EP/stage-1-cut/cut-list.md"
ffmpeg -y -f lavfi -i "color=c=red:s=1440x2560:r=60:d=2" -c:v libx264 -pix_fmt yuv420p \
  "$EP/stage-1-cut/master.mp4" >/dev/null 2>&1

./tools/scripts/run-stage2.sh 2026-04-27-demo \
  || { echo "FAIL: run-stage2 exited non-zero"; exit 1; }

[ -f "$EP/stage-2-composite/seam-plan.md" ]      || { echo "FAIL: seam-plan.md missing"; exit 1; }
[ -f "$EP/stage-2-composite/composition.html" ]  || { echo "FAIL: composition.html missing"; exit 1; }
[ -f "$EP/stage-2-composite/preview.mp4" ]       || { echo "FAIL: preview.mp4 missing"; exit 1; }
echo "OK"
