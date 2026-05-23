"""Unit tests for the HOMESTUDIO_STEP_DEBUG=1 wrapper (HOM-334 Phase A).

Two-part contract:

  1. Flag unset → ``step_debug_pre`` / ``step_debug_post`` are complete
     no-ops. No ``langgraph.types.interrupt`` import, no disk write, no
     exception path.
  2. Flag set → both helpers call ``interrupt(payload)`` with a JSON-
     serialisable structured blob carrying the documented schema; the
     resume payload is interpreted (``approve`` / ``abort``).

See ``docs/step-debug-inventory.md`` for the node list this protects.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from edit_episode_graph import _step_debug
from edit_episode_graph._step_debug import (
    StepDebugAborted,
    is_enabled,
    step_debug_post,
    step_debug_pre,
    wrap_deterministic_node,
    wrap_llm_node_call,
)


# --------------------------------------------------------------------------- #
# Test helpers
# --------------------------------------------------------------------------- #


@pytest.fixture
def enabled(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("HOMESTUDIO_STEP_DEBUG", "1")
    monkeypatch.setenv("HOMESTUDIO_STEP_DEBUG_DUMP_ROOT", str(tmp_path))
    yield tmp_path


@pytest.fixture
def disabled(monkeypatch):
    monkeypatch.delenv("HOMESTUDIO_STEP_DEBUG", raising=False)
    yield


def _stub_interrupt(monkeypatch, decision):
    """Stub ``langgraph.types.interrupt`` to capture payloads + return ``decision``."""
    captured: list[dict] = []
    import langgraph.types as lg_types

    def fake(payload):
        captured.append(payload)
        return decision

    monkeypatch.setattr(lg_types, "interrupt", fake)
    return captured


# --------------------------------------------------------------------------- #
# Disabled-flag path: complete no-op
# --------------------------------------------------------------------------- #


def test_is_enabled_false_when_unset(disabled):
    assert is_enabled() is False


def test_is_enabled_truthy_values(monkeypatch):
    for v in ["1", "true", "yes", "on", "TRUE"]:
        monkeypatch.setenv("HOMESTUDIO_STEP_DEBUG", v)
        assert is_enabled() is True
    monkeypatch.setenv("HOMESTUDIO_STEP_DEBUG", "0")
    assert is_enabled() is False
    monkeypatch.setenv("HOMESTUDIO_STEP_DEBUG", "")
    assert is_enabled() is False


def test_step_debug_pre_noop_when_disabled(disabled, monkeypatch):
    # If anything tried to call interrupt, it would crash here.
    import langgraph.types as lg_types

    def boom(payload):
        raise AssertionError(
            "interrupt() must NOT be called when HOMESTUDIO_STEP_DEBUG is unset"
        )

    monkeypatch.setattr(lg_types, "interrupt", boom)
    # Must return None and not raise.
    assert step_debug_pre("p4_beat", {"slug": "x"}, context={"a": 1}) is None
    assert step_debug_post("p4_beat", {"compose": {}}) is None


def test_wrap_llm_node_call_passthrough_when_disabled(disabled):
    calls = []

    def inner():
        calls.append(1)
        return {"llm_runs": []}

    out = wrap_llm_node_call(
        "p3_pre_scan",
        brief_template="hello {{ slug }}",
        output_schema=None,
        state={"slug": "x"},
        render_ctx={"slug": "x"},
        upstream_gate_findings=None,
        inner=inner,
    )
    assert out == {"llm_runs": []}
    assert calls == [1]


def test_wrap_deterministic_node_passthrough_when_disabled(disabled):
    def inner():
        return {"compose": {"catalog": {}}}

    out = wrap_deterministic_node(
        "p4_catalog_scan",
        state={"slug": "x"},
        context={"slug": "x"},
        inner=inner,
    )
    assert out == {"compose": {"catalog": {}}}


# --------------------------------------------------------------------------- #
# Enabled-flag path: interrupt fires, payload validates
# --------------------------------------------------------------------------- #


_REQUIRED_PRE_KEYS = {
    "phase",
    "node",
    "ts",
    "brief_path",
    "brief_rendered_excerpt",
    "context_keys",
    "context_dump_path",
    "expected_schema",
    "upstream_gate_findings",
    "resume_vocabulary",
}

_REQUIRED_POST_KEYS = {
    "phase",
    "node",
    "ts",
    "output_excerpt",
    "output_dump_path",
    "tokens",
    "latency_s",
    "snapshot_png_path",
    "lint_findings",
    "resume_vocabulary",
}


def test_pre_payload_schema(enabled, monkeypatch):
    captured = _stub_interrupt(monkeypatch, "approved")
    step_debug_pre(
        "p4_beat",
        {"slug": "abc", "_thread_id": "t1"},
        brief_path="briefs/p4_beat.j2",
        brief_rendered="hello world",
        context={"scene_id": "hook", "beat_index": 0},
        expected_schema=None,
        upstream_gate_findings=[{"gate": "gate:lint", "passed": True}],
    )
    assert len(captured) == 1
    payload = captured[0]
    assert set(payload.keys()) >= _REQUIRED_PRE_KEYS
    assert payload["phase"] == "pre"
    assert payload["node"] == "p4_beat"
    assert payload["brief_path"] == "briefs/p4_beat.j2"
    assert payload["brief_rendered_excerpt"] == "hello world"
    assert sorted(payload["context_keys"]) == ["beat_index", "scene_id"]
    assert payload["resume_vocabulary"] == [
        "approve",
        "rerun-with-edit:<state-patch-json>",
        "abort",
    ]
    # The full payload must be JSON-serialisable (the runtime ships it as-is).
    json.dumps(payload)


def test_post_payload_schema(enabled, monkeypatch):
    captured = _stub_interrupt(monkeypatch, "approved")
    step_debug_post(
        "p4_beat",
        {"scenes": {"hook": {"html": "<div/>"}}, "llm_runs": [{"tokens_in": 100, "tokens_out": 50, "backend": "claude", "model": "claude-opus-4-7"}]},
        token_usage={"input": 100, "output": 50},
        latency_s=2.5,
        snapshot_png_path="tmp/step-debug/t1/p4_beat/x.png",
        lint_findings=[],
        state={"slug": "abc", "_thread_id": "t1"},
    )
    assert len(captured) == 1
    payload = captured[0]
    assert set(payload.keys()) >= _REQUIRED_POST_KEYS
    assert payload["phase"] == "post"
    assert payload["node"] == "p4_beat"
    assert payload["snapshot_png_path"] == "tmp/step-debug/t1/p4_beat/x.png"
    json.dumps(payload)


def test_approve_resume_returns_normally(enabled, monkeypatch):
    _stub_interrupt(monkeypatch, "approved")
    # Should not raise.
    step_debug_pre("p4_beat", {"slug": "x"})
    step_debug_post("p4_beat", {"ok": True}, state={"slug": "x"})


def test_empty_resume_is_approval(enabled, monkeypatch):
    for payload in (None, "", {}, True):
        _stub_interrupt(monkeypatch, payload)
        step_debug_pre("p4_beat", {"slug": "x"})  # should not raise


def test_abort_resume_raises(enabled, monkeypatch):
    _stub_interrupt(monkeypatch, "abort")
    with pytest.raises(StepDebugAborted) as exc_info:
        step_debug_pre("p4_beat", {"slug": "x"})
    assert exc_info.value.node == "p4_beat"
    assert exc_info.value.phase == "pre"


def test_abort_resume_in_post_raises(enabled, monkeypatch):
    _stub_interrupt(monkeypatch, "abort")
    with pytest.raises(StepDebugAborted) as exc_info:
        step_debug_post("p4_beat", {"ok": True}, state={"slug": "x"})
    assert exc_info.value.phase == "post"


def test_abort_resume_dict_form_raises(enabled, monkeypatch):
    _stub_interrupt(monkeypatch, {"action": "abort"})
    with pytest.raises(StepDebugAborted):
        step_debug_pre("p4_beat", {"slug": "x"})


def test_rerun_with_edit_passes_through_without_abort(enabled, monkeypatch):
    # `rerun-with-edit:...` is an orchestrator-side dispatch pattern; the
    # graph-side wrapper does NOT abort — it returns normally so the runtime
    # can later replay via `update_state(as_node=...) + runs.create()`.
    _stub_interrupt(monkeypatch, "rerun-with-edit:{\"slug\":\"x\"}")
    step_debug_pre("p4_beat", {"slug": "x"})


def test_context_dump_written_to_disk(enabled, monkeypatch):
    captured = _stub_interrupt(monkeypatch, "approved")
    step_debug_pre(
        "p4_beat",
        {"slug": "abc", "_thread_id": "t-dump-test"},
        context={"scene_id": "hook"},
    )
    dump_path = captured[0]["context_dump_path"]
    assert dump_path is not None
    assert Path(dump_path).exists()
    body = json.loads(Path(dump_path).read_text(encoding="utf-8"))
    assert body["context"]["scene_id"] == "hook"


def test_excerpt_truncation(enabled, monkeypatch):
    captured = _stub_interrupt(monkeypatch, "approved")
    huge = "x" * 20_000
    step_debug_pre("p4_beat", {"slug": "x"}, brief_rendered=huge)
    excerpt = captured[0]["brief_rendered_excerpt"]
    assert len(excerpt) < 5_000
    assert "truncated" in excerpt


def test_wrap_llm_node_call_fires_pre_and_post(enabled, monkeypatch):
    captured = _stub_interrupt(monkeypatch, "approved")
    calls = []

    def inner():
        calls.append(1)
        return {"llm_runs": [{"tokens_in": 10, "tokens_out": 5}]}

    out = wrap_llm_node_call(
        "p3_pre_scan",
        brief_template="hello {{ slug }}",
        output_schema=None,
        state={"slug": "x"},
        render_ctx={"slug": "x"},
        upstream_gate_findings=None,
        inner=inner,
    )
    assert calls == [1]
    assert out == {"llm_runs": [{"tokens_in": 10, "tokens_out": 5}]}
    # Two interrupt() calls — pre + post.
    assert len(captured) == 2
    assert captured[0]["phase"] == "pre"
    assert captured[1]["phase"] == "post"
    # Tokens propagated from llm_runs into the post payload.
    assert captured[1]["tokens"]["input"] == 10
    assert captured[1]["tokens"]["output"] == 5


def test_wrap_deterministic_node_fires_pre_and_post(enabled, monkeypatch):
    captured = _stub_interrupt(monkeypatch, "approved")

    def inner():
        return {"compose": {"catalog": {"blocks": []}}}

    out = wrap_deterministic_node(
        "p4_catalog_scan",
        state={"slug": "x"},
        context={"slug": "x"},
        inner=inner,
    )
    assert out == {"compose": {"catalog": {"blocks": []}}}
    assert len(captured) == 2
    assert captured[0]["phase"] == "pre"
    assert captured[1]["phase"] == "post"
    # Deterministic nodes have no tokens, no schema.
    assert captured[1]["tokens"] is None
    assert captured[0]["expected_schema"] is None


def test_abort_in_wrap_llm_node_call(enabled, monkeypatch):
    _stub_interrupt(monkeypatch, "abort")

    def inner():
        raise AssertionError("inner must not run when pre aborts")

    with pytest.raises(StepDebugAborted):
        wrap_llm_node_call(
            "p3_pre_scan",
            brief_template="x",
            output_schema=None,
            state={"slug": "x"},
            render_ctx={"slug": "x"},
            upstream_gate_findings=None,
            inner=inner,
        )
