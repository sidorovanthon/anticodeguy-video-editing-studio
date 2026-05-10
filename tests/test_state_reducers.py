"""Unit tests for ``state.py`` reducer helpers.

HOM-231 — covers the new ``_scenes_merge`` reducer landed for the
HOM-230 state-first-artifacts epic (Step A). Spec source-of-truth:
``docs/superpowers/specs/2026-05-10-state-first-artifacts.md`` §10 Step A.

The reducer is the only place we control the iteration order of the
``compose.scenes`` channel — parallel ``Send`` completion order is
non-deterministic, so the materializer's cache key (spec §6.3) would
flap without a sort here. These tests pin the contract so future edits
to the reducer can't silently break the fingerprint invariant.
"""

from __future__ import annotations

import hashlib
import json

from edit_episode_graph.state import _scenes_merge


def test_scenes_merge_union() -> None:
    left = {"a": {"html": "<a/>"}}
    right = {"b": {"html": "<b/>"}}
    out = _scenes_merge(left, right)
    assert out == {"a": {"html": "<a/>"}, "b": {"html": "<b/>"}}


def test_scenes_merge_conflict_right_wins() -> None:
    left = {"a": {"html": "<old/>"}}
    right = {"a": {"html": "<new/>"}}
    out = _scenes_merge(left, right)
    assert out == {"a": {"html": "<new/>"}}


def test_scenes_merge_sort_stable() -> None:
    a = _scenes_merge({"b": 1, "a": 2}, {"c": 3})
    b = _scenes_merge({"c": 3}, {"b": 1, "a": 2})
    assert list(a.keys()) == ["a", "b", "c"]
    assert list(b.keys()) == ["a", "b", "c"]


def _fp(d: dict) -> str:
    return hashlib.sha256(
        json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def test_scenes_merge_fingerprint_invariant() -> None:
    """sha256 over the reducer output is invariant under input reordering."""
    left = {"intro": {"html": "<i/>"}, "body": {"html": "<b/>"}}
    right = {"outro": {"html": "<o/>"}}
    fp1 = _fp(_scenes_merge(left, right))
    fp2 = _fp(_scenes_merge(right, left))
    assert fp1 == fp2

    # Also: insertion-order shuffles within a single side don't matter.
    shuffled_left = {"body": {"html": "<b/>"}, "intro": {"html": "<i/>"}}
    fp3 = _fp(_scenes_merge(shuffled_left, right))
    assert fp1 == fp3


def test_scenes_merge_handles_none_inputs() -> None:
    """Defensive: LangGraph may pass ``None`` for an empty channel snapshot."""
    assert _scenes_merge(None, {"a": {"html": "<a/>"}}) == {"a": {"html": "<a/>"}}
    assert _scenes_merge({"a": {"html": "<a/>"}}, None) == {"a": {"html": "<a/>"}}
    assert _scenes_merge(None, None) == {}
