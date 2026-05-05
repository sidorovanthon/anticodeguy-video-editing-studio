"""Unit tests for p4_dispatch_beats node + scene_id sanitiser.

Per spec `2026-05-04-hom-122-p4-beats-fan-out-design.md`:
  - 4 skip cases: no plan, no catalog, no index_html, unparseable dimensions
  - happy path: cumulative data_start_s, is_final on last beat,
    data_width/data_height parsed from root index.html
  - scene_id collision: error surfaces both colliding labels
  - scene_id sanitisation: NFKD, ASCII fold, dash collapse, lowercase, 64-char cap

The dispatcher is class-1 deterministic — no LLM, no subprocess. Real LangGraph
runtime semantics for `Send` aren't exercised here (they're covered by
test_p4_topology.py's compiled-graph edge assertions); we only assert on the
shape of the Command object the node returns.
"""

from __future__ import annotations

from langgraph.constants import END
from langgraph.types import Command, Send

from edit_episode_graph._scene_id import scene_id_for
from edit_episode_graph.nodes.p4_dispatch_beats import p4_dispatch_beats_node


# ---------------------------------------------------------------------------
# scene_id_for
# ---------------------------------------------------------------------------


def test_scene_id_basic_lowercases_and_dashes():
    assert scene_id_for("Hook Scene") == "hook-scene"


def test_scene_id_strips_punct_and_collapses_dashes():
    assert scene_id_for("Beat #2: The Payoff!!!") == "beat-2-the-payoff"


def test_scene_id_nfkd_folds_unicode():
    # "café" → "cafe", "naïve" → "naive"
    assert scene_id_for("Café Naïve") == "cafe-naive"


def test_scene_id_caps_at_64_chars():
    long = "a" * 200
    out = scene_id_for(long)
    assert len(out) <= 64
    assert out == "a" * 64


def test_scene_id_empty_after_sanitisation_falls_back_to_scene():
    assert scene_id_for("***") == "scene"
    assert scene_id_for("") == "scene"


# ---------------------------------------------------------------------------
# p4_dispatch_beats — skip cases
# ---------------------------------------------------------------------------


def _root_html(width: int = 1920, height: int = 1080) -> str:
    return (
        "<!doctype html><html><head>"
        f'<meta name="viewport" content="width={width}, height={height}" />'
        "</head><body>"
        f'<div data-composition-id="root" data-width="{width}" data-height="{height}" '
        'data-duration="10">root</div>'
        "</body></html>"
    )


def _state_with_index(tmp_path, *, html: str | None = None) -> dict:
    hf = tmp_path / "hyperframes"
    hf.mkdir()
    index = hf / "index.html"
    index.write_text(html if html is not None else _root_html(), encoding="utf-8")
    return {
        "episode_dir": str(tmp_path),
        "compose": {
            "hyperframes_dir": str(hf),
            "index_html_path": str(index),
            "catalog": {"blocks": [], "components": [], "fetched_at": "2026-05-04T00:00:00Z"},
            "plan": {
                "narrative_arc": "x",
                "rhythm": "fast-slow",
                "beats": [
                    {"beat": "Hook", "duration_s": 4.5},
                    {"beat": "Tension", "duration_s": 3.0},
                    {"beat": "Payoff", "duration_s": 5.0},
                ],
                "transitions": [],
            },
        },
    }


def test_skip_when_plan_missing(tmp_path):
    state = _state_with_index(tmp_path)
    state["compose"].pop("plan")
    out = p4_dispatch_beats_node(state)
    assert isinstance(out, Command)
    assert out.goto == "p4_assemble_index" or out.goto == END
    # We expect the dispatcher to fall through to assemble (which will
    # itself skip on no beats) rather than terminate the graph.
    assert out.goto == "p4_assemble_index"
    assert any("plan" in n for n in (out.update or {}).get("notices", []))


def test_skip_when_catalog_missing(tmp_path):
    state = _state_with_index(tmp_path)
    state["compose"].pop("catalog")
    out = p4_dispatch_beats_node(state)
    assert isinstance(out, Command)
    assert out.goto == "p4_assemble_index"
    assert any("catalog" in n for n in (out.update or {}).get("notices", []))


def test_skip_when_index_html_missing(tmp_path):
    state = _state_with_index(tmp_path)
    state["compose"]["index_html_path"] = str(tmp_path / "nope.html")
    out = p4_dispatch_beats_node(state)
    assert isinstance(out, Command)
    assert out.goto == "p4_assemble_index"
    assert any("index" in n.lower() for n in (out.update or {}).get("notices", []))


