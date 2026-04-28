#!/usr/bin/env bash
# Sourced by run-stage2-compose.sh / run-stage2-preview.sh / render-final.sh.
# Runs `npx hyperframes doctor` and exits the calling shell on critical
# failures.
#
# Critical failures (always fatal):  Node, FFmpeg, Chrome.
# Conditional failures (fatal only when HF_RENDER_MODE != local):
#   Docker, Docker running.
#
# HF_RENDER_MODE defaults to docker. Set HF_RENDER_MODE=local to bypass
# Docker checks (e.g., on hosts without Docker installed).

hf_preflight() {
  local mode="${HF_RENDER_MODE:-docker}"
  local out
  out="$(npx -y hyperframes doctor 2>&1 || true)"

  if echo "$out" | grep -E "^\s*✗\s+(Node\.js|FFmpeg|FFprobe|Chrome)\b" >/dev/null; then
    echo "[preflight] Critical doctor check failed:"
    echo "$out" | grep -E "^\s*✗\s+(Node\.js|FFmpeg|FFprobe|Chrome)\b"
    return 1
  fi

  if [ "$mode" != "local" ]; then
    if echo "$out" | grep -E "^\s*✗\s+Docker(\s+running)?\b" >/dev/null; then
      echo "[preflight] Docker check failed (HF_RENDER_MODE=docker default):"
      echo "$out" | grep -E "^\s*✗\s+Docker(\s+running)?\b"
      echo "[preflight] To bypass: rerun with HF_RENDER_MODE=local"
      return 1
    fi
  fi

  echo "[preflight] hyperframes doctor OK (mode=$mode)"
  return 0
}
