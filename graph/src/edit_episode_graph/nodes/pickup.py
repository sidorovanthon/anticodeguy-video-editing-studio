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


def _parse(stdout: str) -> dict:
    parsed = json.loads(stdout)
    return {
        "slug": parsed["slug"],
        "episode_dir": parsed["episode_dir"],
        "pickup": {
            "raw_path": parsed.get("raw_path"),
            "script_path": parsed.get("script_path"),
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
