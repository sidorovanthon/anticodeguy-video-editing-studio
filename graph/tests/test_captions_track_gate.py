"""Unit tests for gate:captions_track."""

from __future__ import annotations

from pathlib import Path

from edit_episode_graph.gates.captions_track import captions_track_gate_node


def _hf_with_index(tmp_path: Path, html: str) -> Path:
    hf_dir = tmp_path / "hyperframes"
    hf_dir.mkdir(parents=True)
    (hf_dir / "index.html").write_text(html, encoding="utf-8")
    return hf_dir


def _state(hf_dir: Path) -> dict:
    return {"compose": {"hyperframes_dir": str(hf_dir)}}


def test_passes_when_captions_layer_div_present(tmp_path: Path):
    hf_dir = _hf_with_index(
        tmp_path,
        '<html><body><div id="captions-layer" class="captions-layer">x</div></body></html>',
    )
    update = captions_track_gate_node(_state(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"], record["violations"]
    assert record["gate"] == "gate:captions_track"


def test_passes_when_caption_timeline_registration_present(tmp_path: Path):
    """Fallback marker — no wrapper div but timeline still binds."""
    hf_dir = _hf_with_index(
        tmp_path,
        '<html><body><script>window.__captionTimelines["captions"] = tl;</script></body></html>',
    )
    update = captions_track_gate_node(_state(hf_dir))
    assert update["gate_results"][0]["passed"]


def test_fails_when_neither_marker_present(tmp_path: Path):
    hf_dir = _hf_with_index(
        tmp_path,
        '<html><body><div id="something-else">no captions</div></body></html>',
    )
    update = captions_track_gate_node(_state(hf_dir))
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any("missing captions layer" in v for v in record["violations"])


def test_fails_when_no_index_html(tmp_path: Path):
    hf_dir = tmp_path / "hyperframes"
    hf_dir.mkdir()
    update = captions_track_gate_node(_state(hf_dir))
    assert not update["gate_results"][0]["passed"]


def test_fails_when_no_hyperframes_dir_in_state():
    update = captions_track_gate_node({})
    assert not update["gate_results"][0]["passed"]


def test_id_attribute_quote_styles_all_match(tmp_path: Path):
    """HTML5 attribute quoting variants should all match the marker."""
    forms = (
        'id="captions-layer"',
        "id='captions-layer'",
        "id=captions-layer",
        'ID="captions-layer"',
    )
    for i, attr_form in enumerate(forms):
        hf_dir = _hf_with_index(tmp_path / f"case_{i}", f"<div {attr_form}></div>")
        update = captions_track_gate_node(_state(hf_dir))
        assert update["gate_results"][0]["passed"], (attr_form, update)
