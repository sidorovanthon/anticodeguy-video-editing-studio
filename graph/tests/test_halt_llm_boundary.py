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
