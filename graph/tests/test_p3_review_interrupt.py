"""Unit tests for p3_review_interrupt — Phase 3 → Phase 4 review checkpoint.

Mirrors `test_strategy_confirmed_interrupt.py` shape: stub `interrupt()`,
verify payload + the state delta produced by approve / abort decisions.
"""

from __future__ import annotations

from edit_episode_graph.nodes import p3_review_interrupt as node_module
from edit_episode_graph.nodes.p3_review_interrupt import p3_review_interrupt_node


def _stub_interrupt(monkeypatch, decision):
    captured: list[dict] = []

    def fake(payload):
        captured.append(payload)
        return decision

    monkeypatch.setattr(node_module, "interrupt", fake)
    return captured


def _state(**render) -> dict:
    base = {"n_segments": 4, "delta_ms": 12, "cached": False, "duration_s": 62.0}
    base.update(render)
    return {"edit": {"render": base}}


def test_skips_when_already_approved():
    state = {"edit": {"review": {"phase3": {"approved": True}}}}
    assert p3_review_interrupt_node(state) == {}


def test_skips_when_already_aborted():
    state = {"edit": {"review": {"phase3": {"aborted": True}}}}
    assert p3_review_interrupt_node(state) == {}


def test_payload_carries_render_summary(monkeypatch):
    captured = _stub_interrupt(monkeypatch, "approved")
    p3_review_interrupt_node(_state(n_segments=7, delta_ms=-3))

    assert len(captured) == 1
    payload = captured[0]
    assert payload["checkpoint"] == "phase3_review"
    assert payload["artifact"] == "edit/final.mp4"
    assert payload["render"]["n_segments"] == 7
    assert payload["render"]["delta_ms"] == -3
    assert "resume" in payload["hint"].lower()


def test_string_approval_marks_approved(monkeypatch):
    _stub_interrupt(monkeypatch, "approved")
    update = p3_review_interrupt_node(_state())
    assert update["edit"]["review"]["phase3"]["approved"] is True
    assert update["edit"]["review"]["phase3"].get("aborted") in (None, False)


def test_dict_approval_marks_approved(monkeypatch):
    _stub_interrupt(monkeypatch, {"approved": True})
    update = p3_review_interrupt_node(_state())
    assert update["edit"]["review"]["phase3"]["approved"] is True


def test_empty_payload_counts_as_approval(monkeypatch):
    """Mirrors strategy_confirmed_interrupt: empty Submit = "looks good"."""
    for empty in (None, "", "   ", {}):
        _stub_interrupt(monkeypatch, empty)
        update = p3_review_interrupt_node(_state())
        assert update["edit"]["review"]["phase3"]["approved"] is True, empty


def test_abort_string_marks_aborted(monkeypatch):
    for token in ("abort", "ABORT", "no", "stop", "give up"):
        _stub_interrupt(monkeypatch, token)
        update = p3_review_interrupt_node(_state())
        assert update["edit"]["review"]["phase3"]["aborted"] is True, token
        assert update["edit"]["review"]["phase3"].get("approved") in (None, False), token


def test_abort_dict_marks_aborted(monkeypatch):
    _stub_interrupt(monkeypatch, {"abort": True})
    update = p3_review_interrupt_node(_state())
    assert update["edit"]["review"]["phase3"]["aborted"] is True


def test_unknown_payload_defaults_to_approval(monkeypatch):
    """Anything that isn't an explicit abort token is treated as approval —
    we don't want to wedge the run on a typo. Aborts are explicit."""
    _stub_interrupt(monkeypatch, "ship it")
    update = p3_review_interrupt_node(_state())
    assert update["edit"]["review"]["phase3"]["approved"] is True
