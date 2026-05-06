"""HOM-132.3 smoke — Phase 3 LLM nodes cache-hit on identical input.

Mirrors `smoke_hom150_p4_cache.py`: builds a 5-node chain wrapping the
real Phase 3 LLM nodes (`p3_pre_scan`, `p3_strategy`, `p3_edl_select`,
`p3_self_eval`, `p3_persist_session`) with their real `CACHE_POLICY`
values, runs it twice on identical state, and asserts:

  * Run 1: every node executes (no `cached` metadata flag).
  * Run 2: every node cache-hits — LangGraph surfaces this via
    ``__metadata__.cached == True`` in ``stream_mode="updates"`` events.

Cost: $0. State is shaped so each node returns its early ``skipped=True``
branch (no `episode_dir` / no upstream artifacts), so no LLM dispatch
fires. The cache wrapper still applies — that's the whole point.

Additional assertions per HOM-151 DoD:
  * `takes_packed.md` content edit (Run 3) → `p3_pre_scan`,
    `p3_strategy`, `p3_edl_select` cache-miss; `p3_self_eval` and
    `p3_persist_session` (which key on `final.mp4`/`edl.json`) stay cached.
  * `gate_results` mutation (Run 4) — append a fake `gate:eval_ok` record
    so `_eval_iteration` shifts → `p3_self_eval` cache-misses (validates
    the iteration `extras=` per spec §6).

Run from worktree's `graph/` dir:

    PYTHONPATH=src .venv/Scripts/python smoke_hom132_3_p3_cache.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from langgraph.cache.sqlite import SqliteCache
from langgraph.graph import END, START, StateGraph

from edit_episode_graph.nodes.p3_edl_select import (
    CACHE_POLICY as p3_edl_select_cache_policy,
    p3_edl_select_node,
)
from edit_episode_graph.nodes.p3_persist_session import (
    CACHE_POLICY as p3_persist_session_cache_policy,
    p3_persist_session_node,
)
from edit_episode_graph.nodes.p3_pre_scan import (
    CACHE_POLICY as p3_pre_scan_cache_policy,
    p3_pre_scan_node,
)
from edit_episode_graph.nodes.p3_self_eval import (
    CACHE_POLICY as p3_self_eval_cache_policy,
    p3_self_eval_node,
)
from edit_episode_graph.nodes.p3_strategy import (
    CACHE_POLICY as p3_strategy_cache_policy,
    p3_strategy_node,
)
from edit_episode_graph.state import GraphState


_CACHED_NODES = (
    "p3_pre_scan",
    "p3_strategy",
    "p3_edl_select",
    "p3_self_eval",
    "p3_persist_session",
)


def _build_chain_graph(cache_db: Path):
    g = StateGraph(GraphState)
    g.add_node("p3_pre_scan", p3_pre_scan_node, cache_policy=p3_pre_scan_cache_policy)
    g.add_node("p3_strategy", p3_strategy_node, cache_policy=p3_strategy_cache_policy)
    g.add_node(
        "p3_edl_select", p3_edl_select_node, cache_policy=p3_edl_select_cache_policy
    )
    g.add_node(
        "p3_self_eval", p3_self_eval_node, cache_policy=p3_self_eval_cache_policy
    )
    g.add_node(
        "p3_persist_session",
        p3_persist_session_node,
        cache_policy=p3_persist_session_cache_policy,
    )
    g.add_edge(START, "p3_pre_scan")
    g.add_edge("p3_pre_scan", "p3_strategy")
    g.add_edge("p3_strategy", "p3_edl_select")
    g.add_edge("p3_edl_select", "p3_self_eval")
    g.add_edge("p3_self_eval", "p3_persist_session")
    g.add_edge("p3_persist_session", END)
    return g.compile(cache=SqliteCache(path=str(cache_db)))


def _state(takes_packed: str | None, *, gate_results: list | None = None) -> dict:
    """State that triggers `skipped=True` on every node — no LLM dispatch.

    `transcripts.takes_packed_path` IS read by `p3_strategy`/`p3_edl_select`
    cache keys; we route both to the same sentinel file so a Run-3 mutation
    invalidates them via content hash. No `episode_dir` is set, so every
    node body early-returns.
    """
    return {
        "slug": "hom151-smoke",
        "transcripts": {"takes_packed_path": takes_packed or ""},
        "edit": {
            "pre_scan": {"slips": []},
            "strategy": {},
            "edl": {"skipped": True, "ranges": []},
            "render": {"skipped": True},
            "eval": {},
        },
        "gate_results": gate_results or [],
    }


def _run_and_inspect(graph, state: dict, label: str) -> dict[str, bool]:
    print(f"\n--- {label} ---")
    seen: dict[str, bool] = {}
    for event in graph.stream(state, stream_mode="updates"):
        meta = event.get("__metadata__") or {}
        cached_flag = bool(meta.get("cached"))
        node_keys = [k for k in event.keys() if k != "__metadata__"]
        for n in node_keys:
            if n in _CACHED_NODES:
                seen[n] = seen.get(n, False) or cached_flag
        print(f"  event: nodes={node_keys} cached={cached_flag}")
    return seen


def main() -> int:
    # ignore_cleanup_errors=True per HOM-149 Windows handle-release note.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        cache_db = Path(td) / "smoke_cache.db"
        takes = Path(td) / "takes_packed.md"
        takes.write_text("# initial takes\n", encoding="utf-8")

        graph = _build_chain_graph(cache_db)

        # Run 1 — cold cache.
        cold = _run_and_inspect(graph, _state(str(takes)), "Run 1 (cold)")
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
                f"SMOKE FAIL: Run 1 missing events for {missing}",
                file=sys.stderr,
            )
            return 1

        # Run 2 — warm cache, identical input.
        warm = _run_and_inspect(graph, _state(str(takes)), "Run 2 (warm)")
        warm_misses = [n for n in _CACHED_NODES if not warm.get(n)]
        if warm_misses:
            print(
                f"SMOKE FAIL: Run 2 did NOT cache-hit for {warm_misses}",
                file=sys.stderr,
            )
            return 1

        # Run 3 — edit takes_packed.md → only the three takes-dependent
        # nodes invalidate. p3_self_eval / p3_persist_session key on
        # final.mp4 + edl.json (both "absent" here, fingerprint stable).
        takes.write_text("# mutated takes\n", encoding="utf-8")
        edited = _run_and_inspect(
            graph, _state(str(takes)), "Run 3 (after takes_packed.md edit)"
        )
        takes_dependent = ("p3_pre_scan", "p3_strategy", "p3_edl_select")
        stuck = [n for n in takes_dependent if edited.get(n)]
        if stuck:
            print(
                f"SMOKE FAIL: Run 3 cache-hit on takes-dependent {stuck} "
                "after takes_packed.md content change — invalidation broken",
                file=sys.stderr,
            )
            return 1
        downstream_should_hit = ("p3_self_eval", "p3_persist_session")
        downstream_missed = [n for n in downstream_should_hit if not edited.get(n)]
        if downstream_missed:
            print(
                f"SMOKE FAIL: Run 3 cache-missed {downstream_missed} — "
                "their key (final.mp4, edl.json) did not change",
                file=sys.stderr,
            )
            return 1

        # Run 4 — bump self-eval iteration via a fake gate_results entry.
        # Validates `extras=(_eval_iteration,)` per spec §6.
        gate_results = [{"gate": "gate:eval_ok", "passed": False}]
        bumped = _run_and_inspect(
            graph,
            _state(str(takes), gate_results=gate_results),
            "Run 4 (gate_results bump → iteration shift)",
        )
        if bumped.get("p3_self_eval"):
            print(
                "SMOKE FAIL: Run 4 cache-hit p3_self_eval after gate_results "
                "shift — `extras=(iteration,)` not honoured",
                file=sys.stderr,
            )
            return 1
        # p3_persist_session ALSO renders `iteration` in its brief but the
        # current spec extras don't include it explicitly — strategy/edl/eval
        # in-memory fingerprints DO change when state changes. Here we only
        # changed gate_results, so persist_session's extras are stable; it
        # SHOULD cache-hit. (If a future amendment adds iteration to its
        # extras, flip this assertion.)
        if not bumped.get("p3_persist_session"):
            print(
                "SMOKE FAIL: Run 4 cache-missed p3_persist_session — extras "
                "shouldn't have changed (only gate_results did)",
                file=sys.stderr,
            )
            return 1

    print(
        "\n[OK] smoke_hom132_3_p3_cache PASS — all 5 P3 LLM nodes cache-hit on "
        "warm re-run; takes-dependent nodes invalidate on takes_packed.md edit; "
        "p3_self_eval invalidates on iteration bump per spec §6 extras."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
