"""rehydrate_skip_phase3 — load Phase 3 outputs from disk on the skip path.

When ``route_after_preflight`` short-circuits Phase 3 (because ``final.mp4``
already exists from a prior run), the in-memory channels for ``edit.strategy``
remain empty on a fresh thread. Phase 4 cache keys that fingerprint
``state.edit.strategy`` then diverge from the cached values written when
Phase 3 actually ran — every Phase 4 LLM node misses cache and re-executes.

This deterministic node sits on the skip edge between ``preflight_canon``
and ``glue_remap_transcript``. It reads ``<edit>/strategy.json`` (persisted
by ``p3_strategy``) into ``state.edit.strategy``. Missing file = legacy
episode produced before HOM-160 landed; we emit a notice and let downstream
miss cache (current behaviour). New runs persist the snapshot, so the next
re-run benefits.

Spec: HOM-160 / blocker for §17 acceptance of
``2026-05-07-resolved-brief-profiles-brand-architecture.md``. Architectural
direction: Phase 3 outputs become on-disk artifacts so phase-skip routing
restores them losslessly — same direction as M6's ``brief.resolved.yaml``.
"""

from __future__ import annotations

import json
from pathlib import Path


def _strategy_json_path(episode_dir: str) -> Path:
    return Path(episode_dir) / "edit" / "strategy.json"


def rehydrate_skip_phase3_node(state: dict) -> dict:
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        # No episode_dir means upstream pickup failed — let routing
        # short-circuit naturally; nothing to rehydrate.
        return {}

    update: dict = {}
    notices: list[str] = []

    strategy_path = _strategy_json_path(episode_dir)
    if strategy_path.exists():
        try:
            persisted = json.loads(strategy_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            notices.append(
                f"rehydrate_skip_phase3: strategy.json unreadable ({exc}); "
                "Phase 4 nodes will cache-miss until Phase 3 re-runs"
            )
            persisted = None
        if isinstance(persisted, dict):
            persisted["source_path"] = str(strategy_path)
            update["edit"] = {"strategy": persisted}
            notices.append(
                f"rehydrate_skip_phase3: restored strategy from {strategy_path.name}"
            )
    else:
        notices.append(
            "rehydrate_skip_phase3: no strategy.json on disk (legacy episode "
            "or first re-run after HOM-160); Phase 4 cache keys may diverge"
        )

    if notices:
        update["notices"] = notices
    return update
