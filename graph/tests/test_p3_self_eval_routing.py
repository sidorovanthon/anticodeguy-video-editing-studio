"""Routing + interrupt-payload tests for p3_self_eval / gate:eval_ok."""

from __future__ import annotations

import pytest

from edit_episode_graph.nodes import _routing
from edit_episode_graph.nodes.eval_failure_interrupt import eval_failure_interrupt_node


def _gate_record(passed: bool, iteration: int, violations=None) -> dict:
    return {
        "gate_results": [
            {
                "gate": "gate:eval_ok",
                "passed": passed,
                "violations": violations or [],
                "iteration": iteration,
                "timestamp": "now",
            }
        ]
    }


def test_render_routes_to_self_eval_on_success():
    state = {"edit": {"render": {"final_mp4": "/x/final.mp4"}}}
    assert _routing.route_after_render_segments(state) == "p3_self_eval"


def test_render_skip_routes_to_halt():
    state = {"edit": {"render": {"skipped": True}}}
    assert _routing.route_after_render_segments(state) == "halt_llm_boundary"


def test_self_eval_skip_routes_to_halt():
    state = {"edit": {"eval": {"skipped": True}}}
    assert _routing.route_after_self_eval(state) == "halt_llm_boundary"


def test_self_eval_success_routes_to_gate():
    state = {"edit": {"eval": {"passed": True}}}
    assert _routing.route_after_self_eval(state) == "gate_eval_ok"


def test_eval_ok_pass_routes_to_persist_session():
    """HOM-105 inserts p3_persist_session between gate:eval_ok and halt."""
    assert _routing.route_after_eval_ok(_gate_record(True, 1)) == "p3_persist_session"


def test_eval_ok_fail_iter1_routes_to_render():
    assert _routing.route_after_eval_ok(_gate_record(False, 1, ["x"])) == "p3_render_segments"


def test_eval_ok_fail_iter2_routes_to_render():
    assert _routing.route_after_eval_ok(_gate_record(False, 2, ["x"])) == "p3_render_segments"


def test_eval_ok_fail_iter3_escalates():
    assert _routing.route_after_eval_ok(_gate_record(False, 3, ["x"])) == "eval_failure_interrupt"


def test_eval_ok_no_record_escalates():
    assert _routing.route_after_eval_ok({}) == "eval_failure_interrupt"


def test_interrupt_payload(monkeypatch):
    captured: dict = {}

    def fake_interrupt(value):
        captured["value"] = value
        raise RuntimeError("interrupt-sentinel")

    monkeypatch.setattr(
        "edit_episode_graph.nodes.eval_failure_interrupt.interrupt",
        fake_interrupt,
    )
    state = {
        **_gate_record(False, 3, ["v1", "v2"]),
        "edit": {"eval": {"issues": [{"kind": "audio_pop", "severity": "blocker"}]}},
    }
    with pytest.raises(RuntimeError, match="interrupt-sentinel"):
        eval_failure_interrupt_node(state)
    payload = captured["value"]
    assert payload["gate"] == "gate:eval_ok"
    assert payload["violations"] == ["v1", "v2"]
    assert payload["iteration"] == 3
    assert payload["issues"] == [{"kind": "audio_pop", "severity": "blocker"}]
