"""Unit tests for gate:validate including opacity-0 headless triage."""

from __future__ import annotations

from pathlib import Path

import pytest

from edit_episode_graph.gates import _base
from edit_episode_graph.gates.validate import ValidateGate, validate_gate_node


def _hf_with_index(tmp_path: Path, html: str) -> Path:
    hf_dir = tmp_path / "hyperframes"
    hf_dir.mkdir()
    (hf_dir / "index.html").write_text(html, encoding="utf-8")
    return hf_dir


def _state_for(hf_dir: Path) -> dict:
    return {"compose": {"hyperframes_dir": str(hf_dir)}}


def _patch_run(monkeypatch: pytest.MonkeyPatch, exit_code: int, stdout: str = "", stderr: str = ""):
    def fake_run(args, hf_dir, **kw):
        return _base.CliResult(
            cmd=["hyperframes", *list(args)],
            cwd=str(hf_dir),
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

    monkeypatch.setattr("edit_episode_graph.gates.validate.run_hf_cli", fake_run)


def test_passes_when_cli_exits_zero(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    hf_dir = _hf_with_index(tmp_path, "<html><body></body></html>")
    _patch_run(monkeypatch, 0, "validate ok\n")

    update = validate_gate_node(_state_for(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"], record["violations"]
    assert "headless_artifact_suspected" not in record


def test_fails_on_real_schema_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    hf_dir = _hf_with_index(tmp_path, "<html><body><div>plain</div></body></html>")
    _patch_run(monkeypatch, 1, "schema error: missing data-hf-anchor on .scene\n")

    update = validate_gate_node(_state_for(hf_dir))
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any("schema error" in v for v in record["violations"])


def test_passes_with_artifact_annotation_on_wcag_failure_with_opacity_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Documented headless artifact: WCAG/contrast fail + opacity:0 entrance.

    Per memory feedback_wcag_headless_opacity_artifact this must pass with
    annotation, not fail — failing here would push the pipeline into a
    palette iteration loop that is the documented anti-pattern.
    """
    hf_dir = _hf_with_index(
        tmp_path,
        """<html><body>
        <div class="hero" style="color: #000">Headline</div>
        <script>
          gsap.fromTo('.hero', { opacity: 0 }, { opacity: 1, duration: 0.5 });
        </script>
        </body></html>""",
    )
    _patch_run(monkeypatch, 1, "WCAG contrast failure on .hero: ratio 1.0 < 4.5\n")

    update = validate_gate_node(_state_for(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"], record
    assert record["headless_artifact_suspected"] is True
    assert "do NOT iterate" in record["annotation"]
    assert record["validate_exit_code"] == 1
    assert any("headless_artifact_suspected" in n for n in update["notices"])


def test_fails_loudly_on_wcag_failure_without_opacity_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    hf_dir = _hf_with_index(
        tmp_path,
        "<html><body><div style='color:#000;background:#222'>x</div></body></html>",
    )
    _patch_run(monkeypatch, 1, "WCAG contrast failure on div: ratio 1.5 < 4.5\n")

    update = validate_gate_node(_state_for(hf_dir))
    record = update["gate_results"][0]
    assert not record["passed"]
    assert "headless_artifact_suspected" not in record


def test_fails_loudly_on_wcag_failure_with_static_opacity_zero_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Static `opacity: 0` (no GSAP entrance call) must NOT mask a WCAG fail.

    A permanently-hidden element with `style='opacity:0'` is itself a real
    accessibility problem — invisible text. The triage's job is to ignore
    the documented headless-screenshot artifact (GSAP entrance animations
    captured mid-fade-in), NOT to wave through every opacity:0 element.
    """
    hf_dir = _hf_with_index(
        tmp_path,
        "<html><body><div style='opacity: 0; color: #000'>hidden</div></body></html>",
    )
    _patch_run(monkeypatch, 1, "WCAG contrast failure on div: ratio 1.0 < 4.5\n")

    update = validate_gate_node(_state_for(hf_dir))
    record = update["gate_results"][0]
    assert not record["passed"], record
    assert "headless_artifact_suspected" not in record


def test_fails_loudly_on_non_wcag_failure_even_with_opacity_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Opacity-0 alone must not mask a non-WCAG failure.

    The triage is gated on the failure looking WCAG-related; otherwise
    real schema/parse errors would be hidden by any HF project that
    happens to use the entrance pattern (almost all of them).
    """
    hf_dir = _hf_with_index(
        tmp_path,
        "<html><body><div style='opacity:0'>x</div></body></html>",
    )
    _patch_run(monkeypatch, 1, "schema error: missing required key palette\n")

    update = validate_gate_node(_state_for(hf_dir))
    record = update["gate_results"][0]
    assert not record["passed"]
    assert "headless_artifact_suspected" not in record


def test_fails_when_no_hyperframes_dir_in_state():
    update = validate_gate_node({})
    assert not update["gate_results"][0]["passed"]


def test_fails_when_hyperframes_dir_missing_on_disk(tmp_path: Path):
    update = validate_gate_node(
        {"compose": {"hyperframes_dir": str(tmp_path / "nope")}}
    )
    assert not update["gate_results"][0]["passed"]
    assert any(
        "not on disk" in v for v in update["gate_results"][0]["violations"]
    )
