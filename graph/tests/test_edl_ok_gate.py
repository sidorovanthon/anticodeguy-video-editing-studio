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


def _state(
    episode: Path,
    edl: dict,
    source_duration_s: float = 5.0,
    length_estimate_s: float | None = 2.05,
) -> dict:
    """Default fixture provides a strategy.length_estimate_s matching the
    canonical cut total (~2.05s for `_good_edl()`). Pass `length_estimate_s=None`
    to exercise the upstream-contract-violation branch."""
    edit = {
        "edl": edl,
        "inventory": {"sources": [{"stem": "raw", "duration_s": source_duration_s}]},
    }
    if length_estimate_s is not None:
        edit["strategy"] = {"length_estimate_s": length_estimate_s}
    return {"episode_dir": str(episode), "edit": edit}


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


def test_fails_when_strategy_estimate_missing(episode: Path):
    """`schemas.p3_strategy.Strategy` requires `length_estimate_s` (Field(gt=0)).
    If it's missing at the gate, the upstream contract was violated; gate
    hard-fails rather than fall back to a one-artifact ratio."""
    state = _state(episode, _good_edl(), source_duration_s=100.0, length_estimate_s=None)
    update = edl_ok_gate_node(state)
    assert not update["gate_results"][0]["passed"]
    violations = update["gate_results"][0]["violations"]
    assert any("pacing unverifiable" in v and "length_estimate_s" in v for v in violations), violations


def test_passes_when_length_matches_strategy_estimate(episode: Path):
    """Strategy-anchored: 2.2s cut vs 2.2s estimate → exact match."""
    state = _state(episode, _good_edl(), source_duration_s=100.0, length_estimate_s=2.2)
    update = edl_ok_gate_node(state)
    assert update["gate_results"][0]["passed"], update["gate_results"][0]["violations"]


def test_passes_when_length_within_tolerance(episode: Path):
    """Cut at 2.2s with estimate 2.5s → 12% off, within ±20%."""
    state = _state(episode, _good_edl(), source_duration_s=100.0, length_estimate_s=2.5)
    update = edl_ok_gate_node(state)
    assert update["gate_results"][0]["passed"], update["gate_results"][0]["violations"]


def test_fails_when_length_outside_tolerance(episode: Path):
    """Cut at 2.2s with estimate 5.0s → 56% off, outside ±20%."""
    state = _state(episode, _good_edl(), source_duration_s=100.0, length_estimate_s=5.0)
    update = edl_ok_gate_node(state)
    assert not update["gate_results"][0]["passed"]
    violations = update["gate_results"][0]["violations"]
    assert any("length" in v and "outside target" in v for v in violations), violations


def test_falls_back_to_ffprobe_when_inventory_missing(tmp_path: Path, monkeypatch):
    """Skip-inventory path leaves edit.inventory empty; gate must ffprobe.

    Regression: real run on a cached episode (takes_packed.md present, so
    p3_inventory was skipped by route_after_preflight) hit "pacing
    unverifiable: source durations missing" because the gate read only
    inventory.sources. ffprobe fallback over edl.sources paths fixes it.
    """
    transcripts = tmp_path / "edit" / "transcripts"
    transcripts.mkdir(parents=True)
    words = [
        {"text": "alpha", "start": 1.0, "end": 1.5, "type": "word"},
        {"text": "beta",  "start": 2.0, "end": 2.5, "type": "word"},
        {"text": "gamma", "start": 3.0, "end": 3.5, "type": "word"},
    ]
    (transcripts / "raw.json").write_text(json.dumps({"words": words}), encoding="utf-8")

    # Stub ffprobe by monkeypatching the helper directly. Avoids needing
    # a real video file on disk.
    from edit_episode_graph.gates import edl_ok as gate_module
    monkeypatch.setattr(gate_module, "_ffprobe_duration_s", lambda p: 7.0)

    state = {
        "episode_dir": str(tmp_path),
        "edit": {
            # inventory deliberately absent — mirrors skip-inventory routing
            "edl": _good_edl(),
            "strategy": {"length_estimate_s": 2.05},
        },
    }
    record = edl_ok_gate_node(state)["gate_results"][0]
    assert record["passed"], record["violations"]


