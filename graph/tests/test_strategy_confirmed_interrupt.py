"""Unit tests for strategy_confirmed_interrupt — HR 11 approval node."""

from __future__ import annotations

from edit_episode_graph.nodes import strategy_confirmed_interrupt as node_module
from edit_episode_graph.nodes.strategy_confirmed_interrupt import (
    strategy_confirmed_interrupt_node,
)


def test_skips_when_strategy_skipped():
    state = {"edit": {"strategy": {"skipped": True, "skip_reason": "no input"}}}
    assert strategy_confirmed_interrupt_node(state) == {}


def test_skips_when_already_approved():
    state = {
        "edit": {
            "strategy": {
                "shape": "x",
                "length_estimate_s": 10.0,
                "approved": True,
                "approval_payload": "approved",
            }
        }
    }
    assert strategy_confirmed_interrupt_node(state) == {}


def _stub_interrupt(monkeypatch, decision):
    captured: list[dict] = []

    def fake(payload):
        captured.append(payload)
        return decision

    monkeypatch.setattr(node_module, "interrupt", fake)
    return captured


def _strategy_state(**overrides) -> dict:
    base = {
        "shape": "Cold open then explainer",
        "takes": ["[3.76-10.80]"],
        "grade": "neutral",
        "pacing": "medium",
        "length_estimate_s": 62.0,
    }
    base.update(overrides)
    return {"edit": {"strategy": base}}


def test_invokes_interrupt_with_strategy_summary(monkeypatch):
    """First entry calls interrupt() with the canonical summary keys.

    `interrupt()` raises GraphInterrupt outside a runnable context, so we
    stub it here to verify the payload shape and the post-resume update.
    """
    captured = _stub_interrupt(monkeypatch, "approved")
    update = strategy_confirmed_interrupt_node(_strategy_state())

    assert len(captured) == 1
    payload = captured[0]
    assert payload["checkpoint"] == "strategy_confirmed"
    assert payload["strategy"]["length_estimate_s"] == 62.0
    assert payload["strategy"]["shape"] == "Cold open then explainer"
    assert "resume" in payload["hint"].lower()

    # Approval intent: strategy preserved + approved + payload recorded.
    strategy = update["edit"]["strategy"]
    assert strategy["approved"] is True
    assert strategy["approval_payload"] == "approved"
    assert strategy["length_estimate_s"] == 62.0
    assert strategy["shape"] == "Cold open then explainer"


def test_dict_approval_token_passes(monkeypatch):
    _stub_interrupt(monkeypatch, {"approved": True})
    update = strategy_confirmed_interrupt_node(_strategy_state())
    assert update["edit"]["strategy"]["approved"] is True


def test_string_revision_appends_to_revisions_and_does_not_approve(monkeypatch):
    """Bug-fix regression: 'Target loudness = -14 LUFS' must not auto-approve.

    Resume payloads that aren't approval tokens are revision feedback; the
    node must NOT mark approved=true and must append to strategy_revisions
    so the routing sends control back to p3_strategy.
    """
    _stub_interrupt(monkeypatch, "Target loudness = -14 LUFS")
    update = strategy_confirmed_interrupt_node(_strategy_state())

    # Critical: no edit.strategy in the update — that would dict_merge an
    # `approved` field. Only top-level append-only fields.
    assert "edit" not in update
    assert update["strategy_revisions"] == ["Target loudness = -14 LUFS"]
    assert any("revision queued" in n for n in update.get("notices") or [])


def test_approval_intent_is_case_insensitive(monkeypatch):
    for token in ("YES", "Approved", "ok"):
        _stub_interrupt(monkeypatch, token)
        update = strategy_confirmed_interrupt_node(_strategy_state())
        assert update["edit"]["strategy"]["approved"] is True, token


def test_dict_with_extra_keys_treated_as_revision(monkeypatch):
    """{'approved': True, 'note': '...'} is a revision, not pure approval."""
    decision = {"approved": True, "note": "tighten the cold open"}
    _stub_interrupt(monkeypatch, decision)
    update = strategy_confirmed_interrupt_node(_strategy_state())
    assert "edit" not in update
    assert len(update["strategy_revisions"]) == 1
