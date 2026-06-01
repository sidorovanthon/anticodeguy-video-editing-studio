"""YAML config loader for backend preferences + per-node overrides.

Schema is intentionally permissive (plain dicts, no Pydantic) so tweaking the
file is low-friction. `RouterConfig.resolve_node(name)` returns the merged
NodeConfig for a given node name, applying explicit-key match first, then the
first matching glob.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@dataclass
class NodeConfig:
    tier: str
    backend_preference: list[str]
    timeout_s: int
    model: str | None = None   # optional override; bypasses backend's tier→model map


@dataclass
class RouterConfig:
    backend_preference: list[str]
    concurrency: dict[str, int]
    defaults: dict[str, Any]
    node_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    # HOM-212: per-gate deterministic config (thresholds, carve-out lists).
    # Keyed by gate name without the `gate:` prefix, e.g. `animation_map`.
    # Values are plain dicts; each gate decides its own schema. Kept separate
    # from `node_overrides` because deterministic-gate config is not LLM-tier
    # routing and re-using NodeConfig would conflate the two surfaces.
    gates: dict[str, dict[str, Any]] = field(default_factory=dict)
    # HOM-166: project-default profile/brand selection (spec §6). Resolution
    # priority is CLI/override > intent.yaml > THESE defaults. canonical profile
    # forces brand_id=None regardless.
    default_profile_id: str = "talking-head-portrait"
    default_brand_id: str = "anticodeguy"

    def resolve_gate(self, name: str) -> dict[str, Any]:
        """Returns the (possibly empty) config dict for a given gate name.

        Gate name is the bare suffix (e.g. ``animation_map``), not the
        canonical ``gate:animation_map`` form — the YAML key matches the
        Python module name under ``gates/``. Missing keys return ``{}``,
        leaving the gate to apply its hard-coded defaults.
        """
        return dict(self.gates.get(name) or {})

    def resolve_node(self, name: str) -> NodeConfig:
        override = self.node_overrides.get(name)
        if override is None:
            for pat, val in self.node_overrides.items():
                if fnmatch(name, pat):
                    override = val
                    break
        override = override or {}
        return NodeConfig(
            tier=override.get("tier", "cheap"),
            backend_preference=override.get("backend_preference", self.backend_preference),
            timeout_s=int(override.get("timeout_s", self.defaults.get("timeout_s", 120))),
            model=override.get("model"),
        )


def load_config(path: Path) -> RouterConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return RouterConfig(
        backend_preference=list(raw.get("backend_preference") or []),
        concurrency=dict(raw.get("concurrency") or {}),
        defaults=dict(raw.get("defaults") or {}),
        node_overrides=dict(raw.get("node_overrides") or {}),
        gates=dict(raw.get("gates") or {}),
        default_profile_id=str(raw.get("default_profile_id") or "talking-head-portrait"),
        default_brand_id=str(raw.get("default_brand_id") or "anticodeguy"),
    )


_REPO_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


@lru_cache(maxsize=1)
def load_default_config() -> RouterConfig:
    """Loads `graph/config.yaml`. Returns a permissive default if file is absent.

    Cached: hot-path callers (`LLMNode.__call__`) hit this once per fan-out beat.
    `langgraph dev`'s reload mechanism imports a fresh module on file change, so
    config tunings take effect on dev restart. Tests that mutate the file should
    call `load_default_config.cache_clear()`.
    """
    if _REPO_CONFIG_PATH.exists():
        return load_config(_REPO_CONFIG_PATH)
    return RouterConfig(
        backend_preference=["claude", "codex"],
        concurrency={"claude": 2, "codex": 2, "gemini": 3},
        defaults={"timeout_s": 120},
        node_overrides={},
    )
