"""Unit tests for gate:validate including opacity-0 headless triage."""

from __future__ import annotations

from pathlib import Path

import pytest

from edit_episode_graph.gates import _base
from edit_episode_graph.gates.validate import ValidateGate, validate_gate_node


def _hf_with_index(
    tmp_path: Path, html: str, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, str]:
    """Make an hf_dir on disk + route ``materialize_into_tmpdir`` to it.

    HOM-278: ``_has_opacity_zero_entrance`` reads ``state.compose.index_html``.
    HOM-281: the subprocess cwd comes from ``materialize_into_tmpdir``;
    the unit test stubs that helper to return the on-disk fixture dir so
    the patched subprocess runner sees the expected layout.
    """
    hf_dir = tmp_path / "hyperframes"
    hf_dir.mkdir()
    (hf_dir / "index.html").write_text(html, encoding="utf-8")
    monkeypatch.setattr(
        "edit_episode_graph.gates.validate.materialize_into_tmpdir",
        lambda state, slug=None: hf_dir,
    )
    return hf_dir, html


def _state_for(hf_dir: Path, *, index_html: str | None = None) -> dict:
    # ``slug`` is now load-bearing — the gate short-circuits without it.
    state: dict = {"slug": "demo", "compose": {"hyperframes_dir": str(hf_dir)}}
    if index_html is not None:
        state["compose"]["index_html"] = index_html
    return state


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
    hf_dir, html = _hf_with_index(tmp_path, "<html><body></body></html>", monkeypatch)
    _patch_run(monkeypatch, 0, "validate ok\n")

    update = validate_gate_node(_state_for(hf_dir, index_html=html))
    record = update["gate_results"][0]
    assert record["passed"], record["violations"]
    assert "headless_artifact_suspected" not in record


def test_fails_on_real_schema_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    hf_dir, html = _hf_with_index(tmp_path, "<html><body><div>plain</div></body></html>", monkeypatch)
    _patch_run(monkeypatch, 1, "schema error: missing data-hf-anchor on .scene\n")

    update = validate_gate_node(_state_for(hf_dir, index_html=html))
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

    HOM-278: the entrance-pattern body is now sourced from
    ``state.compose.index_html``, not ``<hf>/index.html`` on disk.
    """
    hf_dir, html = _hf_with_index(
        tmp_path,
        """<html><body>
        <div class="hero" style="color: #000">Headline</div>
        <script>
          gsap.fromTo('.hero', { opacity: 0 }, { opacity: 1, duration: 0.5 });
        </script>
        </body></html>""", monkeypatch)
    _patch_run(monkeypatch, 1, "WCAG contrast failure on .hero: ratio 1.0 < 4.5\n")

    update = validate_gate_node(_state_for(hf_dir, index_html=html))
    record = update["gate_results"][0]
    assert record["passed"], record
    assert record["headless_artifact_suspected"] is True
    assert "do NOT iterate" in record["annotation"]
    assert record["validate_exit_code"] == 1
    assert any("headless_artifact_suspected" in n for n in update["notices"])


def test_fails_loudly_on_wcag_failure_without_opacity_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    hf_dir, html = _hf_with_index(
        tmp_path,
        "<html><body><div style='color:#000;background:#222'>x</div></body></html>", monkeypatch)
    _patch_run(monkeypatch, 1, "WCAG contrast failure on div: ratio 1.5 < 4.5\n")

    update = validate_gate_node(_state_for(hf_dir, index_html=html))
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
    hf_dir, html = _hf_with_index(
        tmp_path,
        "<html><body><div style='opacity: 0; color: #000'>hidden</div></body></html>", monkeypatch)
    _patch_run(monkeypatch, 1, "WCAG contrast failure on div: ratio 1.0 < 4.5\n")

    update = validate_gate_node(_state_for(hf_dir, index_html=html))
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
    hf_dir, html = _hf_with_index(
        tmp_path,
        "<html><body><div style='opacity:0'>x</div></body></html>", monkeypatch)
    _patch_run(monkeypatch, 1, "schema error: missing required key palette\n")

    update = validate_gate_node(_state_for(hf_dir, index_html=html))
    record = update["gate_results"][0]
    assert not record["passed"]
    assert "headless_artifact_suspected" not in record


def test_wcag_failure_without_index_html_body_in_state_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """HOM-278 Class A: body absent in state ⇒ no artifact triage fires.

    Without the body the triage can't detect the opacity-0 entrance
    pattern, so a WCAG-looking failure is reported as a real violation
    (no annotation). The materializer is responsible for ensuring the
    body lives in state.compose.index_html before this gate runs; an
    empty channel is treated as the worst case (loud fail).
    """
    hf_dir, _ = _hf_with_index(
        tmp_path,
        """<html><body>
        <script>
          gsap.fromTo('.hero', { opacity: 0 }, { opacity: 1 });
        </script>
        </body></html>""", monkeypatch)
    _patch_run(monkeypatch, 1, "WCAG contrast failure on .hero: ratio 1.0 < 4.5\n")

    # No index_html injected — body absent in state. The disk file is there
    # but the gate must not read it.
    update = validate_gate_node(_state_for(hf_dir))
    record = update["gate_results"][0]
    assert not record["passed"], record
    assert "headless_artifact_suspected" not in record


def test_fails_when_no_slug_in_state():
    update = validate_gate_node({})
    assert not update["gate_results"][0]["passed"]
    assert any("no slug" in v for v in update["gate_results"][0]["violations"])


def test_fails_when_materialize_into_tmpdir_raises(
    monkeypatch: pytest.MonkeyPatch,
):
    def boom(state, slug=None):
        raise RuntimeError("required body field 'compose.index_html' missing")

    monkeypatch.setattr(
        "edit_episode_graph.gates.validate.materialize_into_tmpdir", boom
    )
    update = validate_gate_node({"slug": "demo"})
    assert not update["gate_results"][0]["passed"]
    assert any(
        "materialize_into_tmpdir failed" in v
        for v in update["gate_results"][0]["violations"]
    )
