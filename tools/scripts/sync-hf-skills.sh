#!/usr/bin/env bash
set -euo pipefail

# Sync vendored HyperFrames skills to match the pinned CLI version in
# tools/compositor/package.json. CLI and skills MUST stay at the same
# version — drift causes methodology rules and runtime to diverge silently.

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SKILLS_DIR="$REPO_ROOT/tools/hyperframes-skills"
PKG_JSON="$REPO_ROOT/tools/compositor/package.json"

# On Windows (Git Bash), Node.js needs a native Windows path; cygpath -w
# converts /c/... → C:\...; on Linux/macOS cygpath is absent so fall back.
if command -v cygpath &>/dev/null; then
  PKG_JSON_NATIVE="$(cygpath -w "$PKG_JSON")"
else
  PKG_JSON_NATIVE="$PKG_JSON"
fi

VERSION="$(HF_PKG_JSON="$PKG_JSON_NATIVE" node -e "
const fs = require('fs');
const pkg = JSON.parse(fs.readFileSync(process.env.HF_PKG_JSON, 'utf8'));
const v = pkg.dependencies.hyperframes;
if (!v) {
  process.stderr.write('ERROR: hyperframes not found in dependencies of tools/compositor/package.json\n');
  process.exit(2);
}
if (/^[\^~]/.test(v)) {
  process.stderr.write('ERROR: hyperframes pin ' + v + ' is not exact (no ^ or ~ allowed)\n       fix: edit tools/compositor/package.json to \"hyperframes\": \"<version>\" (no caret/tilde)\n');
  process.exit(2);
}
console.log(v);
")"
[ -n "$VERSION" ] || { echo "ERROR: could not read pinned hyperframes version"; exit 1; }

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

TARBALL_URL="$(npm view "hyperframes@$VERSION" dist.tarball --registry https://registry.npmjs.org)"
[ -n "$TARBALL_URL" ] || { echo "ERROR: hyperframes@$VERSION has no tarball on npm"; exit 1; }

echo "Syncing hyperframes@$VERSION skills from $TARBALL_URL"
curl -fsSL "$TARBALL_URL" | tar xz -C "$TMP_DIR"

[ -d "$TMP_DIR/package/dist/skills" ] || {
  echo "ERROR: tarball has no dist/skills/ — HF may have changed layout"
  exit 1
}

# Sync upstream-managed subtrees only. tools/hyperframes-skills/package.json,
# package-lock.json, and node_modules/ are ours (they provide @hyperframes/producer
# to the vendored skill scripts) and must survive resync.
# If dist/skills/ adds a new top-level dir, append it to the loop below.
mkdir -p "$SKILLS_DIR"
for subtree in gsap hyperframes hyperframes-cli; do
  rm -rf "$SKILLS_DIR/$subtree"
done
cp -r "$TMP_DIR/package/dist/skills/." "$SKILLS_DIR/"
echo "$VERSION" > "$SKILLS_DIR/VERSION"

echo "Done. Vendored at $SKILLS_DIR (version $VERSION)."
