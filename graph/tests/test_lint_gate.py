"""Unit tests for gate:lint."""

from __future__ import annotations

import json
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


def _json_result(hf_dir: Path, payload: dict, exit_code: int = 0) -> _base.CliResult:
    return _base.CliResult(
        cmd=["hyperframes", "lint", "--json"],
        cwd=str(hf_dir),
        exit_code=exit_code,
        stdout=json.dumps(payload),
        stderr="",
    )


def _patch_runner(monkeypatch: pytest.MonkeyPatch, runner):
    monkeypatch.setattr("edit_episode_graph.gates.lint.run_hf_cli", runner)


def test_passes_when_findings_empty(monkeypatch: pytest.MonkeyPatch, hf_project: Path):
    payload = {"ok": True, "errorCount": 0, "warningCount": 0, "findings": []}

    def fake_run(args, hf_dir, **kw):
        return _json_result(hf_dir, payload, exit_code=0)

    _patch_runner(monkeypatch, fake_run)

    update = lint_gate_node(_state_for(hf_project))
    record = update["gate_results"][0]
    assert record["passed"], record["violations"]
    assert record["gate"] == "gate:lint"


def test_real_failures_propagate(monkeypatch: pytest.MonkeyPatch, hf_project: Path):
    payload = {
        "ok": False,
        "errorCount": 0,
        "warningCount": 1,
        "findings": [
            {
                "code": "overlapping_gsap_tweens",
                "severity": "warning",
                "message": "GSAP tweens overlap on '#x' for opacity between 0 and 1.",
                "selector": "#x",
                "file": "index.html",
            }
        ],
    }

    def fake_run(args, hf_dir, **kw):
        return _json_result(hf_dir, payload, exit_code=2)

    _patch_runner(monkeypatch, fake_run)

    update = lint_gate_node(_state_for(hf_project))
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any("overlapping_gsap_tweens" in v for v in record["violations"])
    assert update["notices"] == [
        "gate:lint: FAILED (1 violation(s)) — see gate_results"
    ]


def test_suppresses_subcomp_blocked_codes(
    monkeypatch: pytest.MonkeyPatch, hf_project: Path
):
    """composition_file_too_large + timeline_track_too_dense are blocked
    by HF #589 (sub-comp loader broken). They must be filtered so the
    gate can pass when nothing else is wrong."""
    payload = {
        "ok": False,
        "errorCount": 0,
        "warningCount": 2,
        "findings": [
            {
                "code": "composition_file_too_large",
                "severity": "warning",
                "message": "This HTML composition file has 2151 lines.",
                "file": "index.html",
            },
            {
                "code": "timeline_track_too_dense",
                "severity": "warning",
                "message": "Track 1 has 6 timed elements.",
                "file": "index.html",
            },
        ],
    }

    def fake_run(args, hf_dir, **kw):
        return _json_result(hf_dir, payload, exit_code=2)

    _patch_runner(monkeypatch, fake_run)

    update = lint_gate_node(_state_for(hf_project))
    record = update["gate_results"][0]
    assert record["passed"], record["violations"]


def test_suppression_does_not_swallow_real_findings(
    monkeypatch: pytest.MonkeyPatch, hf_project: Path
):
    payload = {
        "ok": False,
        "errorCount": 1,
        "warningCount": 1,
        "findings": [
            {
                "code": "composition_file_too_large",
                "severity": "warning",
                "message": "huge",
                "file": "index.html",
            },
            {
                "code": "gsap_repeat_ceil_overshoot",
                "severity": "warning",
                "message": "Math.ceil overshoots duration",
                "file": "index.html",
            },
        ],
    }

    def fake_run(args, hf_dir, **kw):
        return _json_result(hf_dir, payload, exit_code=2)

    _patch_runner(monkeypatch, fake_run)

    update = lint_gate_node(_state_for(hf_project))
    record = update["gate_results"][0]
    assert not record["passed"]
    assert len(record["violations"]) == 1
    assert "gsap_repeat_ceil_overshoot" in record["violations"][0]
    assert not any(
        "composition_file_too_large" in v for v in record["violations"]
    )


