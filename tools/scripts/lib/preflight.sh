#!/usr/bin/env bash
# Sourced by run-stage2-compose.sh / run-stage2-preview.sh / render-final.sh.
# Runs `hyperframes doctor` (via pinned binary) and exits the calling shell
# on critical failures.
#
# Critical failures (always fatal):  Node, FFmpeg, FFprobe, Chrome.
# Conditional failures (fatal only when HF_RENDER_MODE != local):
#   Docker, Docker running.
#
# HF_RENDER_MODE defaults to local (matches run-stage2-preview.sh and
# render-final.sh defaults; commit ece9b63 archived Docker as opt-in).
# Set HF_RENDER_MODE=docker explicitly to enable Docker preflight checks.

hf_preflight() {
  local mode="${HF_RENDER_MODE:-local}"
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

# Soft-check: are the upstream HF issues we filed for catalog selector leakage
# (D15/D21 — heygen-com/hyperframes#556 + #557) still open? If both are closed,
# our wait-and-see plan needs revisiting: validate the fix on a 2-instance test
# and either upgrade past the fixed version (if newer) or close our internal
# WATCH item. Non-blocking — gh may be missing/offline. See
# `feedback_hf_556_watch.md` and `docs/operations/planner-pipeline-fixes/findings.md`.
hf_upstream_shim_check() {
  command -v gh >/dev/null 2>&1 || return 0
  local s556 s557
  s556="$(gh api repos/heygen-com/hyperframes/issues/556 --jq .state 2>/dev/null || echo unknown)"
  s557="$(gh api repos/heygen-com/hyperframes/issues/557 --jq .state 2>/dev/null || echo unknown)"
  if [ "$s556" = "closed" ] || [ "$s557" = "closed" ]; then
    echo
    echo "═══════════════════════════════════════════════════════════════════"
    echo "  UPSTREAM ALERT: HF catalog-selector issues changed state"
    echo "    #556 (isolation gap):  $s556"
    echo "    #557 (lint rule):      $s557"
    echo
    echo "  Action items if first time seeing this:"
    echo "    1. Update tools/compositor/package.json to a hyperframes version"
    echo "       that includes the fix; npm install."
    echo "    2. Verify with a 2-instance flowchart test (see"
    echo "       scratch/hf-shim-test/ for the harness)."
    echo "    3. If verified, remove this preflight check and update"
    echo "       docs/operations/planner-pipeline-fixes/findings.md."
    echo "═══════════════════════════════════════════════════════════════════"
    echo
  fi
  return 0
}
