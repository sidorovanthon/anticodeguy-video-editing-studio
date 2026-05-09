"""Unit tests for gate_animation_map_classify (HOM-156 review S1).

Stub-based behavioural coverage of the cheap-tier LLM classifier extracted
into its own graph node. Mirrors the prior in-gate-body tests
(`test_paced_fast_is_*`) but exercises the node body directly. Replay-
mode coverage lives in `tests/test_graph_replay.py::test_gate_animation_map_classify_smoke`.
"""

from __future__ import annotations

import pytest

from edit_episode_graph.nodes import gate_animation_map_classify as node_mod
from edit_episode_graph.nodes.gate_animation_map_classify import (
    gate_animation_map_classify_node,
)


def _state_with_pending(*pending: dict, base_violations: list[str] | None = None) -> dict:
    record = {
        "gate": "gate:animation_map",
        "passed": False,
        "violations": list(base_violations or []),
        "iteration": 1,
        "timestamp": "2026-05-09T00:00:00Z",
        "pending_justifiable": list(pending),
    }
    return {
        "slug": "fp-fixture",
        "compose": {
            "hyperframes_dir": "/tmp/fp/hyperframes",
            "design_md_path": "/tmp/fp/hyperframes/DESIGN.md",
            "plan": {"beats": []},
        },
        "gate_results": [record],
    }


def _stub_node(monkeypatch, *, decisions: dict[str, str] | None = None,
               raise_exc: Exception | None = None,
               raw_text: str | None = None):
    """Replace LLMNode.__call__ with a stub that emits canned classify output."""
    decisions = decisions or {}

    class _Stub:
        def __call__(self, state, *, router=None):
            if raise_exc is not None:
                raise raise_exc
            if raw_text is not None:
                return {"compose": {"classify_decisions": {"raw_text": raw_text}}}
            flags = []
            for fid, verdict in decisions.items():
                flags.append({
                    "flag_id": fid,
                    "decision": verdict,
                    "reason": f"stub-{verdict}",
                })
            return {"compose": {"classify_decisions": {"flags": flags}}}

    monkeypatch.setattr(node_mod, "_build_node", lambda: _Stub())


def test_classifier_justify_passes(monkeypatch):
    flagged = {"flag_id": ".flash::1::paced-fast", "selector": ".flash",
               "flag": "paced-fast", "duration": 0.12, "index": 1}
    state = _state_with_pending(flagged)
    _stub_node(monkeypatch, decisions={flagged["flag_id"]: "justify"})
    out = gate_animation_map_classify_node(state)
    rec = out["gate_results"][0]
    assert rec["gate"] == "gate:animation_map"
    assert rec["passed"] is True
    assert rec["violations"] == []
    assert rec.get("justifications")
    assert rec["justifications"][0]["flag"] == "paced-fast"


def test_classifier_fix_emits_violation(monkeypatch):
    flagged = {"flag_id": ".flash::1::paced-fast", "selector": ".flash",
               "flag": "paced-fast", "duration": 0.12, "index": 1}
    state = _state_with_pending(flagged)
    _stub_node(monkeypatch, decisions={flagged["flag_id"]: "fix"})
    out = gate_animation_map_classify_node(state)
    rec = out["gate_results"][0]
    assert rec["passed"] is False
    joined = " ".join(rec["violations"])
    assert "paced-fast" in joined and "stub-fix" in joined


def test_classifier_dispatch_failure_treated_as_fix(monkeypatch):
    flagged = {"flag_id": ".flash::1::paced-fast", "selector": ".flash",
               "flag": "paced-fast", "duration": 0.12, "index": 1}
    state = _state_with_pending(flagged)
    _stub_node(monkeypatch, raise_exc=RuntimeError("backends exhausted"))
    out = gate_animation_map_classify_node(state)
    rec = out["gate_results"][0]
    assert rec["passed"] is False
    joined = " ".join(rec["violations"])
    assert "dispatch failed" in joined
    assert "classifier unavailable" in joined


def test_classifier_unstructured_output_treated_as_fix(monkeypatch):
    flagged = {"flag_id": ".flash::1::paced-fast", "selector": ".flash",
               "flag": "paced-fast", "duration": 0.12, "index": 1}
    state = _state_with_pending(flagged)
    _stub_node(monkeypatch, raw_text="hello, prose not JSON")
    out = gate_animation_map_classify_node(state)
    rec = out["gate_results"][0]
    assert rec["passed"] is False
    joined = " ".join(rec["violations"])
    assert "unstructured" in joined or "malformed" in joined


def test_classifier_iteration_counts_prior_records(monkeypatch):
    """The follow-up record's iteration is N+1 where N = prior gate:animation_map records."""
    flagged = {"flag_id": ".flash::1::paced-fast", "selector": ".flash",
               "flag": "paced-fast", "duration": 0.12, "index": 1}
    state = _state_with_pending(flagged)
    _stub_node(monkeypatch, decisions={flagged["flag_id"]: "justify"})
    out = gate_animation_map_classify_node(state)
    # State had 1 prior record; new record is iteration 2.
    assert out["gate_results"][0]["iteration"] == 2


def test_classifier_no_pending_emits_clean_record(monkeypatch):
    """Defensive: if router somehow dispatches with no pending list,
    emit a clean record rather than calling the LLM."""
    state = _state_with_pending()  # no pending flags
    called = {"hit": False}

    def fake_build():
        class _S:
            def __call__(self, state, *, router=None):
                called["hit"] = True
                return {"compose": {"classify_decisions": {"flags": []}}}
        return _S()

    monkeypatch.setattr(node_mod, "_build_node", fake_build)
    out = gate_animation_map_classify_node(state)
    assert called["hit"] is False
    rec = out["gate_results"][0]
    assert rec["passed"] is True