def test_info_level_findings_ignored(
    monkeypatch: pytest.MonkeyPatch, hf_project: Path
):
    payload = {
        "ok": True,
        "errorCount": 0,
        "warningCount": 0,
        "infoCount": 1,
        "findings": [
            {
                "code": "tip_about_something",
                "severity": "info",
                "message": "advisory",
                "file": "index.html",
            }
        ],
    }

    def fake_run(args, hf_dir, **kw):
        return _json_result(hf_dir, payload, exit_code=0)

    _patch_runner(monkeypatch, fake_run)

    update = lint_gate_node(_state_for(hf_project))
    assert update["gate_results"][0]["passed"]


def test_malformed_finding_entry_surfaces_as_violation_not_fallback(
    monkeypatch: pytest.MonkeyPatch, hf_project: Path
):
    """A non-dict element in findings[] must NOT trigger text-mode fallback.
    Fallback can pass on CLIs that happen to exit 0, masking real failures
    that were parseable in the JSON payload. Surface the malformed entry
    inline instead."""

    calls: list[list[str]] = []
    payload = {
        "ok": False,
        "errorCount": 0,
        "warningCount": 1,
        "findings": [
            "this is not a dict",
            {
                "code": "overlapping_gsap_tweens",
                "severity": "warning",
                "message": "real failure",
                "file": "index.html",
            },
        ],
    }

    def fake_run(args, hf_dir, **kw):
        calls.append(list(args))
        if "--json" in args:
            return _json_result(hf_dir, payload, exit_code=2)
        # If we ever reach here, the fallback fired — that's the bug.
        return _base.CliResult(
            cmd=["hyperframes", *list(args)],
            cwd=str(hf_dir),
            exit_code=0,
            stdout="(no output)",
            stderr="",
        )

    _patch_runner(monkeypatch, fake_run)

    update = lint_gate_node(_state_for(hf_project))
    record = update["gate_results"][0]

    assert calls == [["lint", "--json"]], (
        "fallback to text-mode must NOT fire on a malformed entry — that "
        "would let a 0-exit text-mode mask real parseable failures"
    )
    assert not record["passed"]
    assert any("overlapping_gsap_tweens" in v for v in record["violations"])
    assert any("malformed lint finding" in v for v in record["violations"])


def test_falls_back_to_text_mode_when_json_unparseable(
    monkeypatch: pytest.MonkeyPatch, hf_project: Path
):
    """If --json produces non-JSON output (CLI crash, bootstrap failure)
    the gate must not silently pass — it should re-run without --json
    and surface the raw stderr/stdout."""

    calls: list[list[str]] = []

    def fake_run(args, hf_dir, **kw):
        calls.append(list(args))
        if "--json" in args:
            return _base.CliResult(
                cmd=["hyperframes", *list(args)],
                cwd=str(hf_dir),
                exit_code=1,
                stdout="not json at all",
                stderr="boom",
            )
        return _base.CliResult(
            cmd=["hyperframes", *list(args)],
            cwd=str(hf_dir),
            exit_code=2,
            stdout="repeat: -1 found in non-seek-driven adapter at index.html:42\n",
            stderr="",
        )

    _patch_runner(monkeypatch, fake_run)

    update = lint_gate_node(_state_for(hf_project))
    record = update["gate_results"][0]
    assert calls[0] == ["lint", "--json"]
    assert calls[1] == ["lint"]
    assert not record["passed"]
    assert any("repeat: -1" in v for v in record["violations"])
    assert any("exit=2" in v for v in record["violations"])


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


def test_truncates_very_long_text_fallback(
    monkeypatch: pytest.MonkeyPatch, hf_project: Path
):
    huge = "X" * 5000

    def fake_run(args, hf_dir, **kw):
        if "--json" in args:
            return _base.CliResult(
                cmd=[],
                cwd=str(hf_dir),
                exit_code=1,
                stdout="not json",
                stderr="",
            )
        return _base.CliResult(
            cmd=[],
            cwd=str(hf_dir),
            exit_code=1,
            stdout=huge,
            stderr="",
        )

    _patch_runner(monkeypatch, fake_run)

    update = lint_gate_node(_state_for(hf_project))
    body = update["gate_results"][0]["violations"][0]
    assert "truncated" in body
    assert len(body) < 2000
