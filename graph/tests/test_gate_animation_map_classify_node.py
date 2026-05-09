"""Unit tests for gate_animation_map_classify (HOM-156, HOM-204).

HOM-156: cheap-tier LLM classifier extracted from the gate body into its
own graph node so cache_policy= actually fires.

HOM-204: classifier output is **advisory**. Its decisions merge into
``advisory_findings.pending_classify`` (each entry annotated with
``decision`` + ``reason``); the follow-up record's ``passed`` is
preserved from the upstream gate record (advisory: True on a healthy
helper run). Routing always advances to ``gate_snapshot`` regardless of
classifier verdicts. Replay-mode coverage lives in
``tests/test_graph_replay.py::test_gate_animation_map_classify_smoke``.
"""

from __future__ import annotations

import pytest

from edit_episode_graph.nodes import gate_animation_map_classify as node_mod
from edit_episode_graph.nodes.gate_animation_map_classify import (
    gate_animation_map_classify_node,
)


def _state_with_pending(*pending: dict, base_violations: list[str] | None = None,
                        upstream_passed: bool = True) -> dict:
    """Build a state whose latest gate:animation_map record carries
    HOM-204 ``advisory_findings.pending_classify`` entries.
    """
    record = {
        "gate": "gate:animation_map",
        "passed": upstream_passed,
        "violations": list(base_violations or []),
        "advisory_findings": {
            "always_fix": [],
            "dead_zones": [],
            "pending_classify": list(pending),
        },
        "iteration": 1,
        "timestamp": "2026-05-09T00:00:00Z",
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


def test_classifier_justify_decision_annotates_pending(monkeypatch):
    """Decision='justify' annotates the pending entry; passed preserved."""
    flagged = {"flag_id": ".flash::1::paced-fast", "selector": ".flash",
               "flag": "paced-fast", "duration": 0.12, "index": 1}
    state = _state_with_pending(flagged)
    _stub_node(monkeypatch, decisions={flagged["flag_id"]: "justify"})
    out = gate_animation_map_classify_node(state)
    rec = out["gate_results"][0]
    assert rec["gate"] == "gate:animation_map"
    assert rec["passed"] is True, "advisory: classifier never flips passed"
    assert rec["violations"] == []
    pending = rec["advisory_findings"]["pending_classify"]
    assert len(pending) == 1
    assert pending[0]["flag_id"] == flagged["flag_id"]
    assert pending[0]["decision"] == "justify"
    assert pending[0]["reason"] == "stub-justify"
    assert rec["classifier_status"] == "ok"


def test_classifier_fix_decision_is_advisory(monkeypatch):
    """HOM-204: decision='fix' is advisory metadata; passed stays True."""
    flagged = {"flag_id": ".flash::1::paced-fast", "selector": ".flash",
               "flag": "paced-fast", "duration": 0.12, "index": 1}
    state = _state_with_pending(flagged)
    _stub_node(monkeypatch, decisions={flagged["flag_id"]: "fix"})
    out = gate_animation_map_classify_node(state)
    rec = out["gate_results"][0]
    assert rec["passed"] is True
    assert rec["violations"] == []
    pending = rec["advisory_findings"]["pending_classify"]
    assert len(pending) == 1
    assert pending[0]["decision"] == "fix"
    assert pending[0]["reason"] == "stub-fix"
    assert rec["classifier_status"] == "ok"


def test_classifier_dispatch_failure_records_advisory_fallback(monkeypatch):
    """HOM-204: dispatch failure ⇒ advisory fallback decisions; passed preserved."""
    flagged = {"flag_id": ".flash::1::paced-fast", "selector": ".flash",
               "flag": "paced-fast", "duration": 0.12, "index": 1}
    state = _state_with_pending(flagged)
    _stub_node(monkeypatch, raise_exc=RuntimeError("backends exhausted"))
    out = gate_animation_map_classify_node(state)
    rec = out["gate_results"][0]
    assert rec["passed"] is True, "advisory: dispatch failure never flips passed"
    assert rec["violations"] == []
    pending = rec["advisory_findings"]["pending_classify"]
    assert len(pending) == 1
    assert pending[0]["decision"] == "fix", "fallback decision is conservative 'fix'"
    assert "dispatch failed" in pending[0]["reason"]
    assert rec["classifier_status"].startswith("failed:")
    assert "RuntimeError" in rec["classifier_status"]


def test_classifier_unstructured_output_records_advisory_fallback(monkeypatch):
    flagged = {"flag_id": ".flash::1::paced-fast", "selector": ".flash",
               "flag": "paced-fast", "duration": 0.12, "index": 1}
    state = _state_with_pending(flagged)
    _stub_node(monkeypatch, raw_text="hello, prose not JSON")
    out = gate_animation_map_classify_node(state)
    rec = out["gate_results"][0]
    assert rec["passed"] is True
    pending = rec["advisory_findings"]["pending_classify"]
    assert len(pending) == 1
    assert pending[0]["decision"] == "fix"
    assert rec["classifier_status"].startswith("failed:")
    assert "unstructured" in rec["classifier_status"] or "malformed" in rec["classifier_status"]


def test_classifier_iteration_counts_prior_records(monkeypatch):
    """The follow-up record's iteration is N+1 where N = prior gate:animation_map records."""
    flagged = {"flag_id": ".flash::1::paced-fast", "selector": ".flash",
               "flag": "paced-fast", "duration": 0.12, "index": 1}
    state = _state_with_pending(flagged)
    _stub_node(monkeypatch, decisions={flagged["flag_id"]: "justify"})
    out = gate_animation_map_classify_node(state)
    assert out["gate_results"][0]["iteration"] == 2


def test_classifier_no_pending_emits_clean_passthrough(monkeypatch):
    """Defensive: if router somehow dispatches with no pending list,
    emit a passthrough record rather than calling the LLM."""
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
    assert rec["advisory_findings"]["pending_classify"] == []
    assert rec["classifier_status"].startswith("skipped:")


def test_classifier_preserves_upstream_advisory_findings(monkeypatch):
    """always_fix and dead_zones from the upstream record pass through unchanged."""
    flagged = {"flag_id": ".flash::1::paced-fast", "selector": ".flash",
               "flag": "paced-fast", "duration": 0.12, "index": 1}
    state = _state_with_pending(flagged)
    # Inject upstream always_fix + dead_zones the classifier should preserve.
    state["gate_results"][0]["advisory_findings"]["always_fix"] = [
        "collision flag(s) on .a, .b — overlapping animated elements; refine layout"
    ]
    state["gate_results"][0]["advisory_findings"]["dead_zones"] = [
        "dead zone 4.0s–5.5s (duration 1.5s > 1.0s) — no animation"
    ]
    _stub_node(monkeypatch, decisions={flagged["flag_id"]: "justify"})
    out = gate_animation_map_classify_node(state)
    rec = out["gate_results"][0]
    advisory = rec["advisory_findings"]
    assert len(advisory["always_fix"]) == 1
    assert "collision" in advisory["always_fix"][0]
    assert len(advisory["dead_zones"]) == 1
    assert "dead zone" in advisory["dead_zones"][0]


def test_classifier_cache_version_is_2():
    """HOM-204 bumped 1→2 because output / input shape changed."""
    assert node_mod._CACHE_VERSION == 2
