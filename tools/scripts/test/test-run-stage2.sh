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

ffmpeg -y \
  -f lavfi -i "color=c=red:s=1440x2560:r=60:d=2" \
  -f lavfi -i "anullsrc=r=44100:cl=mono" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest \
  "$EP/stage-2-composite/assets/master.mp4" >/dev/null 2>&1

./tools/scripts/run-stage2-compose.sh 2026-04-27-demo \
  || { echo "FAIL: run-stage2-compose exited non-zero"; exit 1; }
./tools/scripts/run-stage2-preview.sh 2026-04-27-demo --draft \
  || { echo "FAIL: run-stage2-preview exited non-zero"; exit 1; }

[ -f "$EP/stage-2-composite/seam-plan.md" ]  || { echo "FAIL: seam-plan.md missing"; exit 1; }
[ -f "$EP/stage-2-composite/index.html" ]    || { echo "FAIL: index.html missing"; exit 1; }
[ -f "$EP/stage-2-composite/preview.mp4" ]   || { echo "FAIL: preview.mp4 missing"; exit 1; }

# --- regression: HF gates must carry strict-mode flags ---
# Compose regenerates index.html before gates run, so injecting a warning
# into a composed file and re-invoking the wrapper is not viable. Instead we
# assert the three gate lines carry the expected flags directly in the wrapper
# source. This is a text assertion: it fails if the flags are absent and
# passes once the wrapper is updated.
WRAPPER="$WORK/repo/tools/scripts/run-stage2-compose.sh"
# The gate lines use $HF_BIN (a variable), not the literal word "hyperframes",
# so match on the gate subcommand + strict flag pattern instead.
grep -qE '\blint\b.*--strict-all' "$WRAPPER" \
  || { echo "FAIL: lint gate missing --strict-all in run-stage2-compose.sh"; exit 1; }
grep -qE '\bvalidate\b.*--strict-all' "$WRAPPER" \
  || { echo "FAIL: validate gate missing --strict-all in run-stage2-compose.sh"; exit 1; }
grep -qE '\binspect\b.*(--strict-all|--strict)' "$WRAPPER" \
  || { echo "FAIL: inspect gate missing --strict / --strict-all in run-stage2-compose.sh"; exit 1; }
echo "PASS: HF gate strict-mode flags present in wrapper"

echo "OK"
