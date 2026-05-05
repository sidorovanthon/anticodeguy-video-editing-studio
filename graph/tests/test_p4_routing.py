"""Pure-function tests for Phase 4 routing helpers."""

from __future__ import annotations

from langgraph.graph import END

from edit_episode_graph.nodes._routing import (
    route_after_assemble_index,
    route_after_catalog_scan,
    route_after_design_ok,
    route_after_design_system,
    route_after_plan,
    route_after_plan_ok,
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


def test_route_after_prompt_expansion_default_to_plan():
    state = {"compose": {"expansion": {"expanded_prompt_path": "/x"}}}
    assert route_after_prompt_expansion(state) == "p4_plan"


def test_route_after_plan_skip_to_end():
    assert route_after_plan({"compose": {"plan": {"skipped": True}}}) == END


def test_route_after_plan_error_to_end():
    state = {"errors": [{"node": "p4_plan", "message": "x", "timestamp": "now"}]}
    assert route_after_plan(state) == END


def test_route_after_plan_pass_to_gate():
    assert route_after_plan({"compose": {"plan": {"beats": []}}}) == "gate_plan_ok"


def test_route_after_plan_ok_pass_to_catalog_scan():
    """HOM-121 wires gate:plan_ok pass → p4_catalog_scan."""
    pass_state = {"gate_results": [
        {"gate": "gate:plan_ok", "passed": True, "iteration": 1,
         "violations": [], "timestamp": "now"},
    ]}
    assert route_after_plan_ok(pass_state) == "p4_catalog_scan"


def test_route_after_plan_ok_fail_to_halt():
    """v4-sans-HITL: gate fail surfaces through halt_llm_boundary."""
    fail_state = {"gate_results": [
        {"gate": "gate:plan_ok", "passed": False, "iteration": 1,
         "violations": ["x"], "timestamp": "now"},
    ]}
    assert route_after_plan_ok(fail_state) == "halt_llm_boundary"


def test_route_after_plan_ok_no_record_to_halt():
    assert route_after_plan_ok({}) == "halt_llm_boundary"


def test_route_after_catalog_scan_error_to_end():
    state = {"errors": [{"node": "p4_catalog_scan", "message": "x", "timestamp": "now"}]}
    assert route_after_catalog_scan(state) == END


def test_route_after_catalog_scan_default_to_captions():
    # HOM-123: catalog scan now always routes to p4_captions_layer; the
    # beat-vs-skip decision moved downstream to route_after_captions_layer.
    assert route_after_catalog_scan({}) == "p4_captions_layer"


def test_route_after_catalog_scan_with_beats_to_captions():
    state = {"compose": {"plan": {"beats": [{"beat": "Hook", "duration_s": 4.5}]}}}
    assert route_after_catalog_scan(state) == "p4_captions_layer"


def test_route_after_captions_layer_error_to_end():
    from edit_episode_graph.nodes._routing import route_after_captions_layer
    state = {"errors": [{"node": "p4_captions_layer", "message": "x", "timestamp": "now"}]}
    assert route_after_captions_layer(state) == END


def test_route_after_captions_layer_with_beats_to_dispatch():
    from edit_episode_graph.nodes._routing import route_after_captions_layer
    state = {"compose": {"plan": {"beats": [{"beat": "Hook", "duration_s": 4.5}]}}}
    assert route_after_captions_layer(state) == "p4_dispatch_beats"


def test_route_after_captions_layer_empty_beats_to_assemble():
    # Defensive: an explicit empty `beats` list must NOT trigger dispatch.
    from edit_episode_graph.nodes._routing import route_after_captions_layer
    state = {"compose": {"plan": {"beats": []}}}
    assert route_after_captions_layer(state) == "p4_assemble_index"


def test_route_after_captions_layer_default_to_assemble():
    from edit_episode_graph.nodes._routing import route_after_captions_layer
    assert route_after_captions_layer({}) == "p4_assemble_index"


def test_route_after_assemble_index_error_to_end():
    state = {"errors": [{"node": "p4_assemble_index", "message": "x", "timestamp": "now"}]}
    assert route_after_assemble_index(state) == END


def test_route_after_assemble_index_default_to_studio_launch():
    """HOM-125: a successful assemble (no error, no skip flag) advances to
    studio_launch — the empty state stands in for "happy path" here."""
    assert route_after_assemble_index({}) == "studio_launch"


def test_route_after_assemble_index_skip_to_halt():
    """Skip case (e.g. missing scenes) still routes to halt — there is
    nothing to preview, so studio_launch would just spawn an idle server."""
    state = {"compose": {"assemble": {"skipped": True, "skip_reason": "no beats"}}}
    assert route_after_assemble_index(state) == "halt_llm_boundary"


def test_route_after_studio_launch_default_to_gate():
    from edit_episode_graph.nodes._routing import route_after_studio_launch
    assert route_after_studio_launch({}) == "gate_static_guard"


def test_route_after_studio_launch_error_to_end():
    from edit_episode_graph.nodes._routing import route_after_studio_launch
    state = {"errors": [{"node": "studio_launch", "message": "x", "timestamp": "now"}]}
    assert route_after_studio_launch(state) == END


def test_route_after_static_guard_always_to_halt():
    """v4 ends here regardless of pass/fail; HITL retry is HOM-78/v6."""
    from edit_episode_graph.nodes._routing import route_after_static_guard
    assert route_after_static_guard({}) == "halt_llm_boundary"
    state = {
        "gate_results": [
            {"gate": "gate:static_guard", "passed": False, "violations": ["x"], "iteration": 1}
        ]
    }
    assert route_after_static_guard(state) == "halt_llm_boundary"
