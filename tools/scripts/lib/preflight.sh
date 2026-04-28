#!/usr/bin/env bash
# Sourced by run-stage2-compose.sh / run-stage2-preview.sh / render-final.sh.
# Runs `hyperframes doctor` (via pinned binary) and exits the calling shell
# on critical failures.
#
# Critical failures (always fatal):  Node, FFmpeg, FFprobe, Chrome.
# Conditional failures (fatal only when HF_RENDER_MODE != local):
#   Docker, Docker running.
#
# HF_RENDER_MODE defaults to docker. Set HF_RENDER_MODE=local to bypass
# Docker checks (e.g., on hosts without Docker installed).

hf_preflight() {
  local mode="${HF_RENDER_MODE:-docker}"
  local hf_bin="$REPO_ROOT/tools/compositor/node_modules/.bin/hyperframes"
  if [ ! -x "$hf_bin" ]; then
    echo "ERROR: pinned hyperframes binary not found at $hf_bin — run 'cd tools/compositor && npm install'"
    return 1
  fi
  local out
  out="$("$hf_bin" doctor 2>&1 || true)"

  # Match either the literal ✗ marker OR a line that mentions the critical label
  # words AND a failure verb. Belt-and-suspenders: a future HF version that wraps
  # ✗ in ANSI colour codes will still trip the second branch.
  local crit_re_glyph='^\s*✗\s+(Node\.js|FFmpeg|FFprobe|Chrome)\b'
  local crit_re_words='(Node\.js|FFmpeg|FFprobe|Chrome).*(missing|not found|FAIL|failed)'
  if echo "$out" | grep -E "$crit_re_glyph" >/dev/null \
     || echo "$out" | grep -E "$crit_re_words" >/dev/null; then
    echo "[preflight] Critical doctor check failed:"
    echo "$out" | grep -E "$crit_re_glyph|$crit_re_words"
    return 1
  fi

  if [ "$mode" != "local" ]; then
    local docker_re_glyph='^\s*✗\s+Docker(\s+running)?\b'
    local docker_re_words='Docker.*(missing|not found|not running|FAIL|failed)'
    if echo "$out" | grep -E "$docker_re_glyph" >/dev/null \
       || echo "$out" | grep -E "$docker_re_words" >/dev/null; then
      echo "[preflight] Docker check failed (HF_RENDER_MODE=docker default):"
      echo "$out" | grep -E "$docker_re_glyph|$docker_re_words"
      echo "[preflight] To bypass: rerun with HF_RENDER_MODE=local"
      return 1
    fi
  fi

  echo "[preflight] hyperframes doctor OK (mode=$mode)"
  return 0
}
