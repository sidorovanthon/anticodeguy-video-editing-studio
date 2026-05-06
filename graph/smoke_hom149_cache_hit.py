"""HOM-149 smoke — `p4_design_system` cache hit on identical input.

Builds a minimal one-node graph wrapping the real `p4_design_system_node`
with the real `CACHE_POLICY`, runs it twice on identical state, and
asserts:

  * Run 1: node body executes (we observe a real update, no `cached`
    metadata flag).
  * Run 2: node body is skipped — cache hit. LangGraph surfaces this
    via the per-step ``__metadata__.cached == True`` channel that only
    appears in ``graph.stream(..., stream_mode="updates")`` output (NOT
    in ``invoke()`` return value — verified against
    ``langgraph._internal._cache``).

Cost: $0. State is shaped so `p4_design_system_node` returns its early
``skipped=True`` branch (no LLM dispatch, no episode_dir required). The
cache wrapper still applies — that's the whole point: we're testing the
LangGraph cache mechanism end-to-end, not the node's LLM behaviour.

Run from worktree's `graph/` dir:

    .venv/Scripts/python smoke_hom149_cache_hit.py

The smoke uses an isolated tmp `SqliteCache` so it never touches
`graph/.cache/langgraph.db`.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from langgraph.cache.sqlite import SqliteCache
from langgraph.graph import END, START, StateGraph

from edit_episode_graph.nodes.p4_design_system import (
    CACHE_POLICY,
    p4_design_system_node,
)
from edit_episode_graph.state import GraphState


def _build_one_node_graph(cache_db: Path):
    g = StateGraph(GraphState)
    g.add_node("p4_design_system", p4_design_system_node, cache_policy=CACHE_POLICY)
    g.add_edge(START, "p4_design_system")
    g.add_edge("p4_design_system", END)
    return g.compile(cache=SqliteCache(path=str(cache_db)))


def _state() -> dict:
    # `p4_design_system_node` early-returns `skipped=True` when there is
    # no episode_dir AND/OR no EDL ranges. We trigger the first branch
    # so no LLM dispatch happens. Cache key only reads `slug` and
    # `transcripts.final_json_path` (absent → "absent" fingerprint).
    return {
        "slug": "hom149-smoke",
        "edit": {"edl": {"skipped": True, "ranges": []}},
        "transcripts": {},
    }


def _run_and_inspect(graph, label: str) -> bool:
    """Return True iff this run cache-hit on `p4_design_system`."""
    print(f"\n--- {label} ---")
    cached_seen = False
    for event in graph.stream(_state(), stream_mode="updates"):
        # `event` is `{node_name: update_dict, "__metadata__": {...}}` when
        # caching surfaces metadata; otherwise `{node_name: update_dict}`.
        meta = event.get("__metadata__") or {}
        cached_flag = bool(meta.get("cached"))
        node_keys = [k for k in event.keys() if k != "__metadata__"]
        print(f"  event: nodes={node_keys} cached={cached_flag} meta_keys={list(meta.keys())}")
        if cached_flag:
            cached_seen = True
    return cached_seen


def main() -> int:
    # See smoke_hom149_sqlite_pair.py for the Windows ignore_cleanup_errors note.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        cache_db = Path(td) / "smoke_cache.db"
        graph = _build_one_node_graph(cache_db)

        first_cached = _run_and_inspect(graph, "Run 1 (cold)")
        if first_cached:
            print("SMOKE FAIL: Run 1 reported cached=True (cache should be empty)", file=sys.stderr)
            return 1

        second_cached = _run_and_inspect(graph, "Run 2 (warm)")
        if not second_cached:
            print(
                "SMOKE FAIL: Run 2 did NOT report cached=True — "
                "CachePolicy/SqliteCache wiring broken",
                file=sys.stderr,
            )
            return 1

    print("\n✓ smoke_hom149_cache_hit PASS — cache hit observed on second run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
