from pathlib import Path

from langgraph.graph import END

from edit_episode_graph.nodes._routing import route_after_preflight


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
