"""Tests for HOM-130 — edl/eval failure-interrupt resume-loop.

The interrupt nodes capture the operator's resume payload into
`state.edit.<edl|eval>.failure_resume`. Routing then either re-runs the
originating gate (retry) or escalates to `halt_llm_boundary` (abort).
These tests cover both branches without exercising the LangGraph runtime
— the topology test (`test_p4_topology.py`) is the deterministic gate
that the new edges are actually wired.
"""

from __future__ import annotations

from langgraph.graph import END

from edit_episode_graph.nodes._routing import (
    route_after_edl_failure_interrupt,
    route_after_eval_failure_interrupt,
)


def _state_with_edl_resume(action) -> dict:
    return {
        "edit": {
            "edl": {
                "ranges": [{"source": "raw", "start": 1.0, "end": 2.0}],
                "failure_resume": {"action": action, "iteration_at_suspend": 1},
            }
        }
    }


def _state_with_eval_resume(action) -> dict:
    return {
        "edit": {
            "eval": {
                "issues": [],
                "failure_resume": {"action": action, "iteration_at_suspend": 3},
            }
        }
    }


# --- edl_failure_interrupt routing -------------------------------------------


def test_edl_resume_empty_routes_to_gate_for_revalidation():
    # Operator's natural Studio gesture: edit EDL, hit Submit with empty box.
    for empty in (None, "", {}):
        assert route_after_edl_failure_interrupt(_state_with_edl_resume(empty)) == "gate_edl_ok"


def test_edl_resume_nonempty_payload_routes_to_gate():
    # Any non-abort string or dict is treated as retry.
    assert route_after_edl_failure_interrupt(_state_with_edl_resume("retry")) == "gate_edl_ok"
    assert route_after_edl_failure_interrupt(_state_with_edl_resume({"note": "fixed"})) == "gate_edl_ok"


def test_edl_resume_abort_string_routes_to_halt():
    for token in ("abort", "STOP", "  give_up  ", "no", "n"):
        assert (
            route_after_edl_failure_interrupt(_state_with_edl_resume(token))
            == "halt_llm_boundary"
        ), f"abort token {token!r} should halt"


def test_edl_resume_abort_dict_routes_to_halt():
    assert (
        route_after_edl_failure_interrupt(_state_with_edl_resume({"abort": True}))
        == "halt_llm_boundary"
    )


def test_edl_resume_ignores_historical_errors():
    """HOM-158: failure interrupts never write `state["errors"]` themselves —
    they capture the operator's resume payload. A historical error from any
    earlier node must NOT block the resume; routing follows the resume action.
    """
    state = _state_with_edl_resume("retry")
    state["errors"] = [{"node": "x", "message": "y", "timestamp": "old"}]
    assert route_after_edl_failure_interrupt(state) == "gate_edl_ok"


def test_edl_resume_missing_failure_resume_routes_to_gate():
    """Defensive: if the interrupt node's state-delta hasn't landed yet for
    some reason, default to retry rather than silently halting."""
    assert route_after_edl_failure_interrupt({"edit": {"edl": {}}}) == "gate_edl_ok"
    assert route_after_edl_failure_interrupt({}) == "gate_edl_ok"


# --- eval_failure_interrupt routing (mirror) ---------------------------------


def test_eval_resume_empty_routes_to_gate_for_revalidation():
    for empty in (None, "", {}):
        assert (
            route_after_eval_failure_interrupt(_state_with_eval_resume(empty))
            == "gate_eval_ok"
        )


def test_eval_resume_abort_string_routes_to_halt():
    for token in ("abort", "stop", "give_up", "n"):
        assert (
            route_after_eval_failure_interrupt(_state_with_eval_resume(token))
            == "halt_llm_boundary"
        )


def test_eval_resume_abort_dict_routes_to_halt():
    assert (
        route_after_eval_failure_interrupt(_state_with_eval_resume({"abort": True}))
        == "halt_llm_boundary"
    )


def test_eval_resume_nonempty_payload_routes_to_gate():
    assert (
        route_after_eval_failure_interrupt(_state_with_eval_resume("retry"))
        == "gate_eval_ok"
    )


def test_eval_resume_ignores_historical_errors():
    """HOM-158: mirror of `test_edl_resume_ignores_historical_errors`."""
    state = _state_with_eval_resume("retry")
    state["errors"] = [{"node": "x", "message": "y", "timestamp": "old"}]
    assert route_after_eval_failure_interrupt(state) == "gate_eval_ok"


# --- interrupt nodes capture resume payload into state -----------------------


def test_edl_interrupt_node_writes_resume_payload(monkeypatch):
    """When the runtime resumes, `interrupt()` returns the resume value
    instead of suspending. The node must persist that value to
    `state.edit.edl.failure_resume.action` so routing can read it.
    """
    from edit_episode_graph.nodes import edl_failure_interrupt as mod

    monkeypatch.setattr(mod, "interrupt", lambda payload: "abort")
    state = {
        "edit": {
            "edl": {"ranges": [{"source": "raw", "start": 0.0, "end": 1.0}]},
        },
        "gate_results": [
            {"gate": "gate:edl_ok", "passed": False, "violations": ["v"], "iteration": 1}
        ],
    }
    delta = mod.edl_failure_interrupt_node(state)
    edl = delta["edit"]["edl"]
    # Existing siblings preserved; new failure_resume added.
    assert edl["ranges"] == state["edit"]["edl"]["ranges"]
    assert edl["failure_resume"]["action"] == "abort"
    assert edl["failure_resume"]["iteration_at_suspend"] == 1
    assert "resumed_at" in edl["failure_resume"]


def test_eval_interrupt_node_writes_resume_payload(monkeypatch):
    from edit_episode_graph.nodes import eval_failure_interrupt as mod

    monkeypatch.setattr(mod, "interrupt", lambda payload: {"abort": True})
    state = {
        "edit": {
            "eval": {"issues": ["i1"], "passed": False},
        },
        "gate_results": [
            {"gate": "gate:eval_ok", "passed": False, "violations": ["v"], "iteration": 3}
        ],
    }
    delta = mod.eval_failure_interrupt_node(state)
    eval_out = delta["edit"]["eval"]
    assert eval_out["issues"] == ["i1"]
    assert eval_out["passed"] is False
    assert eval_out["failure_resume"]["action"] == {"abort": True}
    assert eval_out["failure_resume"]["iteration_at_suspend"] == 3
