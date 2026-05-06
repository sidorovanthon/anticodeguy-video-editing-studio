"""HOM-149 sanity smoke — `SqliteCache + SqliteSaver` cross-thread hit.

Originally framed as a blocking gate for [LangGraph #5980] which flagged
``InMemoryCache + InMemorySaver`` as cache-missing every run. Independent
canon-check (2026-05-06; see spec §4) confirmed #5980 was closed
2025-09-16 as not-a-bug — the recommended resolution is exactly the
``key_func`` override we ship in `_caching.make_key`. This smoke is
therefore a **non-blocking sanity check** that the same pattern holds
when both stores are SQLite-backed; if it ever fails the epic halts and
we file an upstream issue (spec §10, §11).

Cost: $0. Single noop node, one boolean flip in the result dict, no
LLM dispatch.

Run from worktree's `graph/` dir:

    .venv/Scripts/python smoke_hom149_sqlite_pair.py

Uses tmp dirs for both the cache DB and the checkpointer DB so the
real `graph/.cache/langgraph.db` is untouched.

[LangGraph #5980]: https://github.com/langchain-ai/langgraph/issues/5980
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import TypedDict

from langgraph.cache.sqlite import SqliteCache
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import CachePolicy


class _S(TypedDict, total=False):
    n: int
    seen: list[str]


_calls = 0


def _noop(state: _S) -> dict:
    global _calls
    _calls += 1
    return {"seen": [*(state.get("seen") or []), f"call#{_calls}"]}


def _key(_state, *_a, **_k) -> str:
    return "fixed-key"


def main() -> int:
    global _calls
    # ignore_cleanup_errors: SqliteCache (and SqliteSaver) keep file handles
    # open for the lifetime of the compiled graph; on Windows the cleanup
    # races the still-open .db files. Tests pass before cleanup; we don't
    # care if temp survives.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        cache_db = Path(td) / "cache.db"
        ckpt_db = Path(td) / "checkpoints.sqlite"
        # SqliteSaver context manager is the only public way to construct one
        # against a file; reuse the same connection for both runs (different
        # threads).
        with SqliteSaver.from_conn_string(str(ckpt_db)) as saver:
            g = StateGraph(_S)
            g.add_node("noop", _noop, cache_policy=CachePolicy(key_func=_key))
            g.add_edge(START, "noop")
            g.add_edge("noop", END)
            graph = g.compile(checkpointer=saver, cache=SqliteCache(path=str(cache_db)))

            cfg_a = {"configurable": {"thread_id": "thread-a"}}
            cfg_b = {"configurable": {"thread_id": "thread-b"}}

            print("--- Run on thread-a (cold) ---")
            calls_before = _calls
            cached_a = False
            for ev in graph.stream({"n": 1}, config=cfg_a, stream_mode="updates"):
                cached_a = cached_a or bool((ev.get("__metadata__") or {}).get("cached"))
                print(f"  event keys={list(ev.keys())} cached={cached_a}")
            if _calls != calls_before + 1:
                print(f"SMOKE FAIL: noop body should have run once on cold thread; ran {_calls - calls_before} times", file=sys.stderr)
                return 1

            print("--- Run on thread-b (different thread, identical input) ---")
            calls_before = _calls
            cached_b = False
            for ev in graph.stream({"n": 1}, config=cfg_b, stream_mode="updates"):
                cached_b = cached_b or bool((ev.get("__metadata__") or {}).get("cached"))
                print(f"  event keys={list(ev.keys())} cached={cached_b}")

            if not cached_b:
                print(
                    "SMOKE FAIL (sanity, non-blocking): cross-thread cache hit "
                    "did not surface — investigate before HOM-132.2.",
                    file=sys.stderr,
                )
                return 1
            if _calls != calls_before:
                print(f"SMOKE FAIL: noop body re-ran on thread-b ({_calls - calls_before} extra call/s) despite cache=True", file=sys.stderr)
                return 1

    print("\n✓ smoke_hom149_sqlite_pair PASS — SqliteCache+SqliteSaver cross-thread hit OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
