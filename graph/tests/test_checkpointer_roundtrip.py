"""HOM-346 regression: SqliteSaver round-trips checkpoint state across instances.

In-process analog of `graph/scripts/verify_postgres_resume.py` — guards against
future `langgraph-checkpoint-sqlite` upgrades silently breaking the
`BaseCheckpointSaver` contract that HOM-334 Phase B (multi-session step-debug
walkthroughs via `langgraph up`) depends on.

The test deliberately uses TWO distinct `SqliteSaver` instances pointing at the
same tmp file — and compiles TWO separate graphs against them — to prove the
state survives via the on-disk backend, not via shared in-process state. This
is structurally weaker than the subprocess proof in `verify_postgres_resume.py`
(which forks the interpreter) but strong enough to detect a regression in the
saver's serialisation/deserialisation protocol.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict


class _State(TypedDict, total=False):
    counter: int
    resumed_with: str


def _before(state: _State) -> _State:
    return {"counter": state.get("counter", 0) + 1}


def _pause(state: _State) -> _State:
    payload = interrupt({"awaiting": "operator approval"})
    return {"resumed_with": str(payload)}


def _after(state: _State) -> _State:
    return {"counter": state["counter"] + 1}


def _build_pause_graph() -> StateGraph:
    g = StateGraph(_State)
    g.add_node("before", _before)
    g.add_node("pause", _pause)
    g.add_node("after", _after)
    g.add_edge(START, "before")
    g.add_edge("before", "pause")
    g.add_edge("pause", "after")
    g.add_edge("after", END)
    return g


def test_sqlite_checkpointer_round_trips_across_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "hom346-roundtrip.db"
    thread_id = "hom346-roundtrip-thread"
    config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

    # Phase 1 — instance #1: invoke until interrupt, then close.
    with SqliteSaver.from_conn_string(str(db_path)) as saver_a:
        graph_a = _build_pause_graph().compile(checkpointer=saver_a)
        graph_a.invoke({"counter": 0}, config=config)
        state_a = graph_a.get_state(config)
        assert state_a.tasks, "expected an outstanding task at the interrupt"
        assert state_a.tasks[0].interrupts, "expected interrupt to be recorded"
        assert "pause" in state_a.next, f"expected next=pause, got {state_a.next!r}"

    # Phase 2 — instance #2 (fresh saver + fresh compiled graph) on same file.
    # Mirrors `langgraph up` reattaching to a Postgres-backed thread after a
    # Studio restart: no shared in-process state with phase 1.
    with SqliteSaver.from_conn_string(str(db_path)) as saver_b:
        graph_b = _build_pause_graph().compile(checkpointer=saver_b)
        restored = graph_b.get_state(config)
        assert restored.tasks, "interrupt position did not survive saver re-open"
        assert restored.tasks[0].interrupts, "interrupt payload lost across instances"

        result = graph_b.invoke(Command(resume="approved"), config=config)
        assert result.get("counter") == 2, f"counter did not advance: {result!r}"
        assert result.get("resumed_with"), "resume payload not threaded into state"

        after = graph_b.get_state(config)
        assert not after.next, f"graph should be terminal after resume, got {after.next!r}"