def test_skip_when_dimensions_unparseable(tmp_path):
    state = _state_with_index(tmp_path, html="<html><body>no viewport</body></html>")
    out = p4_dispatch_beats_node(state)
    assert isinstance(out, Command)
    assert out.goto == "p4_assemble_index"
    notices = (out.update or {}).get("notices", [])
    assert any("dimension" in n.lower() or "viewport" in n.lower() for n in notices)


def test_skip_to_end_when_plan_beats_empty(tmp_path):
    state = _state_with_index(tmp_path)
    state["compose"]["plan"]["beats"] = []
    out = p4_dispatch_beats_node(state)
    assert isinstance(out, Command)
    assert out.goto == END


# ---------------------------------------------------------------------------
# p4_dispatch_beats — happy path
# ---------------------------------------------------------------------------


def test_happy_path_builds_send_per_beat_with_cumulative_timing(tmp_path):
    state = _state_with_index(tmp_path)
    out = p4_dispatch_beats_node(state)
    assert isinstance(out, Command)
    assert isinstance(out.goto, list)
    assert all(isinstance(s, Send) for s in out.goto)
    assert [s.node for s in out.goto] == ["p4_beat", "p4_beat", "p4_beat"]

    payloads = [s.arg["_beat_dispatch"] for s in out.goto]
    assert [p["scene_id"] for p in payloads] == ["hook", "tension", "payoff"]
    assert [p["beat_index"] for p in payloads] == [0, 1, 2]
    assert [p["total_beats"] for p in payloads] == [3, 3, 3]
    assert [p["data_start_s"] for p in payloads] == [0.0, 4.5, 7.5]
    assert [p["data_duration_s"] for p in payloads] == [4.5, 3.0, 5.0]
    assert [p["is_final"] for p in payloads] == [False, False, True]
    assert all(p["data_width"] == 1920 and p["data_height"] == 1080 for p in payloads)
    assert all(p["data_track_index"] == 1 for p in payloads)


def test_happy_path_payload_carries_paths_and_plan_beat(tmp_path):
    state = _state_with_index(tmp_path)
    out = p4_dispatch_beats_node(state)
    first = out.goto[0].arg["_beat_dispatch"]
    assert first["plan_beat"] == {"beat": "Hook", "duration_s": 4.5}
    assert first["scene_html_path"].replace("\\", "/").endswith("compositions/hook.html")
    # Per spec: the Send arg should be `{**state, "_beat_dispatch": ...}` so
    # the sub-agent has access to upstream artefacts as well.
    full = out.goto[0].arg
    assert full.get("episode_dir") == state["episode_dir"]
    assert "compose" in full


def test_happy_path_supports_vertical_viewport(tmp_path):
    state = _state_with_index(tmp_path, html=_root_html(width=1080, height=1920))
    out = p4_dispatch_beats_node(state)
    payloads = [s.arg["_beat_dispatch"] for s in out.goto]
    assert all(p["data_width"] == 1080 and p["data_height"] == 1920 for p in payloads)


# ---------------------------------------------------------------------------
# p4_dispatch_beats — collision + sanitisation
# ---------------------------------------------------------------------------


def test_scene_id_collision_surfaces_both_labels(tmp_path):
    state = _state_with_index(tmp_path)
    state["compose"]["plan"]["beats"] = [
        {"beat": "The Hook!", "duration_s": 1.0},
        {"beat": "the-hook", "duration_s": 1.0},
        {"beat": "Payoff", "duration_s": 1.0},
    ]
    out = p4_dispatch_beats_node(state)
    assert isinstance(out, Command)
    # On collision we route to assemble (graceful skip) and surface both
    # labels in an error.
    assert out.goto == "p4_assemble_index"
    errors = (out.update or {}).get("errors", [])
    assert errors, "expected an error entry"
    msg = errors[0]["message"]
    assert "The Hook!" in msg and "the-hook" in msg
    assert "the-hook" in msg  # the colliding scene_id should appear


def test_unicode_beat_label_routed_through_sanitiser(tmp_path):
    state = _state_with_index(tmp_path)
    state["compose"]["plan"]["beats"] = [
        {"beat": "Café — Opening", "duration_s": 2.0},
        {"beat": "Naïve Reveal", "duration_s": 2.0},
        {"beat": "Payoff", "duration_s": 2.0},
    ]
    out = p4_dispatch_beats_node(state)
    payloads = [s.arg["_beat_dispatch"] for s in out.goto]
    assert payloads[0]["scene_id"] == "cafe-opening"
    assert payloads[1]["scene_id"] == "naive-reveal"
