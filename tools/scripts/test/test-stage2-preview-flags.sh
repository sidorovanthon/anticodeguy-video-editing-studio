#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

cp -r "$REPO_ROOT" "$WORK/repo"
cd "$WORK/repo"

SLUG="2026-04-27-flagtest"
EP="$WORK/repo/episodes/$SLUG"
mkdir -p "$EP/stage-2-composite"
# Minimal index.html to satisfy the wrapper's existence check.
cat > "$EP/stage-2-composite/index.html" <<'HTML'
<!doctype html><html><body>stub</body></html>
HTML

# Replace the pinned hyperframes binary inside the copy with a stub that:
#  - logs argv,
#  - on `render <projectDir>` touches preview.mp4 inside that dir so the
#    wrapper's post-render existence check passes,
#  - exits 0 for every invocation (including the doctor preflight call).
HF_STUB_LOG="$WORK/hf-stub.log"
export HF_STUB_LOG
HF_BIN_PATH="$WORK/repo/tools/compositor/node_modules/.bin/hyperframes"
mkdir -p "$(dirname "$HF_BIN_PATH")"
cat > "$HF_BIN_PATH" <<'STUB'
#!/usr/bin/env bash
echo "ARGS: $*" >> "$HF_STUB_LOG"
if [ "${1:-}" = "render" ] && [ -n "${2:-}" ]; then
  mkdir -p "$2"
  : > "$2/preview.mp4"
fi
exit 0
STUB
chmod +x "$HF_BIN_PATH"

HF_RENDER_MODE=local ./tools/scripts/run-stage2-preview.sh "$SLUG" --gpu \
  || { echo "FAIL: run-stage2-preview exited non-zero with --gpu"; cat "$HF_STUB_LOG" 2>/dev/null || true; exit 1; }

# The render invocation must carry --gpu. The doctor preflight call will not.
grep -qE '^ARGS: render(\s|$).*--gpu' "$HF_STUB_LOG" \
  || { echo "FAIL: --gpu not present on hyperframes render argv"; echo "--- stub log ---"; cat "$HF_STUB_LOG"; exit 1; }

echo "PASS: --gpu plumbing reaches hyperframes invocation"

# ----------------------------------------------------------------------------
# Scenario 2: duration-warning tripwire for long master.mp4 in local mode.
# Build a 31s placeholder master.mp4 and assert the wrapper warns when invoked
# without --draft, and does NOT warn when invoked with --draft.
# ----------------------------------------------------------------------------

mkdir -p "$EP/stage-2-composite/assets"
MASTER_MP4="$EP/stage-2-composite/assets/master.mp4"
ffmpeg -y -hide_banner -loglevel error \
  -f lavfi -i "color=c=black:s=320x240:r=30:d=31" \
  -c:v libx264 -pix_fmt yuv420p "$MASTER_MP4" \
  || { echo "FAIL: could not synthesise placeholder master.mp4"; exit 1; }

# 2a: WITHOUT --draft → warning expected.
: > "$HF_STUB_LOG"
STDERR_LOG="$WORK/wrapper.stderr.log"
HF_RENDER_MODE=local ./tools/scripts/run-stage2-preview.sh "$SLUG" 2>"$STDERR_LOG" >/dev/null \
  || { echo "FAIL: wrapper exited non-zero on long-master scenario"; cat "$STDERR_LOG"; exit 1; }
grep -q "WARNING: long episode in local mode" "$STDERR_LOG" \
  || { echo "FAIL: duration warning not emitted for >30s master in local mode"; echo "--- stderr ---"; cat "$STDERR_LOG"; exit 1; }
echo "PASS: duration warning emitted for long episode in local mode"

# 2b: WITH --draft → warning suppressed (negative control).
: > "$HF_STUB_LOG"
STDERR_LOG2="$WORK/wrapper.stderr.draft.log"
HF_RENDER_MODE=local ./tools/scripts/run-stage2-preview.sh "$SLUG" --draft 2>"$STDERR_LOG2" >/dev/null \
  || { echo "FAIL: wrapper exited non-zero on long-master + --draft scenario"; cat "$STDERR_LOG2"; exit 1; }
if grep -q "WARNING: long episode in local mode" "$STDERR_LOG2"; then
  echo "FAIL: duration warning emitted despite --draft (false positive)"
  echo "--- stderr ---"; cat "$STDERR_LOG2"; exit 1
fi
echo "PASS: duration warning suppressed when --draft is passed"
