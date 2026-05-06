"""Tests for edl_failure_interrupt node and its routing.

Verifies that:
  - The node raises GraphInterrupt with the violation list as payload.
  - route_after_edl_ok dispatches to the interrupt node only on gate fail.
  - Compiled graph with an InMemorySaver actually suspends (does not
    crash, does not END) when the gate fails — proving the interrupt is
    visible to the runtime, not swallowed.
"""

from __future__ import annotations

import pytest

from edit_episode_graph.nodes._routing import route_after_edl_ok
from edit_episode_graph.nodes.edl_failure_interrupt import edl_failure_interrupt_node


def _state_with_gate(passed: bool, violations: list[str] | None = None,
                     iteration: int = 1) -> dict:
    return {
        "gate_results": [
            {
                "gate": "gate:edl_ok",
                "passed": passed,
                "violations": violations or [],
                "iteration": iteration,
                "timestamp": "now",
            }
        ]
    }


def test_routing_first_fail_routes_to_retry():
    """HOM-147: first failure (iter=1) routes to p3_edl_select for a retry
    with prior violations injected, rather than straight to interrupt."""
    state = _state_with_gate(False, ["range[0].start cuts inside word"])
    assert route_after_edl_ok(state) == "p3_edl_select"


def test_routing_exhausted_fail_goes_to_interrupt():
    """HOM-147: once iter ≥ max_iterations (3) the retry budget is spent;
    routing falls through to the interrupt for HITL recovery."""
    state = _state_with_gate(False, ["range[0].start cuts inside word"], iteration=3)
    assert route_after_edl_ok(state) == "edl_failure_interrupt"


def test_routing_pass_skips_interrupt():
    state = _state_with_gate(True)
    assert route_after_edl_ok(state) == "p3_render_segments"


def test_routing_no_record_treated_as_fail():
    """Defensive: missing gate record should not silently route to halt or
    burn a retry — fall through to the interrupt so the operator sees state."""
    assert route_after_edl_ok({}) == "edl_failure_interrupt"


def test_node_calls_interrupt_with_violations(monkeypatch):
    """Verify the payload passed to langgraph.types.interrupt.

    interrupt() needs a Runnable context to actually raise GraphInterrupt;
    calling the node bare-function would fail with RuntimeError. We don't
    need the runtime here — we only need to assert the payload shape. The
    full runtime path is exercised by the smoke harness and Studio.
    """
    captured: dict = {}

    def fake_interrupt(value):
        captured["value"] = value
        raise RuntimeError("interrupt-sentinel")

    monkeypatch.setattr(
        "edit_episode_graph.nodes.edl_failure_interrupt.interrupt",
        fake_interrupt,
    )
    state = _state_with_gate(False, ["v1", "v2"])
    with pytest.raises(RuntimeError, match="interrupt-sentinel"):
        edl_failure_interrupt_node(state)
    payload = captured["value"]
    assert payload["gate"] == "gate:edl_ok"
    assert payload["violations"] == ["v1", "v2"]
    assert payload["iteration"] == 1
    assert "hint" in payload


def test_compiled_minigraph_suspends_on_gate_failure(tmp_path):
    """End-to-end: real interrupt visible to LangGraph runtime.

    Builds a 2-node mini-graph (gate_edl_ok → routing → edl_failure_interrupt)
    around the synthetic-failure state. Asserts the run lands in
    `__interrupt__` rather than reaching END. This proves the gate→interrupt
    split (state lands; then suspend) works under the real runtime — the
    bare-function test above can't exercise the suspend.
    """
    import json
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, StateGraph

    from edit_episode_graph.gates.edl_ok import edl_ok_gate_node
    from edit_episode_graph.nodes.edl_failure_interrupt import edl_failure_interrupt_node
    from edit_episode_graph.state import GraphState

    transcripts = tmp_path / "edit" / "transcripts"
    transcripts.mkdir(parents=True)
    (transcripts / "raw.json").write_text(
        json.dumps({"words": [{"text": "alpha", "start": 1.0, "end": 2.0, "type": "word"}]}),
        encoding="utf-8",
    )

    g = StateGraph(GraphState)
    g.add_node("gate_edl_ok", edl_ok_gate_node)
    g.add_node("edl_failure_interrupt", edl_failure_interrupt_node)
    g.set_entry_point("gate_edl_ok")
    # HOM-147: gate_edl_ok router can also route to p3_edl_select (retry)
    # on early-iteration failures. We skip the retry branch in this mini-
    # graph by pre-seeding state with two prior failed records so the next
    # gate run records iteration=3 and routes straight to the interrupt.
    # The retry path is exercised by test_gate_retry_routing.py.
    g.add_conditional_edges(
        "gate_edl_ok",
        route_after_edl_ok,
        {
            "p3_render_segments": END,        # placeholder for the pass branch
            "p3_edl_select": END,             # retry branch — not exercised here
            "edl_failure_interrupt": "edl_failure_interrupt",
        },
    )
    g.add_edge("edl_failure_interrupt", END)
    compiled = g.compile(checkpointer=InMemorySaver())

    prior_failures = [
        {"gate": "gate:edl_ok", "passed": False,
         "violations": ["earlier"], "iteration": i, "timestamp": "old"}
        for i in (1, 2)
    ]
    state = {
        "slug": "synthetic",
        "episode_dir": str(tmp_path),
        "gate_results": prior_failures,
        "edit": {
            "edl": {
                "version": 1,
                "sources": {"raw": "/abs/raw.mp4"},
                # Mid-word cut: end=1.5 sits inside word [1.0, 2.0]
                "ranges": [{"source": "raw", "start": 1.5, "end": 1.8,
                            "beat": "X", "quote": "alpha", "reason": "x"}],
                "grade": "neutral",
                "overlays": [],
                "total_duration_s": 0.3,
            },
            "inventory": {"sources": [{"stem": "raw", "duration_s": 5.0}]},
        },
    }
    config = {"configurable": {"thread_id": "test-suspend"}}
    result = compiled.invoke(state, config=config)
    assert "__interrupt__" in result, f"expected interrupt, got keys={list(result)}"
    interrupts = result["__interrupt__"]
    payload = interrupts[0].value
    assert payload["gate"] == "gate:edl_ok"
    assert payload["violations"], "expected non-empty violations"
    # State delta from the gate ran before the interrupt — record is visible.
    snapshot = compiled.get_state(config).values
    gate_records = snapshot.get("gate_results") or []
    assert any(r["gate"] == "gate:edl_ok" and not r["passed"] for r in gate_records)
