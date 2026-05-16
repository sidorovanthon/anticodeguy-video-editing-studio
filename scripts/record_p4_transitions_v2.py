"""One-shot recorder for the HOM-259 p4_transitions v2 cache row.

The standard ``scripts/record_fixture`` driver cannot reach
``p4_transitions`` after HOM-259's ``_CACHE_VERSION`` bump because
``route_after_remap`` short-circuits to END whenever
``hyperframes/index.html`` is present on disk (the committed fixture
pins it there) and deleting the file does not help — ``p4_scaffold``
cache-hits and skips the ``npx hyperframes init`` subprocess that
would have re-created it.

This driver uses LangGraph's native midpoint-dispatch primitive
(``compiled.update_state(config, values, as_node="p4_assemble_index")``
+ ``compiled.invoke(None, config)``) to inject the post-assemble state
reconstructed from the existing fixture cache.db, then lets the
graph runtime advance from ``route_after_assemble_index`` onwards.
``p4_transitions`` runs (v2 cache miss → fresh record), then the
gate cluster, persist, and materializer all cache-hit on their
existing rows or are themselves deterministic. The whole flow lands
exactly one new cache row (``p4_transitions``) and updates any
downstream rows whose keys changed.

Native primitive contract (CLAUDE.md §"LangGraph primitives"):
``update_state(as_node=…)`` + ``invoke(None)`` is the canonical
midpoint-dispatch mechanism — see
https://docs.langchain.com/oss/python/langgraph/use-graph-api#update-graph-state .
No script-level cache writes; full Pregel observability preserved.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_WORKTREE = Path(__file__).resolve().parents[1]
os.environ["HOMESTUDIO_PROJECT_ROOT"] = str(_WORKTREE / "tests" / "fixtures")

_GRAPH_SRC = _WORKTREE / "graph" / "src"
if _GRAPH_SRC.is_dir() and str(_GRAPH_SRC) not in sys.path:
    sys.path.insert(0, str(_GRAPH_SRC))
if str(_WORKTREE) not in sys.path:
    sys.path.insert(0, str(_WORKTREE))


def main() -> int:
    from langgraph.checkpoint.memory import InMemorySaver

    from edit_episode_graph import graph as graph_mod
    from edit_episode_graph._paths import project_root
    from tests._helpers.materialize_into_tmpdir import _reconstruct_state
    from tests._helpers.replay_harness import (
        finalize_record_on_miss,
        mount_fixture_cache,
        open_cache,
    )

    slug = "canonical-portrait-talking-head"
    fixture_root = _WORKTREE / "tests" / "fixtures"
    episode_dir = fixture_root / "episodes" / slug
    cache_db = episode_dir / "cache.db"
    if not cache_db.is_file():
        print(f"[record-transitions] FATAL: cache.db missing at {cache_db}", file=sys.stderr)
        return 2

    print(f"[record-transitions] HOMESTUDIO_PROJECT_ROOT = {os.environ['HOMESTUDIO_PROJECT_ROOT']}")
    print(f"[record-transitions] project_root()         = {project_root()}")

    state = _reconstruct_state(slug, episode_dir)
    state["slug"] = slug
    state.setdefault("episode_dir", str(episode_dir))
    body = (state.get("compose") or {}).get("index_html")
    if not isinstance(body, str) or not body:
        print(
            "[record-transitions] FATAL: state.compose.index_html missing — "
            "p4_assemble_index recording did not carry body string. Re-record "
            "of HOM-241 likely needed first.",
            file=sys.stderr,
        )
        return 3
    plan = (state.get("compose") or {}).get("plan") or {}
    print(
        f"[record-transitions] reconstructed: "
        f"{len(plan.get('beats') or [])} beats, "
        f"{len(plan.get('transitions') or [])} transitions, "
        f"index_html={len(body)} chars"
    )

    mounted = mount_fixture_cache(slug, mode="record-on-miss", fixtures_root=fixture_root)
    print(f"[record-transitions] mounted cache mode={mounted.mode}")
    print(f"[record-transitions]   working_path={mounted.working_path}")
    print(f"[record-transitions]   fixture_path={mounted.fixture_path}")
    cache = open_cache(mounted)

    saver = InMemorySaver()
    compiled = graph_mod.build_graph_uncompiled().compile(cache=cache, checkpointer=saver)

    thread_id = f"hom-259-record-{int(time.time())}"
    cfg = {"configurable": {"thread_id": thread_id}, "recursion_limit": 200}
    print(f"[record-transitions] thread_id={thread_id}")

    try:
        # Seed checkpoint as if p4_assemble_index just completed with our
        # reconstructed state. LangGraph then follows the outgoing edge
        # (route_after_assemble_index → p4_transitions) on invoke(None).
        compiled.update_state(cfg, values=state, as_node="p4_assemble_index")
        print("[record-transitions] update_state(as_node=p4_assemble_index) ok")

        started = time.time()
        final = compiled.invoke(None, config=cfg)
        elapsed = time.time() - started
        print(f"[record-transitions] invoke complete in {elapsed:.1f}s")

        ints = (final or {}).get("__interrupt__") or []
        if ints:
            print(
                "[record-transitions] WARN: run halted on interrupt(s); "
                f"count={len(ints)}",
                file=sys.stderr,
            )
        errs = (final or {}).get("errors") or []
        print(f"[record-transitions] errors={len(errs)} notices={len((final or {}).get('notices') or [])}")
        if errs:
            for e in errs[-3:]:
                print(f"[record-transitions] ERR: {e}", file=sys.stderr)

        post_transitions = (final or {}).get("compose", {}).get("index_html")
        if isinstance(post_transitions, str):
            has_marker = "<!-- p4_transitions: begin -->" in post_transitions
            print(
                f"[record-transitions] final compose.index_html len="
                f"{len(post_transitions)} marker={has_marker}"
            )

    finally:
        try:
            finalize_record_on_miss(mounted, cache)
            print(f"[record-transitions] finalized -> {mounted.fixture_path}")
        except Exception as e:
            print(f"[record-transitions] finalize failed: {e!r}", file=sys.stderr)
        mounted.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
