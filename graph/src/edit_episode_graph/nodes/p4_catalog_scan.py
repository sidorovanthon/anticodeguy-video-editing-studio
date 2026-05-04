"""p4_catalog_scan node — wraps `npx hyperframes catalog --json`.

Deterministic class-1 node (per spec §6.1). Discovers the registry of
HyperFrames blocks and components so downstream Phase 4 nodes can pick
catalog-shipped assets over hand-rolled ones (HF SKILL.md house rule —
catalog scan is an orchestrator-house gate; per-beat justification belongs
in DESIGN.md, see memory `feedback_hf_catalog_orchestrator_gate`).

Output shape: parses the CLI's flat JSON array into
`{blocks: [...], components: [...], fetched_at: <iso>}` so consumers
don't repeat the type-split. Items pass through with their CLI-given
fields (name/title/description/tags/dimensions/duration); we don't
schema-narrow because the registry adds fields over time and clipping
upstream additions silently is worse than tolerating extras.

The CLI is currently global (the `npx hyperframes` registry) so cwd
doesn't materially affect output, but we still run inside the episode's
`hyperframes/` directory: that's where any future per-project registry
overrides will land, and it surfaces "scaffold ran first" as a precondition
(`hyperframes/` must exist).
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(message: str) -> dict:
    return {
        "errors": [
            {"node": "p4_catalog_scan", "message": message, "timestamp": _now()},
        ]
    }


def _split_items(items: list) -> dict:
    blocks: list[dict] = []
    components: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        if kind == "block":
            blocks.append(item)
        elif kind == "component":
            components.append(item)
        # Unknown types ignored — registry may add new categories.
    return {"blocks": blocks, "components": components, "fetched_at": _now()}


def parse_catalog_stdout(stdout: str) -> dict:
    """Parse `npx hyperframes catalog --json` stdout into a CatalogReport.

    Raises `ValueError` if stdout is not a JSON array.
    """
    parsed = json.loads(stdout)
    if not isinstance(parsed, list):
        raise ValueError(
            f"expected JSON array from `hyperframes catalog --json`, got {type(parsed).__name__}"
        )
    return _split_items(parsed)


def p4_catalog_scan_node(state):
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return _error("episode_dir missing from state (pickup must run first)")
    hf_dir = Path(episode_dir) / "hyperframes"
    if not hf_dir.is_dir():
        return _error(f"hyperframes/ directory missing at {hf_dir} (p4_scaffold must run first)")
    try:
        result = subprocess.run(
            ["npx", "hyperframes", "catalog", "--json"],
            cwd=hf_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            shell=(sys.platform == "win32"),
        )
    except OSError as exc:
        return _error(f"npx hyperframes catalog failed to spawn: {exc!r}")
    if result.returncode != 0:
        combined = "\n".join(s for s in (result.stderr, result.stdout) if s).strip()
        return _error(combined or f"exit code {result.returncode}, no output")
    try:
        report = parse_catalog_stdout(result.stdout)
    except Exception as exc:
        return _error(
            f"parser error: {exc!r}\n--- stdout ---\n{result.stdout[:2000]}"
        )
    return {"compose": {"catalog": report}}
