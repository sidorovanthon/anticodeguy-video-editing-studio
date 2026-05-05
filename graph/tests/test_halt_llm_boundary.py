"""halt_llm_boundary copy: distinguishes v1 vs v2 halt so Studio shows
*why* the run stopped and what would unblock it."""

from __future__ import annotations

from edit_episode_graph.nodes.halt_llm_boundary import halt_llm_boundary_node


def test_v1_halt_when_pre_scan_skipped():
    state = {"edit": {"pre_scan": {"skipped": True, "skip_reason": "missing"}}}
    update = halt_llm_boundary_node(state)
    msg = update["notices"][0]
    assert msg.startswith("v1 halt")
    assert "final.mp4" in msg


def test_v1_halt_when_no_pre_scan_state_at_all():
    update = halt_llm_boundary_node({})
    assert update["notices"][0].startswith("v1 halt")


def test_v2_halt_when_pre_scan_ran():
    state = {"edit": {"pre_scan": {"slips": [
        {"quote": "x", "take_index": 1, "reason": "placeholder"},
    ]}}}
    update = halt_llm_boundary_node(state)
    msg = update["notices"][0]
    assert msg.startswith("v2 halt: pre_scan ran")
    assert "1 slip" in msg


def test_v2_halt_with_zero_slips_still_v2():
    """An empty `slips` list still indicates pre_scan executed (no placeholders found)."""
    state = {"edit": {"pre_scan": {"slips": []}}}
    update = halt_llm_boundary_node(state)
    assert update["notices"][0].startswith("v2 halt: pre_scan ran")


def test_v3_halt_when_render_completed():
    state = {
        "edit": {
            "edl": {"ranges": [{}, {}, {}]},
            "render": {
                "final_mp4": "/x/edit/final.mp4",
                "n_segments": 3,
                "delta_ms": 12,
                "cached": False,
            },
        },
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert msg.startswith("v3 halt: final.mp4 rendered")
    assert "3 segment" in msg
    assert "12ms" in msg


def test_v3_halt_marks_cached_render():
    state = {
        "edit": {
            "edl": {"ranges": [{}]},
            "render": {"final_mp4": "/x/edit/final.mp4", "n_segments": 1, "cached": True},
        },
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert "[cached]" in msg


def test_v4_halt_after_plan_gate_pass():
    state = {
        "compose": {"plan": {"beats": [{}, {}, {}]}},
        "gate_results": [
            {"gate": "gate:plan_ok", "passed": True, "iteration": 1,
             "violations": [], "timestamp": "now"},
        ],
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert msg.startswith("v4 halt: gate:plan_ok passed")
    assert "p4_catalog_scan" in msg


def test_v4_halt_after_catalog_scan():
    """Catalog scanned but assembly hasn't run — notice names catalog as latest reachable."""
    state = {
        "compose": {
            "catalog": {"blocks": [{}, {}], "components": [{}], "fetched_at": "now"},
        },
        "gate_results": [
            {"gate": "gate:plan_ok", "passed": True, "iteration": 1,
             "violations": [], "timestamp": "now"},
        ],
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert "catalog scanned" in msg
    assert "2 block" in msg
    assert "1 component" in msg
    assert "p4_assemble_index" in msg


def test_v4_halt_after_assemble_skip():
    state = {
        "compose": {
            "catalog": {"blocks": [{}], "components": [], "fetched_at": "now"},
            "assemble": {"skipped": True, "skip_reason": "no beats in state"},
        },
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert "p4_assemble_index skipped" in msg
    assert "no beats" in msg


def test_v4_halt_after_assemble_success():
    state = {
        "compose": {
            "assemble": {
                "assembled_at": "now",
                "beat_names": ["HOOK", "PAYOFF"],
                "captions_included": True,
            },
        },
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert "scenes assembled" in msg
    assert "2 scene" in msg
    assert "HOM-124" in msg

