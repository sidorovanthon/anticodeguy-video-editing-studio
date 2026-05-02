"""Pickup node — wraps `scripts/pickup.py` via the deterministic-node factory."""

import json
import sys
from pathlib import Path

from ._deterministic import deterministic_node

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _cmd(state) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "scripts.pickup",
        "--inbox",
        "inbox",
        "--episodes",
        "episodes",
    ]
    if state.get("slug"):
        cmd += ["--slug", state["slug"]]
    return cmd


def _abs(p: str | None) -> str | None:
    """Resolve `p` against PROJECT_ROOT if relative; pass through None.

    `scripts/pickup.py` emits paths relative to the orchestrator root (its own
    cwd at run time). Conditional-edge routing functions in `nodes/_routing.py`
    run *in-process* inside `langgraph dev`, whose cwd is wherever the user
    invoked it from — not necessarily PROJECT_ROOT. Absolutizing here makes
    every downstream consumer (routing, subprocess wrappers) cwd-independent.
    """
    if p is None:
        return None
    pp = Path(p)
    return str(pp if pp.is_absolute() else (PROJECT_ROOT / pp).resolve())


def _parse(stdout: str) -> dict:
    parsed = json.loads(stdout)
    return {
        "slug": parsed["slug"],
        "episode_dir": _abs(parsed["episode_dir"]),
        "pickup": {
            "raw_path": _abs(parsed.get("raw_path")),
            "script_path": _abs(parsed.get("script_path")),
            "resumed": parsed.get("resumed", False),
            "idle": parsed.get("idle", False),
            "warning": parsed.get("warning"),
        },
    }


pickup_node = deterministic_node(
    name="pickup",
    cmd_factory=_cmd,
    parser=_parse,
    cwd=PROJECT_ROOT,
)
