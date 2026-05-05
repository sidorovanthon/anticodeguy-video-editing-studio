"""Unit tests for gate:static_guard (HOM-125)."""

from __future__ import annotations

from pathlib import Path

import pytest

from edit_episode_graph.gates.static_guard import (
    scan_log_text,
    static_guard_gate_node,
)


def _state(log_path: Path) -> dict:
    return {"compose": {"preview_log_path": str(log_path)}}


def _no_sleep(_seconds: float) -> None:
    return None


def test_pure_scan_passes_on_clean_log():
    out = scan_log_text("hyperframes preview listening on 3002\nready\n")
    assert out.violations == []
    assert out.extras == {}


def test_pure_scan_fails_on_static_guard_marker():
    out = scan_log_text(
        "ready\n[StaticGuard] missing data-hf-anchor on .scene\n"
    )
    assert out.violations
    assert "StaticGuard" in out.violations[0]
    assert "canon_video_audio_artifact" not in out.extras


def test_pure_scan_fails_on_invalid_contract_marker():
    out = scan_log_text("Invalid HyperFrame contract: schema mismatch\n")
    assert out.violations
    assert any("Invalid HyperFrame contract" in v for v in out.violations)


def test_pure_scan_treats_video_audio_canon_bug_as_artifact():
    """Per memory feedback_hf_video_audio_canon_bug — canon Video/Audio
    example trips StaticGuard with `data-has-audio` not set."""
    out = scan_log_text(
        "ready\n"
        "[StaticGuard] <video> element missing data-has-audio attribute\n"
    )
    assert out.violations == []
    assert out.extras["canon_video_audio_artifact"] is True
    assert "data-has-audio" in out.extras["annotation"]
    assert out.extras["matched_lines"]


def test_pure_scan_does_not_apply_artifact_to_unrelated_static_guard():
    """A non-Video/Audio StaticGuard hit must still fail loudly — the
    canon-bug triage is narrow on purpose."""
    out = scan_log_text(
        "[StaticGuard] missing data-hf-anchor on .scene\n"
        "[StaticGuard] <video> element missing data-has-audio attribute\n"
    )
    # First line is unrelated to the canon bug → real failure.
    assert out.violations
    assert "canon_video_audio_artifact" not in out.extras


def test_pure_scan_does_not_apply_artifact_when_contract_failure_present():
    out = scan_log_text(
        "[StaticGuard] <video> element missing data-has-audio attribute\n"
        "Invalid HyperFrame contract: schema mismatch on root\n"
    )
    assert out.violations
    assert "canon_video_audio_artifact" not in out.extras


def test_node_passes_on_clean_log(tmp_path: Path):
    log = tmp_path / "preview.log"
    log.write_text("ready\n", encoding="utf-8")
    update = static_guard_gate_node(_state(log), sleep_fn=_no_sleep)
    record = update["gate_results"][0]
    assert record["passed"], record["violations"]
    assert "notices" not in update


def test_node_fails_when_log_missing(tmp_path: Path):
    update = static_guard_gate_node(
        _state(tmp_path / "missing.log"), sleep_fn=_no_sleep
    )
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any("not on disk" in v for v in record["violations"])


def test_node_fails_when_preview_log_path_absent():
    update = static_guard_gate_node({"compose": {}}, sleep_fn=_no_sleep)
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any("preview_log_path missing" in v for v in record["violations"])


def test_node_fails_on_real_static_guard(tmp_path: Path):
    """Negative case: deliberately broken HTML produces a real StaticGuard."""
    log = tmp_path / "preview.log"
    log.write_text(
        "[StaticGuard] missing data-hf-anchor on .scene\n", encoding="utf-8"
    )
    update = static_guard_gate_node(_state(log), sleep_fn=_no_sleep)
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any("StaticGuard" in v for v in record["violations"])
    assert any("FAILED" in n for n in update["notices"])


def test_node_passes_with_canon_artifact_annotation(tmp_path: Path):
    """Per memory `feedback_hf_video_audio_canon_bug` — must not iterate."""
    log = tmp_path / "preview.log"
    log.write_text(
        "[StaticGuard] <video> element missing data-has-audio attribute\n",
        encoding="utf-8",
    )
    update = static_guard_gate_node(_state(log), sleep_fn=_no_sleep)
    record = update["gate_results"][0]
    assert record["passed"], record
    assert record["canon_video_audio_artifact"] is True
    assert any("canon_video_audio_artifact" in n for n in update["notices"])


def test_node_does_not_false_positive_on_empty_state_text(tmp_path: Path):
    """Per memory `feedback_studio_player_empty_state` — the Studio Player's
    "Drop media here" empty UI is NOT a render fail. The gate scans the
    preview-CLI log only, so even if such text were echoed there, the gate
    must not treat it as a violation."""
    log = tmp_path / "preview.log"
    log.write_text(
        "Studio: Drop media here to load a composition\n"
        "preview server ready on http://localhost:3002\n",
        encoding="utf-8",
    )
    update = static_guard_gate_node(_state(log), sleep_fn=_no_sleep)
    assert update["gate_results"][0]["passed"]


def test_node_iteration_increments(tmp_path: Path):
    log = tmp_path / "preview.log"
    log.write_text("ready\n", encoding="utf-8")
    state = _state(log)
    state["gate_results"] = [
        {"gate": "gate:static_guard", "passed": False, "violations": [], "iteration": 1},
    ]
    update = static_guard_gate_node(state, sleep_fn=_no_sleep)
    assert update["gate_results"][0]["iteration"] == 2
