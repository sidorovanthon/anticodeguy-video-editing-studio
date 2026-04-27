#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
CLI="$REPO_ROOT/tools/scripts/script-diff.py"
FIX="$SCRIPT_DIR/fixtures/script-diff"

if [ ! -f "$CLI" ]; then
  echo "FAIL: $CLI missing"; exit 1
fi

run_case() {
  local name="$1"; shift
  local work; work="$(mktemp -d)"
  trap 'rm -rf "$work"' RETURN
  local ep="$work/episode"
  mkdir -p "$ep/source" "$ep/stage-1-cut/edit/transcripts"
  cp "$FIX/$name/script.txt" "$ep/source/script.txt"
  cp "$FIX/$name/raw.json"   "$ep/stage-1-cut/edit/transcripts/raw.json"
  cp "$FIX/$name/edl.json"   "$ep/stage-1-cut/edl.json"
  python "$CLI" --episode "$ep" >/dev/null
  if [ ! -f "$ep/stage-1-cut/script-diff.md" ]; then
    echo "FAIL[$name]: script-diff.md not produced"; return 1
  fi
  if [ ! -f "$ep/stage-1-cut/script-diff.json" ]; then
    echo "FAIL[$name]: script-diff.json not produced"; return 1
  fi
  python - "$ep/stage-1-cut/script-diff.json" "$name" <<'PY'
import json, sys
data = json.loads(open(sys.argv[1], encoding="utf-8").read())
case = sys.argv[2]
if case == "basic":
    assert data["script_coverage_pct"] >= 90.0, data
    assert data["dropped_spans"] == [], data
    assert data["ad_libs"] == [], data
    assert data["retakes"] == [], data
elif case == "dropped-line":
    # The middle sentence (8 tokens) must show up as a dropped span, marked in_raw=true.
    drops = data["dropped_spans"]
    assert any("compilers are pattern matchers" in d["text"] and d["in_raw"]
               for d in drops), drops
elif case == "retake-and-adlib":
    rt = data["retakes"]
    assert len(rt) >= 1, rt
    assert any(r["kept_range"] is not None for r in rt), rt
    al = data["ad_libs"]
    assert any("by the way please" in a["text"] for a in al), al
print(f"OK[{case}]")
PY
}

run_case basic
run_case dropped-line
run_case retake-and-adlib

# Skip behavior: missing inputs should exit 0 silently.
EMPTY="$(mktemp -d)"
trap 'rm -rf "$EMPTY"' EXIT
mkdir -p "$EMPTY/episode/stage-1-cut"
OUT="$(python "$CLI" --episode "$EMPTY/episode")"
echo "$OUT" | grep -q "skipping" || { echo "FAIL: missing-input case did not skip"; exit 1; }

echo "OK: script-diff smoke tests pass"
