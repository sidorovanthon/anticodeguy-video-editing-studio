#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cp -r "$REPO_ROOT" "$WORK/repo"
cd "$WORK/repo"
EP="$WORK/repo/episodes/2026-04-27-demo"
mkdir -p "$EP/stage-1-cut" "$EP/stage-2-composite" "$EP/master" "$WORK/repo/library/music"

# Stage 2 reads ONLY the bundle (Phase 5 contract). No transcript.json or cut-list.md needed.
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

ffmpeg -y -f lavfi -i "color=c=red:s=1440x2560:r=60:d=2" -f lavfi -i "anullsrc=r=48000:cl=stereo:d=2" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 128k -shortest \
  "$EP/stage-1-cut/master.mp4" >/dev/null 2>&1
ffmpeg -y -f lavfi -i "anoisesrc=d=2:c=pink:r=48000:a=0.05" -c:a libmp3lame \
  "$WORK/repo/library/music/test.mp3" >/dev/null 2>&1

cat > "$EP/meta.yaml" <<EOF
title: "Demo"
slug: 2026-04-27-demo
date: 2026-04-27
duration_seconds: 2
tags: []
targets: [youtube-shorts]
music: library/music/test.mp3
EOF

./tools/scripts/run-stage2.sh 2026-04-27-demo
./tools/scripts/render-final.sh 2026-04-27-demo \
  || { echo "FAIL: render-final exited non-zero"; exit 1; }

FINAL="$EP/stage-2-composite/final.mp4"
[ -f "$FINAL" ] || { echo "FAIL: final.mp4 missing"; exit 1; }

RES="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of default=nw=1 "$FINAL")"
echo "$RES" | grep -q "width=1440"  || { echo "FAIL: width";  echo "$RES"; exit 1; }
echo "$RES" | grep -q "height=2560" || { echo "FAIL: height"; echo "$RES"; exit 1; }
echo "$RES" | grep -qE "r_frame_rate=60(/1)?" || { echo "FAIL: fps"; echo "$RES"; exit 1; }

MEAN_VOL="$(ffmpeg -i "$FINAL" -af volumedetect -vn -f null /dev/null 2>&1 | grep mean_volume | awk '{print $5}')"
[ -n "$MEAN_VOL" ] || { echo "FAIL: no audio in final"; exit 1; }

echo "OK: final.mp4 conforms to spec"
