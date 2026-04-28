#!/usr/bin/env bash
set -uo pipefail

# Non-blocking pre-flight: warn if fast-moving dependencies have newer upstream
# versions than what we have locally. Run from new-episode.sh so each new
# episode starts with current tooling. Never fails the build — surfaces
# notices for the operator to act on.

REPO_ROOT="$(pwd)"
NOTICES=0

note() { echo "  - $*"; NOTICES=$((NOTICES + 1)); }

echo "[check-updates] scanning fast-moving deps…"

# 1. HyperFrames (npm, 0.x — published frequently per docs/notes/hyperframes-cli.md)
LOCAL_HF="$(node -e "console.log(require('./tools/compositor/package.json').dependencies?.hyperframes || '')" 2>/dev/null | sed 's/^[~^>=]*//')"
if [ -n "$LOCAL_HF" ]; then
  LATEST_HF="$(npm view hyperframes version 2>/dev/null || true)"
  if [ -n "$LATEST_HF" ] && [ "$LOCAL_HF" != "$LATEST_HF" ]; then
    note "hyperframes: pinned $LOCAL_HF, latest $LATEST_HF — review CHANGELOG before upgrade (CLI surface still moving in 0.x)."
  fi
fi

# 1b. @hyperframes/producer — pinned in tools/hyperframes-skills/package.json (where its
#     consumers live). Must move in lockstep with the hyperframes CLI pin.
LOCAL_HFP="$(node -e "console.log(require('./tools/hyperframes-skills/package.json').dependencies?.['@hyperframes/producer'] || '')" 2>/dev/null | sed 's/^[~^>=]*//')"
if [ -n "$LOCAL_HFP" ]; then
  LATEST_HFP="$(npm view @hyperframes/producer version 2>/dev/null || true)"
  if [ -n "$LATEST_HFP" ] && [ "$LOCAL_HFP" != "$LATEST_HFP" ]; then
    note "@hyperframes/producer: pinned $LOCAL_HFP, latest $LATEST_HFP — must move in lockstep with hyperframes pin."
  fi
  if [ -n "$LOCAL_HF" ] && [ "$LOCAL_HF" != "$LOCAL_HFP" ]; then
    note "hyperframes ($LOCAL_HF) and @hyperframes/producer ($LOCAL_HFP) pins disagree — must be identical."
  fi
fi

# 1a. CLI/skills mismatch (exact-pin in package.json must equal vendored VERSION)
SKILLS_VERSION_FILE="$REPO_ROOT/tools/hyperframes-skills/VERSION"
if [ -n "$LOCAL_HF" ] && [ -f "$SKILLS_VERSION_FILE" ]; then
  SKILLS_VER="$(tr -d '[:space:]' < "$SKILLS_VERSION_FILE")"
  if [ "$LOCAL_HF" != "$SKILLS_VER" ]; then
    note "hyperframes CLI pin ($LOCAL_HF) ≠ vendored skills version ($SKILLS_VER) — run tools/scripts/sync-hf-skills.sh"
  fi
fi

# 2. video-use (vendored at a SHA in vendor/video-use)
if [ -d "$REPO_ROOT/vendor/video-use/.git" ] || [ -f "$REPO_ROOT/vendor/video-use/.git" ]; then
  LOCAL_VU="$(git -C "$REPO_ROOT/vendor/video-use" rev-parse --short HEAD 2>/dev/null || true)"
  REMOTE_VU="$(git -C "$REPO_ROOT/vendor/video-use" ls-remote origin HEAD 2>/dev/null | awk '{print substr($1,1,7)}')"
  if [ -n "$LOCAL_VU" ] && [ -n "$REMOTE_VU" ] && [ "$LOCAL_VU" != "$REMOTE_VU" ]; then
    note "vendor/video-use: at $LOCAL_VU, upstream HEAD $REMOTE_VU — re-vendor if upstream changes affect transcribe/pack."
  fi
fi

if [ "$NOTICES" -eq 0 ]; then
  echo "[check-updates] all dependencies current."
else
  echo "[check-updates] $NOTICES notice(s) above. Non-blocking — continuing."
fi

exit 0
