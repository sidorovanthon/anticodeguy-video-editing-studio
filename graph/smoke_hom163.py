"""HOM-163 smoke — `gate_results_reducer` clear-on-replay sentinels through the runtime.

Exercises the reducer via the actual LangGraph compiled graph + checkpointer
(InMemorySaver, since this isn't a long-running session). The reducer is a
pure function exhaustively tested in `tests/test_state.py`; this smoke proves
the framework actually invokes it for `update_state` calls (i.e. the
`Annotated[list, gate_results_reducer]` annotation is wired into the channel).

Three cases:

  1. **Append (default).** Two writes via `invoke` accumulate via the reducer.
  2. **`_clear_gate` sentinel via `update_state`.** Drive state to two records
     (`gate:lint` + `gate:eval_ok`), call `update_state(values={"gate_results":
     {"_clear_gate": "gate:lint"}}, as_node=<some_node>)`, snapshot state and
     assert only the eval_ok record remains.
  3. **`_replace` sentinel via `update_state`.** Same setup, replace with a
     fresh single-record list, assert exact contents.

The graph topology isn't important here — we use a tiny throwaway 2-node
graph with the production state schema (`GraphState`) so the reducer is the
real one. This isolates the reducer from Phase 3/4 routing complexity (which
is covered by the broader test suite).

Run from the worktree's graph directory:

    PYTHONPATH=$(pwd)/src .venv/Scripts/python smoke_hom163.py
"""

from __future__ import annotations

import sys

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph

from edit_episode_graph.state import GraphState


def _node_a(state):
    return {"gate_results": [{"gate": "gate:lint", "passed": False, "iteration": 1}]}


def _node_b(state):
    return {"gate_results": [{"gate": "gate:eval_ok", "passed": False, "iteration": 1}]}


def _compile():
    g = StateGraph(GraphState)
    g.add_node("a", _node_a)
    g.add_node("b", _node_b)
    g.set_entry_point("a")
    g.add_edge("a", "b")
    g.add_edge("b", END)
    return g.compile(checkpointer=InMemorySaver())


def main() -> int:
    graph = _compile()
    cfg = {"configurable": {"thread_id": "hom-163-smoke"}}

    # --- Case 1: append (default reducer behavior through invoke). -----------
    out = graph.invoke({"slug": "smoke"}, cfg)
    gates = [r["gate"] for r in (out.get("gate_results") or [])]
    if gates != ["gate:lint", "gate:eval_ok"]:
        print(f"SMOKE FAIL: append case got {gates!r}", file=sys.stderr)
        return 1
    print(f"OK case 1 (append): gate_results = {gates}")

    # --- Case 2: _clear_gate via update_state (the canonical rewind path). ---
    graph.update_state(
        cfg,
        {"gate_results": {"_clear_gate": "gate:lint"}},
        as_node="b",
    )
    snap = graph.get_state(cfg)
    gates = [r["gate"] for r in (snap.values.get("gate_results") or [])]
    if gates != ["gate:eval_ok"]:
        print(f"SMOKE FAIL: _clear_gate case got {gates!r}", file=sys.stderr)
        return 2
    print(f"OK case 2 (_clear_gate gate:lint): gate_results = {gates}")

    # --- Case 3: _replace via update_state (full overwrite). -----------------
    graph.update_state(
        cfg,
        {"gate_results": {"_replace": True, "items": [
            {"gate": "gate:plan_ok", "passed": True, "iteration": 1},
        ]}},
        as_node="b",
    )
    snap = graph.get_state(cfg)
    records = snap.values.get("gate_results") or []
    if len(records) != 1 or records[0].get("gate") != "gate:plan_ok":
        print(f"SMOKE FAIL: _replace case got {records!r}", file=sys.stderr)
        return 3
    print(f"OK case 3 (_replace): gate_results = {records}")

    # --- Case 4: _replace with empty items clears entirely. ------------------
    graph.update_state(
        cfg,
        {"gate_results": {"_replace": True, "items": []}},
        as_node="b",
    )
    snap = graph.get_state(cfg)
    records = snap.values.get("gate_results") or []
    if records:
        print(f"SMOKE FAIL: _replace empty case got {records!r}", file=sys.stderr)
        return 4
    print(f"OK case 4 (_replace empty): gate_results = []")

    print("\nAll cases passed. gate_results_reducer is wired into the channel "
          "and update_state honors both sentinels.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