def test_strategy_estimate_supersedes_fallback(tmp_path: Path):
    """Empirical case from real run: 70s source, 56s cut, estimate 62s.

    Old fixed 25–35% pacing rejected this (80% kept). The new strategy-anchored
    ±20% bound around 62s admits any cut in [49.6, 74.4]. 56s passes.
    """
    transcripts = tmp_path / "edit" / "transcripts"
    transcripts.mkdir(parents=True)
    words = [
        {"text": "intro", "start": 4.0, "end": 5.0, "type": "word"},
        {"text": "outro", "start": 60.0, "end": 61.0, "type": "word"},
    ]
    (transcripts / "raw.json").write_text(json.dumps({"words": words}), encoding="utf-8")
    edl = {
        "version": 1,
        "sources": {"raw": "/abs/raw.mp4"},
        "ranges": [
            # Padding 50ms past intro end (5.0) and 50ms past outro end (61.0).
            {"source": "raw", "start": 5.05, "end": 61.05,
             "beat": "X", "quote": "...", "reason": "x"},
        ],
        "grade": "neutral",
        "overlays": [],
        "total_duration_s": 56.0,
    }
    state = {
        "episode_dir": str(tmp_path),
        "edit": {
            "edl": edl,
            "inventory": {"sources": [{"stem": "raw", "duration_s": 70.0}]},
            "strategy": {"length_estimate_s": 62.0},
        },
    }
    record = edl_ok_gate_node(state)["gate_results"][0]
    assert record["passed"], record["violations"]


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


def test_long_silence_cut_passes_when_close_to_neighbor(tmp_path: Path):
    """A cut in a 3s silence is fine if the *near* boundary is within 30–200ms.

    Regression: the prior global-min-distance check would have flagged this
    cut at 4.05 because it was ~2.95s from the next word at 7.0 — even though
    the near side (prev word ending at 4.0) sits at 50ms.
    """
    transcripts = tmp_path / "edit" / "transcripts"
    transcripts.mkdir(parents=True)
    words = [
        {"text": "alpha", "start": 3.500, "end": 4.000, "type": "word"},
        # 3-second silence here
        {"text": "beta",  "start": 7.000, "end": 7.500, "type": "word"},
    ]
    (transcripts / "raw.json").write_text(json.dumps({"words": words}), encoding="utf-8")
    edl = {
        "version": 1,
        "sources": {"raw": "/abs/raw.mp4"},
        "ranges": [
            # source=10s, cut=3.95-4.05 padded around alpha's end at 4.000
            {"source": "raw", "start": 3.450, "end": 4.050,
             "beat": "X", "quote": "alpha", "reason": "x"},
            {"source": "raw", "start": 6.950, "end": 7.550,
             "beat": "Y", "quote": "beta", "reason": "y"},
        ],
        "grade": "neutral",
        "overlays": [],
        "total_duration_s": 1.20,
    }
    state = {
        "episode_dir": str(tmp_path),
        "edit": {
            "edl": edl,
            "inventory": {"sources": [{"stem": "raw", "duration_s": 4.0}]},
            "strategy": {"length_estimate_s": 1.20},
        },
    }
    record = edl_ok_gate_node(state)["gate_results"][0]
    assert record["passed"], record["violations"]


def test_cut_in_middle_of_long_silence_fails(tmp_path: Path):
    """Cut equally far from both bracketing words — both sides > 200ms → fail.

    The new bracketing logic treats this correctly: nearest neighboring
    boundary is 1.5s away, well above the 200ms cap.
    """
    transcripts = tmp_path / "edit" / "transcripts"
    transcripts.mkdir(parents=True)
    words = [
        {"text": "alpha", "start": 0.0, "end": 1.0, "type": "word"},
        {"text": "beta",  "start": 4.0, "end": 5.0, "type": "word"},
    ]
    (transcripts / "raw.json").write_text(json.dumps({"words": words}), encoding="utf-8")
    edl = {
        "version": 1,
        "sources": {"raw": "/abs/raw.mp4"},
        "ranges": [
            {"source": "raw", "start": 2.5, "end": 4.95,
             "beat": "X", "quote": "x", "reason": "x"},
        ],
        "grade": "neutral",
        "overlays": [],
        "total_duration_s": 2.45,
    }
    state = {
        "episode_dir": str(tmp_path),
        "edit": {
            "edl": edl,
            "inventory": {"sources": [{"stem": "raw", "duration_s": 8.0}]},
        },
    }
    record = edl_ok_gate_node(state)["gate_results"][0]
    assert not record["passed"]
    assert any("padding 1500ms" in v or "1500" in v for v in record["violations"])
