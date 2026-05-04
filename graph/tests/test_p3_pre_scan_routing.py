from pathlib import Path

from langgraph.graph import END

from edit_episode_graph.nodes._routing import (
    route_after_inventory,
    route_after_pre_scan,
    route_after_preflight,
    route_after_strategy,
    route_after_strategy_confirmed,
)


def test_routes_to_pre_scan_when_takes_packed_exists(tmp_path):
    edit = tmp_path / "edit"
    edit.mkdir()
    (edit / "takes_packed.md").write_text("# t\n", encoding="utf-8")
    state = {"episode_dir": str(tmp_path)}
    assert route_after_preflight(state) == "p3_pre_scan"


def test_routes_to_glue_when_final_exists(tmp_path):
    edit = tmp_path / "edit"
    edit.mkdir()
    (edit / "final.mp4").write_bytes(b"x")
    (edit / "takes_packed.md").write_text("# t\n", encoding="utf-8")
    state = {"episode_dir": str(tmp_path)}
    assert route_after_preflight(state) == "glue_remap_transcript"


def test_routes_to_inventory_when_neither_exists(tmp_path):
    state = {"episode_dir": str(tmp_path)}
    assert route_after_preflight(state) == "p3_inventory"


def test_routes_to_end_after_inventory_error():
    state = {"errors": [{"node": "p3_inventory", "message": "boom", "timestamp": "now"}]}
    assert route_after_inventory(state) == END


def test_routes_to_pre_scan_after_inventory_success():
    assert route_after_inventory({}) == "p3_pre_scan"


def test_routes_to_end_after_pre_scan_error():
    state = {"errors": [{"node": "p3_pre_scan", "message": "boom", "timestamp": "now"}]}
    assert route_after_pre_scan(state) == END


def test_routes_to_strategy_after_pre_scan_success():
    assert route_after_pre_scan({}) == "p3_strategy"


def test_routes_to_end_after_strategy_error():
    state = {"errors": [{"node": "p3_strategy", "message": "boom", "timestamp": "now"}]}
    assert route_after_strategy(state) == END


def test_routes_to_strategy_confirmed_after_strategy_success():
    """HR 11 — strategy approval comes between p3_strategy and p3_edl_select."""
    assert route_after_strategy({}) == "strategy_confirmed_interrupt"


def test_routes_to_edl_select_after_strategy_confirmed():
    assert route_after_strategy_confirmed({}) == "p3_edl_select"


def test_routes_to_end_after_strategy_confirmed_error():
    state = {"errors": [{"node": "x", "message": "boom", "timestamp": "now"}]}
    assert route_after_strategy_confirmed(state) == END


def test_routes_to_end_when_strategy_skipped():
    state = {"edit": {"strategy": {"skipped": True, "skip_reason": "missing input"}}}
    assert route_after_strategy_confirmed(state) == END
