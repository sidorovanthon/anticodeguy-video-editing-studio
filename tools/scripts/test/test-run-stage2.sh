#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cp -r "$REPO_ROOT" "$WORK/repo"
cd "$WORK/repo"
EP="$WORK/repo/episodes/2026-04-27-demo"
mkdir -p "$EP/stage-1-cut" "$EP/stage-2-composite/assets" "$EP/master"

# Stage 2 must read ONLY the bundle. Deliberately do NOT write transcript.json
# or cut-list.md — if Stage 2 still reads them, run-stage2 will fail.
cat > "$EP/master/bundle.json" <<'JSON'
{
  "schemaVersion": 1,
  "slug": "2026-04-27-demo",
  "master": { "durationMs": 2000, "width": 1440, "height": 2560, "fps": 60 },
  "boundaries": [
    { "atMs": 0, "kind": "start" },
    { "atMs": 1000, "kind": "seam" },
    { "atMs": 2000, "kind": "end" }
  ],
  "transcript": {
    "language": "en",
    "words": [
      { "text": "Hello", "startMs": 0,    "endMs": 350 },
      { "text": "world", "startMs": 380,  "endMs": 720 },
      { "text": "today", "startMs": 1100, "endMs": 1480 }
    ]
  }
}
JSON

ffmpeg -y -f lavfi -i "color=c=red:s=1440x2560:r=60:d=2" -c:v libx264 -pix_fmt yuv420p \
  "$EP/stage-2-composite/assets/master.mp4" >/dev/null 2>&1

./tools/scripts/run-stage2-compose.sh 2026-04-27-demo \
  || { echo "FAIL: run-stage2-compose exited non-zero"; exit 1; }
./tools/scripts/run-stage2-preview.sh 2026-04-27-demo --draft \
  || { echo "FAIL: run-stage2-preview exited non-zero"; exit 1; }

[ -f "$EP/stage-2-composite/seam-plan.md" ]  || { echo "FAIL: seam-plan.md missing"; exit 1; }
[ -f "$EP/stage-2-composite/index.html" ]    || { echo "FAIL: index.html missing"; exit 1; }
[ -f "$EP/stage-2-composite/preview.mp4" ]   || { echo "FAIL: preview.mp4 missing"; exit 1; }

echo "OK"
