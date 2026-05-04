"""Pure-function tests for Phase 4 routing helpers."""

from __future__ import annotations

from langgraph.graph import END

from edit_episode_graph.nodes._routing import (
    route_after_design_ok,
    route_after_design_system,
    route_after_prompt_expansion,
    route_after_scaffold,
)


def _gate_record(passed: bool, iteration: int = 1) -> dict:
    return {
        "gate_results": [
            {"gate": "gate:design_ok", "passed": passed, "iteration": iteration,
             "violations": [] if passed else ["x"], "timestamp": "now"},
        ],
    }


def test_route_after_scaffold_error_to_end():
    assert route_after_scaffold({"errors": [{"node": "p4_scaffold", "message": "x", "timestamp": "now"}]}) == END


def test_route_after_scaffold_default_to_design():
    assert route_after_scaffold({}) == "p4_design_system"


def test_route_after_design_system_skip_to_end():
    assert route_after_design_system({"compose": {"design": {"skipped": True}}}) == END


def test_route_after_design_system_error_to_end():
    state = {"errors": [{"node": "p4_design_system", "message": "x", "timestamp": "now"}]}
    assert route_after_design_system(state) == END


def test_route_after_design_system_pass_to_gate():
    assert route_after_design_system({"compose": {"design": {"palette": []}}}) == "gate_design_ok"


def test_route_after_design_ok_pass_to_prompt_expansion():
    assert route_after_design_ok(_gate_record(passed=True)) == "p4_prompt_expansion"


def test_route_after_design_ok_fail_to_halt():
    assert route_after_design_ok(_gate_record(passed=False)) == "halt_llm_boundary"


def test_route_after_design_ok_no_record_to_halt():
    assert route_after_design_ok({}) == "halt_llm_boundary"


def test_route_after_prompt_expansion_skip_to_end():
    assert route_after_prompt_expansion({"compose": {"expansion": {"skipped": True}}}) == END


def test_route_after_prompt_expansion_error_to_end():
    state = {"errors": [{"node": "p4_prompt_expansion", "message": "x", "timestamp": "now"}]}
    assert route_after_prompt_expansion(state) == END


def test_route_after_prompt_expansion_default_to_halt():
    state = {"compose": {"expansion": {"expanded_prompt_path": "/x"}}}
    assert route_after_prompt_expansion(state) == "halt_llm_boundary"
