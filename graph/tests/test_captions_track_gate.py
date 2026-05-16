"""Unit tests for gate:captions_track."""

from __future__ import annotations

from edit_episode_graph.gates.captions_track import captions_track_gate_node


def _state(html: str | None) -> dict:
    """HOM-274 (Class A): inject the assembled index.html body string into
    state.compose.index_html instead of writing to disk. Mirrors HOM-270's
    DESIGN.md test migration. ``None`` simulates the assemble node not
    having populated the state channel."""
    compose: dict = {}
    if html is not None:
        compose["index_html"] = html
    return {"compose": compose}


def test_passes_when_captions_layer_div_present():
    update = captions_track_gate_node(_state(
        '<html><body><div id="captions-layer" class="captions-layer">x</div></body></html>',
    ))
    record = update["gate_results"][0]
    assert record["passed"], record["violations"]
    assert record["gate"] == "gate:captions_track"


def test_passes_when_caption_timeline_registration_present():
    """Fallback marker — no wrapper div but timeline still binds."""
    update = captions_track_gate_node(_state(
        '<html><body><script>window.__captionTimelines["captions"] = tl;</script></body></html>',
    ))
    assert update["gate_results"][0]["passed"]


def test_fails_when_neither_marker_present():
    update = captions_track_gate_node(_state(
        '<html><body><div id="something-else">no captions</div></body></html>',
    ))
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any("missing captions layer" in v for v in record["violations"])


def test_fails_when_index_html_body_absent_from_state():
    """Producer (p4_assemble_index) did not populate state.compose.index_html.
    Gate must surface that explicitly rather than silently passing."""
    update = captions_track_gate_node(_state(None))
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any(
        "index.html body absent in state.compose.index_html" in v
        for v in record["violations"]
    )


def test_fails_when_no_compose_in_state():
    update = captions_track_gate_node({})
    assert not update["gate_results"][0]["passed"]


def test_id_attribute_quote_styles_all_match():
    """HTML5 attribute quoting variants should all match the marker."""
    forms = (
        'id="captions-layer"',
        "id='captions-layer'",
        "id=captions-layer",
        'ID="captions-layer"',
    )
    for attr_form in forms:
        update = captions_track_gate_node(_state(f"<div {attr_form}></div>"))
        assert update["gate_results"][0]["passed"], (attr_form, update)
