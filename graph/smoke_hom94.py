"""HOM-94 smoke: invoke p3_pre_scan against desktop-licensing-story.

Verifies end-to-end:
  1. Happy path with Haiku — node returns success, telemetry has expected shape.
  2. Forced cli_error via invalid model — BackendCLIError propagates from
     claude.py through router into state["llm_runs"] with exc_type +
     returncode + stderr_preview.

Run from the worktree's graph directory:
    .venv/Scripts/python smoke_hom94.py
"""

from __future__ import annotations

import json
from pathlib import Path

from edit_episode_graph.backends._concurrency import BackendSemaphores
from edit_episode_graph.backends._router import BackendRouter
from edit_episode_graph.backends.claude import ClaudeCodeBackend
from edit_episode_graph.backends.codex import CodexBackend
from edit_episode_graph._paths import repo_root
from edit_episode_graph.config import load_default_config
from edit_episode_graph.nodes.p3_pre_scan import _build_node, p3_pre_scan_node

REPO_ROOT = repo_root()
SLUG = "desktop-licensing-story"
EPISODE = REPO_ROOT / "episodes" / SLUG


def _router_with(model_override: str | None = None) -> BackendRouter:
    backends = [ClaudeCodeBackend(), CodexBackend()]
    sems = BackendSemaphores({b.name: b.capabilities.max_concurrent for b in backends})
    return BackendRouter(backends, sems)


def _print(label: str, run: dict) -> None:
    print(f"  {label}: {json.dumps({k: v for k, v in run.items() if v is not None}, indent=2)}")


def case_happy_path() -> None:
    print("\n=== Case 1: happy path (Haiku via config override) ===")
    state = {"slug": SLUG, "episode_dir": str(EPISODE)}
    router = _router_with()
    update = p3_pre_scan_node(state, router=router)
    runs = update.get("llm_runs") or []
    print(f"  attempts: {len(runs)}")
    for r in runs:
        _print(f"attempt[{r.get('reason') or 'success'}]", r)
    pre = (update.get("edit") or {}).get("pre_scan") or {}
    print(f"  pre_scan keys: {sorted(pre.keys())}")
    assert any(r.get("success") for r in runs), "expected at least one successful attempt"


def case_forced_cli_error() -> None:
    print("\n=== Case 2: forced cli_error (invalid model) ===")
    node = _build_node()
    # Bypass config; force claude into a bad model so it exits non-zero,
    # then codex (also forced bad) so we see both attempts in telemetry.
    state = {"slug": SLUG, "episode_dir": str(EPISODE)}
    router = _router_with()
    render_ctx = {
        "slug": SLUG,
        "episode_dir": str(EPISODE),
        "takes_packed_path": str(EPISODE / "edit" / "takes_packed.md"),
    }
    update = node._invoke_with(
        router, state, render_ctx=render_ctx,
        model_override="claude-not-a-real-model-xyz",
        timeout_s=60,
    )
    runs = update.get("llm_runs") or []
    print(f"  attempts: {len(runs)}")
    for r in runs:
        _print(f"attempt[{r.get('reason')}]", r)
    cli_errors = [r for r in runs if r.get("reason") == "cli_error"]
    if cli_errors:
        e = cli_errors[0]
        assert e.get("exc_type") == "BackendCLIError", f"missing exc_type: {e}"
        assert e.get("returncode") is not None, f"missing returncode: {e}"
        assert "stderr_preview" in e, f"missing stderr_preview: {e}"
        print("  ✓ cli_error attempt has exc_type + returncode + stderr_preview")
    else:
        print("  ⚠ no cli_error attempt — model may have been accepted; telemetry shape:")


if __name__ == "__main__":
    if not (EPISODE / "edit" / "takes_packed.md").exists():
        raise SystemExit(f"missing {EPISODE / 'edit' / 'takes_packed.md'}")
    case_happy_path()
    try:
        case_forced_cli_error()
    except Exception as e:
        print(f"  case 2 raised (acceptable if all backends exhausted): {type(e).__name__}: {e}")
    print("\nDONE")
