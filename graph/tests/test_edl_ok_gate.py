"""Unit tests for gate:edl_ok — runs against a synthetic transcript on disk."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from edit_episode_graph.gates.edl_ok import EdlOkGate, edl_ok_gate_node


@pytest.fixture()
def episode(tmp_path: Path) -> Path:
    transcripts = tmp_path / "edit" / "transcripts"
    transcripts.mkdir(parents=True)
    # Construct words at well-known positions: word_a [1.000-1.500], word_b
    # [2.000-2.500], word_c [3.000-3.500]. Boundaries: 1.0, 1.5, 2.0, 2.5, 3.0,
    # 3.5. Cut edges in [0.85,0.97] / [3.53,3.65] = padding 30-150ms.
    words = [
        {"text": "alpha", "start": 1.000, "end": 1.500, "type": "word"},
        {"text": " ",     "start": 1.500, "end": 2.000, "type": "spacing"},
        {"text": "beta",  "start": 2.000, "end": 2.500, "type": "word"},
        {"text": " ",     "start": 2.500, "end": 3.000, "type": "spacing"},
        {"text": "gamma", "start": 3.000, "end": 3.500, "type": "word"},
    ]
    (transcripts / "raw.json").write_text(json.dumps({"words": words}), encoding="utf-8")
    return tmp_path


def _state(episode: Path, edl: dict, source_duration_s: float = 5.0) -> dict:
    return {
        "episode_dir": str(episode),
        "edit": {
            "edl": edl,
            "inventory": {"sources": [{"stem": "raw", "duration_s": source_duration_s}]},
        },
    }


def _good_edl() -> dict:
    return {
        "version": 1,
        "sources": {"raw": "/abs/raw.mp4"},
        "ranges": [
            # cut runtime: (1.4 - 0.95) + (3.55 - 1.95) = 0.45 + 1.60 = 2.05
            {"source": "raw", "start": 0.95, "end": 1.55,
             "beat": "A", "quote": "alpha", "reason": "x"},
            {"source": "raw", "start": 1.95, "end": 3.55,
             "beat": "B", "quote": "beta gamma", "reason": "y"},
        ],
        "grade": "neutral",
        "overlays": [],
        "total_duration_s": 2.20,
    }


def test_passes_on_clean_edl(episode: Path):
    # cut total = 0.6 + 1.6 = 2.2; source = 7.0 → ratio 0.314 ✓
    state = _state(episode, _good_edl(), source_duration_s=7.0)
    update = edl_ok_gate_node(state)
    record = update["gate_results"][0]
    assert record["passed"], record["violations"]
    assert record["gate"] == "gate:edl_ok"
    assert record["iteration"] == 1


def test_fails_when_overlays_nonempty(episode: Path):
    edl = _good_edl()
    edl["overlays"] = [{"file": "x.mp4", "start_in_output": 0.0, "duration": 1.0}]
    state = _state(episode, edl, source_duration_s=7.0)
    update = edl_ok_gate_node(state)
    assert not update["gate_results"][0]["passed"]
    assert any("overlays" in v for v in update["gate_results"][0]["violations"])


def test_fails_when_subtitles_field_present(episode: Path):
    edl = _good_edl()
    edl["subtitles"] = "edit/master.srt"
    state = _state(episode, edl, source_duration_s=7.0)
    update = edl_ok_gate_node(state)
    assert not update["gate_results"][0]["passed"]
    assert any("subtitles" in v for v in update["gate_results"][0]["violations"])


def test_fails_when_cut_inside_word(episode: Path):
    edl = _good_edl()
    edl["ranges"][0]["end"] = 1.300  # mid-word "alpha" [1.0, 1.5]
    state = _state(episode, edl, source_duration_s=7.0)
    update = edl_ok_gate_node(state)
    assert not update["gate_results"][0]["passed"]
    assert any("cuts inside word" in v for v in update["gate_results"][0]["violations"])


def test_fails_when_padding_too_small(episode: Path):
    edl = _good_edl()
    edl["ranges"][0]["start"] = 0.999  # 1ms from boundary 1.000 < 30ms
    state = _state(episode, edl, source_duration_s=7.0)
    update = edl_ok_gate_node(state)
    assert not update["gate_results"][0]["passed"]
    assert any("padding" in v for v in update["gate_results"][0]["violations"])


def test_fails_when_padding_too_large(episode: Path):
    edl = _good_edl()
    edl["ranges"][0]["start"] = 0.500  # 500ms from boundary 1.000 > 200ms
    state = _state(episode, edl, source_duration_s=7.0)
    update = edl_ok_gate_node(state)
    assert not update["gate_results"][0]["passed"]
    assert any("padding" in v for v in update["gate_results"][0]["violations"])


def test_fails_when_pacing_outside_window(episode: Path):
    # cut total 2.2 with source 100s → ratio 2.2% << 25%
    state = _state(episode, _good_edl(), source_duration_s=100.0)
    update = edl_ok_gate_node(state)
    assert not update["gate_results"][0]["passed"]
    assert any("pacing" in v for v in update["gate_results"][0]["violations"])


def test_fails_when_source_durations_missing(episode: Path):
    state = {
        "episode_dir": str(episode),
        "edit": {"edl": _good_edl()},
    }
    update = edl_ok_gate_node(state)
    assert not update["gate_results"][0]["passed"]
    assert any("pacing unverifiable" in v for v in update["gate_results"][0]["violations"])


def test_fails_when_range_references_unknown_source(episode: Path):
    edl = _good_edl()
    edl["ranges"][0]["source"] = "missing"
    state = _state(episode, edl, source_duration_s=7.0)
    update = edl_ok_gate_node(state)
    assert not update["gate_results"][0]["passed"]
    assert any("not in EDL.sources" in v for v in update["gate_results"][0]["violations"])


def test_iteration_increments_across_invocations(episode: Path):
    state = _state(episode, _good_edl(), source_duration_s=7.0)
    first = edl_ok_gate_node(state)
    state["gate_results"] = first["gate_results"]
    second = edl_ok_gate_node(state)
    assert second["gate_results"][0]["iteration"] == 2


def test_skipped_edl_emits_violation(episode: Path):
    state = {
        "episode_dir": str(episode),
        "edit": {"edl": {"skipped": True, "skip_reason": "missing input"}},
    }
    update = edl_ok_gate_node(state)
    assert not update["gate_results"][0]["passed"]
    assert "skipped upstream" in update["gate_results"][0]["violations"][0]


def test_gate_class_identity():
    g = EdlOkGate()
    assert g.name == "gate:edl_ok"
