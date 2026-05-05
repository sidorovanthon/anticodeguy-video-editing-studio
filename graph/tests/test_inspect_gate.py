"""Unit tests for gate:inspect."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from edit_episode_graph.gates import _base
from edit_episode_graph.gates.inspect import (
    InspectGate,
    _beat_start_offsets,
    _leaf_token,
    _opted_out_tokens,
    inspect_gate_node,
)


def _hf_with_index(tmp_path: Path, html: str = "<html></html>") -> Path:
    hf_dir = tmp_path / "hyperframes"
    hf_dir.mkdir()
    (hf_dir / "index.html").write_text(html, encoding="utf-8")
    return hf_dir


def _state_with_plan(hf_dir: Path, beats: list[dict] | None = None) -> dict:
    state: dict = {"compose": {"hyperframes_dir": str(hf_dir)}}
    if beats is not None:
        state["compose"]["plan"] = {"beats": beats}
    return state


def _patch_run(monkeypatch: pytest.MonkeyPatch, exit_code: int, payload):
    captured: dict = {}

    def fake_run(args, hf_dir, **kw):
        captured["args"] = list(args)
        captured["hf_dir"] = hf_dir
        stdout = json.dumps(payload) if not isinstance(payload, str) else payload
        return _base.CliResult(
            cmd=["hyperframes", *list(args)],
            cwd=str(hf_dir),
            exit_code=exit_code,
            stdout=stdout,
            stderr="",
        )

    monkeypatch.setattr("edit_episode_graph.gates.inspect.run_hf_cli", fake_run)
    return captured


def test_passes_when_no_overflows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    hf_dir = _hf_with_index(tmp_path)
    _patch_run(monkeypatch, 0, {"issues": []})

    update = inspect_gate_node(_state_with_plan(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"], record["violations"]
    assert record["gate"] == "gate:inspect"


def test_fails_when_overflow_target_unmarked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    hf_dir = _hf_with_index(
        tmp_path,
        '<html><body><h1 class="hero">Long headline that overflows</h1></body></html>',
    )
    payload = {
        "issues": [
            {
                "type": "overflow",
                "selector": ".scene-1 .hero",
                "timestamp": 1.5,
                "hint": "increase max-width",
            }
        ]
    }
    _patch_run(monkeypatch, 1, payload)

    update = inspect_gate_node(_state_with_plan(hf_dir))
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any(".hero" in v for v in record["violations"])
    assert any("not marked" in v for v in record["violations"])


def test_passes_when_overflow_target_has_marker_directly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    hf_dir = _hf_with_index(
        tmp_path,
        '<html><body>'
        '<h1 class="hero" data-layout-allow-overflow>Headline</h1>'
        '</body></html>',
    )
    payload = {
        "issues": [
            {"type": "overflow", "selector": ".hero", "timestamp": 1.5}
        ]
    }
    _patch_run(monkeypatch, 1, payload)

    update = inspect_gate_node(_state_with_plan(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"], record


def test_passes_when_ancestor_has_marker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Canon: marker on element OR ancestor opts out the subtree."""
    hf_dir = _hf_with_index(
        tmp_path,
        '<html><body>'
        '<section class="scene" data-layout-ignore>'
        '  <div><h1 class="hero">Headline</h1></div>'
        '</section>'
        '</body></html>',
    )
    payload = {"issues": [{"type": "overflow", "selector": ".hero"}]}
    _patch_run(monkeypatch, 1, payload)

    update = inspect_gate_node(_state_with_plan(hf_dir))
    record = update["gate_results"][0]
    assert record["passed"], record


def test_marker_on_unrelated_element_does_not_opt_out_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """A marker on an element that isn't an ancestor of the overflow target
    must not silently opt the target out."""
    hf_dir = _hf_with_index(
        tmp_path,
        '<html><body>'
        '<aside class="decor" data-layout-allow-overflow>side</aside>'
        '<h1 class="hero">Headline</h1>'
        '</body></html>',
    )
    payload = {"issues": [{"type": "overflow", "selector": ".hero"}]}
    _patch_run(monkeypatch, 1, payload)

    update = inspect_gate_node(_state_with_plan(hf_dir))
    record = update["gate_results"][0]
    assert not record["passed"], record


