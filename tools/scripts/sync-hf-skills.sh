#!/usr/bin/env bash
set -euo pipefail

# Sync vendored HyperFrames skills from the latest npm tarball.
# Writes the resolved version to tools/hyperframes-skills/VERSION.
# Run on demand when HyperFrames updates and we want their newer skill text.

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SKILLS_DIR="$REPO_ROOT/tools/hyperframes-skills"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

VERSION="$(npm view hyperframes version)"
TARBALL_URL="$(npm view hyperframes dist.tarball)"

echo "Syncing hyperframes@$VERSION skills from $TARBALL_URL"
curl -sL "$TARBALL_URL" | tar xz -C "$TMP_DIR"

[ -d "$TMP_DIR/package/dist/skills" ] || {
  echo "ERROR: tarball has no dist/skills/ — HF may have changed layout"
  exit 1
}

rm -rf "$SKILLS_DIR"
mkdir -p "$SKILLS_DIR"
cp -r "$TMP_DIR/package/dist/skills/." "$SKILLS_DIR/"
echo "$VERSION" > "$SKILLS_DIR/VERSION"

echo "Done. Vendored at $SKILLS_DIR (version $VERSION)."
