"""HOM-150 smoke — Phase 4 LLM nodes cache-hit on identical input.

Builds a 5-node graph wrapping the real Phase 4 LLM nodes
(`p4_prompt_expansion`, `p4_plan`, `p4_beat`, `p4_captions_layer`,
`p4_persist_session`) with their real `CACHE_POLICY` values, runs it
twice on identical state, and asserts:

  * Run 1: every node executes (no `cached` metadata flag).
  * Run 2: every node cache-hits — LangGraph surfaces this via the
    per-step ``__metadata__.cached == True`` channel that only appears
    in ``graph.stream(..., stream_mode="updates")`` output.

Cost: $0. State is shaped so each node returns its early ``skipped=True``
branch (no `episode_dir` / no upstream artifacts), so no LLM dispatch
fires. The cache wrapper still applies — that's the whole point: we're
testing the LangGraph cache mechanism end-to-end across all five nodes,
not their LLM behaviour.

Edit-invalidation smoke: a third run with a sentinel file mutated
between runs is exercised to confirm content-hash invalidation
propagates per spec §6.

Run from worktree's `graph/` dir:

    PYTHONPATH=src .venv/Scripts/python smoke_hom150_p4_cache.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from langgraph.cache.sqlite import SqliteCache
from langgraph.graph import END, START, StateGraph

from edit_episode_graph.nodes.p4_beat import (
    CACHE_POLICY as p4_beat_cache_policy,
    p4_beat_node,
)
from edit_episode_graph.nodes.p4_captions_layer import (
    CACHE_POLICY as p4_captions_layer_cache_policy,
    p4_captions_layer_node,
)
from edit_episode_graph.nodes.p4_persist_session import (
    CACHE_POLICY as p4_persist_session_cache_policy,
    p4_persist_session_node,
)
from edit_episode_graph.nodes.p4_plan import (
    CACHE_POLICY as p4_plan_cache_policy,
    p4_plan_node,
)
from edit_episode_graph.nodes.p4_prompt_expansion import (
    CACHE_POLICY as p4_prompt_expansion_cache_policy,
    p4_prompt_expansion_node,
)
from edit_episode_graph.state import GraphState


_CACHED_NODES = (
    "p4_prompt_expansion",
    "p4_plan",
    "p4_beat",
    "p4_captions_layer",
    "p4_persist_session",
)


def _build_chain_graph(cache_db: Path):
    """Assemble all 5 cached nodes in a linear chain off START.

    Each node short-circuits via its own `skipped` branch (no episode_dir
    / no upstream files), so the chain runs cheaply but exercises every
    cache wrapper. We don't recreate the production topology — only the
    cache mechanism is under test.
    """
    g = StateGraph(GraphState)
    g.add_node(
        "p4_prompt_expansion",
        p4_prompt_expansion_node,
        cache_policy=p4_prompt_expansion_cache_policy,
    )
    g.add_node("p4_plan", p4_plan_node, cache_policy=p4_plan_cache_policy)
    g.add_node("p4_beat", p4_beat_node, cache_policy=p4_beat_cache_policy)
    g.add_node(
        "p4_captions_layer",
        p4_captions_layer_node,
        cache_policy=p4_captions_layer_cache_policy,
    )
    g.add_node(
        "p4_persist_session",
        p4_persist_session_node,
        cache_policy=p4_persist_session_cache_policy,
    )
    g.add_edge(START, "p4_prompt_expansion")
    g.add_edge("p4_prompt_expansion", "p4_plan")
    g.add_edge("p4_plan", "p4_beat")
    g.add_edge("p4_beat", "p4_captions_layer")
    g.add_edge("p4_captions_layer", "p4_persist_session")
    g.add_edge("p4_persist_session", END)
    return g.compile(cache=SqliteCache(path=str(cache_db)))


def _state(design_md_path: str | None) -> dict:
    """State that triggers `skipped=True` on every node — no LLM dispatch.

    Each node's body checks for `episode_dir` / upstream paths and bails
    out early; the cache key, however, IS computed against this state, so
    identical-state re-runs hit the cache wrapper.

    `design_md_path` is included so the edit-invalidation run can mutate
    a real file and observe the content-hash changing the cache key for
    every node that lists it in `files=`.
    """
    return {
        "slug": "hom150-smoke",
        # Intentionally NO episode_dir — every node early-returns.
        "compose": {
            "design_md_path": design_md_path or "",
            "expanded_prompt_path": "",
            "style_request": "",
        },
        "transcripts": {},
        "edit": {"edl": {"skipped": True, "ranges": []}},
        "_beat_dispatch": {"scene_id": "hook"},
    }


def _run_and_inspect(graph, state: dict, label: str) -> dict[str, bool]:
    """Run the graph once; return {node_name: cached_flag} for each node we care about."""
    print(f"\n--- {label} ---")
    seen: dict[str, bool] = {}
    for event in graph.stream(state, stream_mode="updates"):
        meta = event.get("__metadata__") or {}
        cached_flag = bool(meta.get("cached"))
        node_keys = [k for k in event.keys() if k != "__metadata__"]
        for n in node_keys:
            if n in _CACHED_NODES:
                # If a node fires multiple times (it shouldn't here), prefer the
                # cached=True observation — that's what we're testing for.
                seen[n] = seen.get(n, False) or cached_flag
        print(f"  event: nodes={node_keys} cached={cached_flag}")
    return seen


def main() -> int:
    # See smoke_hom149_sqlite_pair.py for the Windows ignore_cleanup_errors note.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        cache_db = Path(td) / "smoke_cache.db"
        # Sentinel design_md file used to exercise content-hash invalidation.
        design_md = Path(td) / "DESIGN.md"
        design_md.write_text("# initial palette", encoding="utf-8")

        graph = _build_chain_graph(cache_db)

        # Run 1 — cold cache.
        cold = _run_and_inspect(graph, _state(str(design_md)), "Run 1 (cold)")
        cold_misses = [n for n in _CACHED_NODES if cold.get(n)]
        if cold_misses:
            print(
                f"SMOKE FAIL: Run 1 reported cached=True for {cold_misses} "
                "(cache should be empty)",
                file=sys.stderr,
            )
            return 1
        if not all(n in cold for n in _CACHED_NODES):
            missing = [n for n in _CACHED_NODES if n not in cold]
            print(
                f"SMOKE FAIL: Run 1 missing events for {missing} — "
                "topology / state shape is wrong",
                file=sys.stderr,
            )
            return 1

        # Run 2 — warm cache, identical input.
        warm = _run_and_inspect(graph, _state(str(design_md)), "Run 2 (warm)")
        warm_misses = [n for n in _CACHED_NODES if not warm.get(n)]
        if warm_misses:
            print(
                f"SMOKE FAIL: Run 2 did NOT cache-hit for {warm_misses} — "
                "CachePolicy/SqliteCache wiring broken on those nodes",
                file=sys.stderr,
            )
            return 1

        # Run 3 — edit DESIGN.md → content hash changes → invalidates every
        # node whose `files=` includes design_md_path. Per spec §6, that's
        # all four content-driven nodes (everything except p4_persist_session,
        # which keys on index_html_path only).
        design_md.write_text("# mutated palette", encoding="utf-8")
        edited = _run_and_inspect(graph, _state(str(design_md)), "Run 3 (after DESIGN.md edit)")
        design_dependent = (
            "p4_prompt_expansion",
            "p4_plan",
            "p4_beat",
            "p4_captions_layer",
        )
        stuck = [n for n in design_dependent if edited.get(n)]
        if stuck:
            print(
                f"SMOKE FAIL: Run 3 cache-hit on design-dependent nodes "
                f"{stuck} after DESIGN.md content change — invalidation broken",
                file=sys.stderr,
            )
            return 1
        # p4_persist_session keys on index_html_path (absent here, "absent"
        # fingerprint stable) — it SHOULD still cache-hit.
        if not edited.get("p4_persist_session"):
            print(
                "SMOKE FAIL: Run 3 cache-missed p4_persist_session — its "
                "key (slug, index_html_path) did not change, expected hit",
                file=sys.stderr,
            )
            return 1

    print(
        "\n✓ smoke_hom150_p4_cache PASS — all 5 P4 LLM nodes cache-hit on warm "
        "re-run; design-dependent nodes invalidate on DESIGN.md edit; "
        "persist_session stays cached (correct — keys on index_html_path)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