def test_passes_args_at_beat_offsets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    hf_dir = _hf_with_index(tmp_path)
    captured = _patch_run(monkeypatch, 0, {"issues": []})

    state = _state_with_plan(
        hf_dir,
        beats=[
            {"beat": "HOOK", "duration_s": 2.5},
            {"beat": "PROBLEM", "duration_s": 3.0},
            {"beat": "PAYOFF", "duration_s": 4.5},
        ],
    )
    inspect_gate_node(state)

    args = captured["args"]
    assert "--at" in args
    at_value = args[args.index("--at") + 1]
    # Beat starts: 0, 2.5, 5.5
    assert at_value == "0,2.5,5.5"


def test_omits_at_when_no_beats(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    hf_dir = _hf_with_index(tmp_path)
    captured = _patch_run(monkeypatch, 0, {"issues": []})

    inspect_gate_node({"compose": {"hyperframes_dir": str(hf_dir)}})
    assert "--at" not in captured["args"]


def test_fails_when_cli_errors_with_no_parseable_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    hf_dir = _hf_with_index(tmp_path)

    def fake_run(args, hf_dir, **kw):
        return _base.CliResult(
            cmd=["hyperframes", *list(args)],
            cwd=str(hf_dir),
            exit_code=2,
            stdout="",
            stderr="puppeteer: Failed to launch browser\n",
        )

    monkeypatch.setattr("edit_episode_graph.gates.inspect.run_hf_cli", fake_run)

    update = inspect_gate_node(_state_with_plan(hf_dir))
    record = update["gate_results"][0]
    assert not record["passed"]
    assert any("exit=2" in v for v in record["violations"])


def test_fails_when_no_hyperframes_dir_in_state():
    update = inspect_gate_node({})
    assert not update["gate_results"][0]["passed"]


def test_fails_when_hyperframes_dir_missing_on_disk(tmp_path: Path):
    update = inspect_gate_node(
        {"compose": {"hyperframes_dir": str(tmp_path / "nope")}}
    )
    assert not update["gate_results"][0]["passed"]


def test_extract_overflows_from_root_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """CLI may emit a bare list as the JSON root; we still find overflows."""
    hf_dir = _hf_with_index(
        tmp_path, '<html><body><div class="x">x</div></body></html>'
    )
    _patch_run(monkeypatch, 1, [{"type": "overflow", "selector": ".x"}])

    update = inspect_gate_node(_state_with_plan(hf_dir))
    record = update["gate_results"][0]
    assert not record["passed"]


def test_non_overflow_issues_are_ignored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """`inspect` may return non-overflow advisory entries; only overflow-class
    issues block the gate."""
    hf_dir = _hf_with_index(tmp_path, "<html></html>")
    payload = {
        "issues": [
            {"type": "advisory", "selector": ".whatever", "message": "fyi"}
        ]
    }
    _patch_run(monkeypatch, 0, payload)

    update = inspect_gate_node(_state_with_plan(hf_dir))
    assert update["gate_results"][0]["passed"]


# --- Pure-helper tests ---


def test_leaf_token_extraction():
    assert _leaf_token(".scene-1 .headline") == ".headline"
    assert _leaf_token("body > div > #card") == "#card"
    assert _leaf_token("div.stat") == ".stat"
    assert _leaf_token("h1") == "h1"
    assert _leaf_token("#card.big") == "#card"
    assert _leaf_token("") is None


def test_beat_start_offsets_cumulative():
    state = {
        "compose": {
            "plan": {
                "beats": [
                    {"duration_s": 2},
                    {"duration_s": 3.5},
                    {"duration_s": 1.25},
                ]
            }
        }
    }
    assert _beat_start_offsets(state) == [0.0, 2.0, 5.5]


def test_beat_start_offsets_empty():
    assert _beat_start_offsets({}) == []
    assert _beat_start_offsets({"compose": {"plan": {"beats": []}}}) == []


def test_opted_out_tokens_handles_void_tags():
    # <img> is void; its non-presence on the open-element stack must not
    # break ancestor scope tracking.
    html = (
        '<section data-layout-ignore>'
        '<img src="x"><div class="hero">y</div>'
        '</section>'
    )
    assert _opted_out_tokens(html, [".hero"]) == {".hero"}
