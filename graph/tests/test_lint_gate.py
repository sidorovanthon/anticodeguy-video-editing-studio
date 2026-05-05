"""Unit tests for gate:lint."""

from __future__ import annotations

from pathlib import Path

import pytest

from edit_episode_graph.gates import _base
from edit_episode_graph.gates.lint import LintGate, lint_gate_node


@pytest.fixture()
def hf_project(tmp_path: Path) -> Path:
    hf_dir = tmp_path / "hyperframes"
    hf_dir.mkdir()
    (hf_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    return hf_dir


def _state_for(hf_dir: Path) -> dict:
    return {"compose": {"hyperframes_dir": str(hf_dir)}}


def test_passes_when_cli_exits_zero(monkeypatch: pytest.MonkeyPatch, hf_project: Path):
    def fake_run(args, hf_dir, **kw):
        return _base.CliResult(
            cmd=["hyperframes", *list(args)],
            cwd=str(hf_dir),
            exit_code=0,
            stdout="ok\n",
            stderr="",
        )

    monkeypatch.setattr(_base, "run_hf_cli", fake_run)
    monkeypatch.setattr("edit_episode_graph.gates.lint.run_hf_cli", fake_run)

    update = lint_gate_node(_state_for(hf_project))
    record = update["gate_results"][0]
    assert record["passed"], record["violations"]
    assert record["gate"] == "gate:lint"


def test_fails_with_cli_output_when_cli_exits_non_zero(
    monkeypatch: pytest.MonkeyPatch, hf_project: Path
):
    def fake_run(args, hf_dir, **kw):
        return _base.CliResult(
            cmd=["hyperframes", *list(args)],
            cwd=str(hf_dir),
            exit_code=2,
            stdout="repeat: -1 found in non-seek-driven adapter at index.html:42\n",
            stderr="",
        )

    monkeypatch.setattr("edit_episode_graph.gates.lint.run_hf_cli", fake_run)

    update = lint_gate_node(_state_for(hf_project))
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any("repeat: -1" in v for v in record["violations"])
    assert any("exit=2" in v for v in record["violations"])
    assert update["notices"] == [
        "gate:lint: FAILED (1 violation(s)) — see gate_results"
    ]


def test_fails_when_no_hyperframes_dir_in_state():
    update = lint_gate_node({})
    assert not update["gate_results"][0]["passed"]
    assert any(
        "no hyperframes_dir" in v for v in update["gate_results"][0]["violations"]
    )


def test_fails_when_hyperframes_dir_missing_on_disk(tmp_path: Path):
    state = {"compose": {"hyperframes_dir": str(tmp_path / "nope")}}
    update = lint_gate_node(state)
    assert not update["gate_results"][0]["passed"]
    assert any(
        "not on disk" in v for v in update["gate_results"][0]["violations"]
    )


def test_truncates_very_long_cli_output(monkeypatch: pytest.MonkeyPatch, hf_project: Path):
    huge = "X" * 5000

    def fake_run(args, hf_dir, **kw):
        return _base.CliResult(
            cmd=[],
            cwd=str(hf_dir),
            exit_code=1,
            stdout=huge,
            stderr="",
        )

    monkeypatch.setattr("edit_episode_graph.gates.lint.run_hf_cli", fake_run)

    update = lint_gate_node(_state_for(hf_project))
    body = update["gate_results"][0]["violations"][0]
    assert "truncated" in body
    assert len(body) < 2000
