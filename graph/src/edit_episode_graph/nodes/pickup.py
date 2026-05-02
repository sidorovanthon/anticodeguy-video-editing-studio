"""Pickup node — wraps `scripts/pickup.py` via subprocess.

v0's only functional node. Reads the inbox, moves the raw container into
`episodes/<slug>/`, and records the resulting paths in graph state.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def pickup_node(state):
    cmd = [sys.executable, "-m", "scripts.pickup", "--inbox", "inbox", "--episodes", "episodes"]
    if state.get("slug"):
        cmd += ["--slug", state["slug"]]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        return {"errors": [{"node": "pickup", "message": result.stderr, "timestamp": _now()}]}

    parsed = json.loads(result.stdout)
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
