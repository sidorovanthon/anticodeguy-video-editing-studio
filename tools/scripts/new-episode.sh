#!/usr/bin/env bash
set -euo pipefail

# Create a new episode directory from incoming/raw.mp4.
# Usage: tools/scripts/new-episode.sh [<slug>]
# With no slug, derives one from the first sentence of incoming/script.txt.

if [ "$#" -gt 1 ]; then
  echo "Usage: $0 [<slug>]"
  exit 1
fi

derive_slug_from_script() {
  local script_file="$1"
  # First non-empty line, BOM stripped, CR stripped.
  local line
  line="$(sed -e '1s/^\xEF\xBB\xBF//' -e 's/\r$//' "$script_file" \
          | awk 'NF { print; exit }')"
  # First sentence: cut at . ! ? when not preceded by a digit (avoid 1.5 splits).
  # If no terminator matches, keep the whole line.
  local sentence
  sentence="$(printf '%s' "$line" \
              | sed -E 's/^(([^.!?]|[0-9][.!?])*[^.!?0-9]?)[.!?].*$/\1/')"
  # Lowercase, non [a-z0-9] -> '-', collapse runs, strip edges.
  local slug
  slug="$(printf '%s' "$sentence" \
          | tr '[:upper:]' '[:lower:]' \
          | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"
  # Truncate to <=40 chars on a '-' boundary, strip trailing '-'.
  if [ "${#slug}" -gt 40 ]; then
    local head="${slug:0:40}"
    if [[ "$head" == *-* ]]; then
      head="${head%-*}"
    fi
    slug="$head"
  fi
  slug="${slug%-}"
  printf '%s' "$slug"
}

if [ "$#" -eq 1 ]; then
  SLUG="$1"
else
  SCRIPT_TXT="$(pwd)/incoming/script.txt"
  if [ ! -f "$SCRIPT_TXT" ]; then
    echo "ERROR: no slug given and incoming/script.txt not found." >&2
    exit 1
  fi
  SLUG="$(derive_slug_from_script "$SCRIPT_TXT")"
  if [ -z "$SLUG" ]; then
    echo "ERROR: could not derive slug from incoming/script.txt (empty after slugification)." >&2
    exit 1
  fi
  echo "Auto-derived slug: $SLUG" >&2
fi

if ! [[ "$SLUG" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "ERROR: slug must be lowercase alphanumeric with dashes (got: $SLUG)"
  exit 1
fi

REPO_ROOT="$(pwd)"
INCOMING="$REPO_ROOT/incoming"
EPISODES="$REPO_ROOT/episodes"
RAW="$INCOMING/raw.mp4"

if [ ! -f "$RAW" ]; then
  echo "ERROR: $RAW not found. Drop your raw footage there first."
  exit 1
fi

# Pre-flight: surface upstream updates for fast-moving deps. Non-blocking.
if [ -x "$REPO_ROOT/tools/scripts/check-updates.sh" ]; then
  "$REPO_ROOT/tools/scripts/check-updates.sh" || true
fi

# Reject HDR/HLG sources. Probe color transfer characteristics with ffprobe.
TRC="$(ffprobe -v error -select_streams v:0 -show_entries stream=color_transfer \
       -of default=nw=1:nk=1 "$RAW" 2>/dev/null || true)"
case "$TRC" in
  smpte2084|arib-std-b67|smpte428|bt2020-10|bt2020-12)
    echo "ERROR: source uses HDR/HLG transfer ($TRC). Re-export as Rec.709 SDR (gamma 2.4)."
    echo "See standards/color.md for source format requirements."
    exit 1
    ;;
esac

DATE="$(date +%Y-%m-%d)"
DIR="$EPISODES/${DATE}-${SLUG}"

if [ -e "$DIR" ]; then
  echo "ERROR: $DIR already exists"
  exit 1
fi

mkdir -p "$DIR/source" "$DIR/stage-1-cut" "$DIR/stage-2-composite"
mv "$RAW" "$DIR/source/raw.mp4"

# Optional notes file
if [ -f "$INCOMING/notes.md" ]; then
  mv "$INCOMING/notes.md" "$DIR/notes.md"
fi

# Optional verbatim script (consumed by tools/scripts/script-diff.py at CP1)
if [ -f "$INCOMING/script.txt" ]; then
  mv "$INCOMING/script.txt" "$DIR/source/script.txt"
fi

# Probe basic metadata for meta.yaml
DURATION="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 \
            "$DIR/source/raw.mp4" 2>/dev/null || echo "0")"

cat > "$DIR/meta.yaml" <<EOF
title: ""
slug: ${SLUG}
date: ${DATE}
duration_seconds: ${DURATION}
tags: []
targets:
  - youtube-shorts
  - tiktok
music: ""  # Fill with relative path: library/music/<filename>.mp3
EOF

# Empty retro file ready for the episode
: > "$DIR/retro.md"

echo "Created $DIR"
echo "Next steps:"
echo "  1. Edit $DIR/meta.yaml (title, music, tags)."
echo "  2. Run: tools/scripts/run-stage1.sh ${DATE}-${SLUG}"
if [ -f "$DIR/source/script.txt" ]; then
  echo "Detected verbatim script — script-diff will run automatically at CP1."
fi
