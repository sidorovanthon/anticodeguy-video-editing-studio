"""Routing tests for p3_persist_session and gate:eval_ok pass leg."""

from __future__ import annotations

from langgraph.graph import END

from edit_episode_graph.nodes import _routing


def _gate_record(passed: bool, iteration: int = 1) -> dict:
    return {
        "gate_results": [
            {
                "gate": "gate:eval_ok",
                "passed": passed,
                "violations": [],
                "iteration": iteration,
                "timestamp": "now",
            }
        ]
    }


def test_eval_ok_pass_routes_to_persist_session():
    """HOM-105: pass leg now hops through persist before halt."""
    assert _routing.route_after_eval_ok(_gate_record(True)) == "p3_persist_session"


def test_eval_ok_fail_iter1_still_routes_to_render():
    assert _routing.route_after_eval_ok(_gate_record(False, 1)) == "p3_render_segments"


def test_eval_ok_fail_iter3_still_escalates():
    assert _routing.route_after_eval_ok(_gate_record(False, 3)) == "eval_failure_interrupt"


def test_persist_session_routes_to_halt_on_clean_run():
    state = {"edit": {"persist": {"persisted_at": "/tmp/project.md", "session_n": 1}}}
    assert _routing.route_after_persist_session(state) == "halt_llm_boundary"


def test_persist_session_routes_to_halt_on_skip():
    state = {"edit": {"persist": {"skipped": True, "skip_reason": "no edl"}}}
    assert _routing.route_after_persist_session(state) == "halt_llm_boundary"


def test_persist_session_routes_to_end_on_hard_error():
    state = {"errors": [{"node": "p3_persist_session", "message": "boom", "timestamp": "t"}]}
    assert _routing.route_after_persist_session(state) == END
