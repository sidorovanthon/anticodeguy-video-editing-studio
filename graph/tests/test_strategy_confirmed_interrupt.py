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


def test_invokes_interrupt_with_strategy_summary(monkeypatch):
    """First entry calls interrupt() with the canonical summary keys.

    `interrupt()` raises GraphInterrupt outside a runnable context, so we
    stub it here to verify the payload shape and the post-resume update.
    """
    captured: list[dict] = []

    def fake_interrupt(payload):
        captured.append(payload)
        return "approved"

    monkeypatch.setattr(node_module, "interrupt", fake_interrupt)

    state = {
        "edit": {
            "strategy": {
                "shape": "Cold open then explainer",
                "takes": ["[3.76-10.80]"],
                "grade": "neutral",
                "pacing": "medium",
                "length_estimate_s": 62.0,
            }
        }
    }
    update = strategy_confirmed_interrupt_node(state)

    assert len(captured) == 1
    payload = captured[0]
    assert payload["checkpoint"] == "strategy_confirmed"
    assert payload["strategy"]["length_estimate_s"] == 62.0
    assert payload["strategy"]["shape"] == "Cold open then explainer"
    assert "resume" in payload["hint"].lower()

    # Returned update preserves prior strategy fields and marks approved.
    strategy = update["edit"]["strategy"]
    assert strategy["approved"] is True
    assert strategy["approval_payload"] == "approved"
    assert strategy["length_estimate_s"] == 62.0
    assert strategy["shape"] == "Cold open then explainer"
