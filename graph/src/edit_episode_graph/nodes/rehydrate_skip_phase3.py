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

from .._paths import EpisodePaths


def _strategy_json_path(slug: str) -> Path:
    return EpisodePaths(slug).edit_dir / "strategy.json"


# HOM-223 review: legacy strategy.json files (recorded pre-HOM-223) carry
# `source_path` (recording-machine absolute path) and may carry `skipped` /
# `skip_reason`. Filter these out before re-injecting into state so the
# rehydrated dict matches the post-HOM-223 contract that
# `p3_edl_select._strategy()` enforces for fingerprinting.
_DEPRECATED_STRATEGY_KEYS = frozenset({"source_path", "skipped", "skip_reason"})


def _clean_strategy(persisted: dict) -> dict:
    return {k: v for k, v in persisted.items() if k not in _DEPRECATED_STRATEGY_KEYS}


def rehydrate_skip_phase3_node(state: dict) -> dict:
    # HOM-334 Phase A.5: step-debug pre/post interrupts. No-op when
    # ``HOMESTUDIO_STEP_DEBUG`` is unset.
    from .._step_debug import is_enabled as _sd_enabled, wrap_deterministic_node

    if _sd_enabled():
        return wrap_deterministic_node(
            "rehydrate_skip_phase3",
            state=state,
            context={"slug": state.get("slug")},
            inner=lambda: _rehydrate_skip_phase3_body(state),
        )
    return _rehydrate_skip_phase3_body(state)


def _rehydrate_skip_phase3_body(state: dict) -> dict:
    slug = state.get("slug")
    if not slug:
        # No slug means upstream pickup failed — let routing short-circuit
        # naturally; nothing to rehydrate.
        return {}

    update: dict = {}
    notices: list[str] = []

    strategy_path = _strategy_json_path(slug)
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
            # HOM-223: `source_path` no longer echoed into state — the
            # canonical path lives at `EpisodePaths(slug).edit_dir / "strategy.json"`.
            # Filter deprecated keys (`source_path`, `skipped`, `skip_reason`)
            # so old recordings don't leak the recording-machine path back
            # into state. Mirrors `p3_edl_select._strategy()`.
            update["edit"] = {"strategy": _clean_strategy(persisted)}
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
