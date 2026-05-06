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


def test_persist_session_routes_to_review_on_clean_run():
    """HOM-146: post-persist now flows into the Phase-3 review interrupt."""
    state = {"edit": {"persist": {"persisted_at": "/tmp/project.md", "session_n": 1}}}
    assert _routing.route_after_persist_session(state) == "p3_review_interrupt"


def test_persist_session_routes_to_review_on_skip():
    """A persist skip is non-fatal — operator still gets a chance to review."""
    state = {"edit": {"persist": {"skipped": True, "skip_reason": "no edl"}}}
    assert _routing.route_after_persist_session(state) == "p3_review_interrupt"


def test_persist_session_routes_to_end_on_hard_error():
    state = {"errors": [{"node": "p3_persist_session", "message": "boom", "timestamp": "t"}]}
    assert _routing.route_after_persist_session(state) == END


# HOM-146 — review_interrupt routing


def test_review_interrupt_default_routes_to_glue():
    """No review payload yet → graph proceeds into Phase 4 on resume."""
    state = {}
    assert _routing.route_after_p3_review_interrupt(state) == "glue_remap_transcript"


def test_review_interrupt_approved_routes_to_glue():
    state = {"edit": {"review": {"phase3": {"approved": True}}}}
    assert _routing.route_after_p3_review_interrupt(state) == "glue_remap_transcript"


def test_review_interrupt_aborted_routes_to_halt():
    state = {"edit": {"review": {"phase3": {"aborted": True}}}}
    assert _routing.route_after_p3_review_interrupt(state) == "halt_llm_boundary"


def test_review_interrupt_errors_route_to_end():
    state = {"errors": [{"node": "p3_review_interrupt", "message": "boom", "timestamp": "t"}]}
    assert _routing.route_after_p3_review_interrupt(state) == END
