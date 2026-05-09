"""Drive a full real-tier graph run against a fixture episode and record cache.db.

HOM-189: rebuild ``tests/fixtures/episodes/<slug>/cache.db`` against the actual
fixture clip (not whatever production episode the operator's main checkout
happens to surface). Critical env to set BEFORE importing
``edit_episode_graph``: ``HOMESTUDIO_PROJECT_ROOT=<repo>/tests/fixtures`` so
``_paths.project_root()`` resolves ``episodes/<slug>/`` under the fixture
tree, not the gitignored production ``episodes/``. Pickup captures
``project_root()`` at import time, hence the early ``os.environ`` mutation
below.

Usage::

    python -m scripts.record_fixture --slug canonical-portrait-talking-head [--dry-run]

The driver:

1. Mounts the fixture cache.db via :mod:`tests._helpers.replay_harness` in
   ``record-on-miss`` mode (working tmp file seeded from any existing
   fixture cache.db; finalize VACUUMs into the canonical fixture path,
   atomic rename). Hits short-circuit on already-recorded entries — only
   misses spend real LLM. For a fully-fresh re-record, ``rm`` the fixture
   ``cache.db`` before running.
2. Compiles the graph with ``cache=<that working SqliteCache>`` and an
   :class:`~langgraph.checkpoint.memory.InMemorySaver` (we are not running
   under ``langgraph dev``; the langgraph-api-rejected checkpointer
   constraint does not apply here).
3. ``invoke`` with ``{"slug": <slug>}``, then loops:
   each :class:`~langgraph.errors.GraphInterrupt` is resumed via
   ``Command(resume="approved")``. Two interrupts are expected on the
   recorded happy path (``strategy_confirmed_interrupt`` after
   ``p3_strategy`` and ``p3_review_interrupt`` after
   ``p3_persist_session``); we loop generically so a third surprise
   interrupt is still handled.
4. On clean termination, finalizes the working cache via
   :func:`finalize_record_on_miss` so the fixture file is in deterministic
   raw form (``VACUUM INTO`` + atomic rename — no WAL artefacts, no
   spurious diff).

Native primitives: ``Command(resume=...)`` for HITL resume — see
https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/ and
``langgraph.types.Command``. No custom dispatch / no Studio API roundtrip.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# 1. Resolve the worktree root (this file is at <root>/scripts/record_fixture.py).
_WORKTREE = Path(__file__).resolve().parents[1]

# 2. Pin HOMESTUDIO_PROJECT_ROOT before any edit_episode_graph import. Pickup
#    and other deterministic nodes capture project_root() at module load time.
os.environ["HOMESTUDIO_PROJECT_ROOT"] = str(_WORKTREE / "tests" / "fixtures")

# 3. Make the worktree's graph/src importable ahead of any global editable
#    install (which may resolve to a different checkout). Mirrors
#    tests/conftest.py.
_GRAPH_SRC = _WORKTREE / "graph" / "src"
if _GRAPH_SRC.is_dir() and str(_GRAPH_SRC) not in sys.path:
    sys.path.insert(0, str(_GRAPH_SRC))

# 4. Make the worktree itself importable so `tests._helpers.*` and
#    `scripts.*` resolve from this checkout.
if str(_WORKTREE) not in sys.path:
    sys.path.insert(0, str(_WORKTREE))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slug",
        default="canonical-portrait-talking-head",
        help="Fixture episode slug (default: canonical-portrait-talking-head)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mount + compile but do not invoke (smoke test wiring without LLM spend).",
    )
    parser.add_argument(
        "--max-resumes",
        type=int,
        default=8,
        help="Defensive ceiling on interrupt-resume loop iterations (default 8).",
    )
    args = parser.parse_args()

    # Imports deferred until after env is pinned.
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.errors import GraphInterrupt
    from langgraph.types import Command

    from edit_episode_graph import graph as graph_mod
    from edit_episode_graph._paths import project_root

    from tests._helpers.replay_harness import (
        finalize_record_on_miss,
        mount_fixture_cache,
        open_cache,
    )

    print(f"[record_fixture] HOMESTUDIO_PROJECT_ROOT = {os.environ['HOMESTUDIO_PROJECT_ROOT']}")
    print(f"[record_fixture] project_root()         = {project_root()}")
    print(f"[record_fixture] slug                    = {args.slug}")

    fixture_root = _WORKTREE / "tests" / "fixtures"
    episode_dir = fixture_root / "episodes" / args.slug
    raw_path = episode_dir / "raw.mp4"
    if not raw_path.exists():
        print(f"[record_fixture] FATAL: fixture raw not found at {raw_path}", file=sys.stderr)
        return 2

    # Mount fixture in record mode — empty tmp working file. finalize_record_on_miss
    # will VACUUM INTO the canonical fixture path on success.
    mounted = mount_fixture_cache(args.slug, mode="record-on-miss", fixtures_root=fixture_root)
    print(f"[record_fixture] mounted cache mode={mounted.mode}")
    print(f"[record_fixture]   working_path={mounted.working_path}")
    print(f"[record_fixture]   fixture_path={mounted.fixture_path}")

    cache = open_cache(mounted)

    # Compile graph with our working cache + InMemorySaver. langgraph-api
    # rejects user-supplied checkpointers but we are not running under it.
    saver = InMemorySaver()
    compiled = graph_mod.build_graph_uncompiled().compile(cache=cache, checkpointer=saver)

    if args.dry_run:
        print("[record_fixture] --dry-run: graph compiled, no invoke. Exiting clean.")
        mounted.cleanup()
        return 0

    thread_id = f"hom-189-record-{int(time.time())}"
    cfg = {"configurable": {"thread_id": thread_id}, "recursion_limit": 200}
    print(f"[record_fixture] thread_id={thread_id}")

    # First invocation seeds the slug; subsequent invocations resume.
    invocation_input = {"slug": args.slug}
    started = time.time()
    resumes = 0
    final_state: dict | None = None

    try:
        while True:
            try:
                final_state = compiled.invoke(invocation_input, config=cfg)
            except GraphInterrupt as gi:
                # Older / different code paths may still raise; treat the same
                # as the channel-based signal below.
                final_state = {"__interrupt__": list(gi.args[0]) if gi.args else []}

            # langgraph 1.x: an interrupt sets the `__interrupt__` channel
            # on the returned state instead of raising. Reference:
            # https://docs.langchain.com/oss/python/langgraph/use-graph-api#human-in-the-loop
            # https://docs.langchain.com/oss/python/langgraph/types#interrupt
            ints = (final_state or {}).get("__interrupt__") or []
            if not ints:
                print(f"[record_fixture] graph terminated after {resumes} resume(s)")
                break

            resumes += 1
            if resumes > args.max_resumes:
                print(
                    f"[record_fixture] FATAL: exceeded --max-resumes={args.max_resumes}",
                    file=sys.stderr,
                )
                break

            preview = []
            for i in ints[:3]:
                val = getattr(i, "value", None) if not isinstance(i, dict) else i.get("value")
                if isinstance(val, dict):
                    preview.append(val.get("checkpoint", "?"))
                else:
                    preview.append(repr(val)[:60])
            print(f"[record_fixture] interrupt #{resumes}: {preview} — resuming with 'approved'")
            invocation_input = Command(resume="approved")  # type: ignore[assignment]

        # Pull the final state via checkpoint, in case invoke returned a partial dict.
        snap = compiled.get_state(cfg)
        if snap is not None:
            final_state = snap.values
        elapsed = time.time() - started
        print(f"[record_fixture] elapsed: {elapsed:.1f}s, resumes: {resumes}")
        if isinstance(final_state, dict):
            errs = final_state.get("errors") or []
            notices = final_state.get("notices") or []
            print(f"[record_fixture] errors: {len(errs)} | notices: {len(notices)}")
            if errs:
                print(f"[record_fixture] FIRST ERROR: {errs[0]}", file=sys.stderr)
            for n in notices[-3:]:
                print(f"[record_fixture] NOTICE: {n}")

    finally:
        # Always try to persist whatever the run produced — partial recordings
        # are still valuable. finalize is a no-op in replay mode; safe.
        try:
            finalize_record_on_miss(mounted, cache)
            print(f"[record_fixture] finalized -> {mounted.fixture_path}")
        except Exception as e:  # pragma: no cover — diagnostic only
            print(f"[record_fixture] finalize failed: {e!r}", file=sys.stderr)
        mounted.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
