"""Unit tests for the p4_materialize_disk no-op writer (HOM-238).

Step C of HOM-230: the materializer reads body fields from state,
asserts mandatory presence, returns a ``materialized_at`` timestamp.
No disk I/O — Step D1 activates writes. These tests pin the read
shape + cache-key determinism so Step D1 can swap in atomic writes
without changing the contract.

Spec: docs/superpowers/specs/2026-05-10-state-first-artifacts.md §6.3,
§"Step C".
"""

from __future__ import annotations

from datetime import datetime

import pytest

from edit_episode_graph.nodes.p4_materialize_disk import (
    _cache_key,
    p4_materialize_disk_node,
)


def _happy_state(*, with_captions: bool = True, with_persist: bool = True) -> dict:
    state = {
        "slug": "demo",
        "compose": {
            "design": {"design_md": "# DESIGN\nbody"},
            "expansion": {"expanded_prompt": "# expanded\nbody"},
            "index_html": "<!doctype html><html><body>scenes here</body></html>",
            "captions": {},
            "persist": {},
        },
        "scenes": {
            "b1": {"html": "<section id='b1'>hook</section>"},
            "b2": {"html": "<section id='b2'>reveal</section>"},
        },
    }
    if with_captions:
        state["compose"]["captions"]["html"] = "<div class='captions'>...</div>"
    if with_persist:
        state["compose"]["persist"]["session_block"] = "## Session 1 — 2026-05-16\n\n- ...\n"
    return state


# --- happy path ------------------------------------------------------------

def test_happy_path_returns_materialized_at_timestamp(tmp_path):
    """Mandatory bodies present → materialized_at ISO timestamp +
    empty files_written. Does NOT raise; does NOT touch disk."""
    update = p4_materialize_disk_node(_happy_state())
    materialize = update["compose"]["materialize"]
    assert materialize["files_written"] == [], (
        "Step C is a no-op — files_written must be empty until Step D1"
    )
    # ISO 8601 parse-back. Raises ValueError if shape drifted.
    datetime.fromisoformat(materialize["materialized_at"])
    # No skip on the happy path.
    assert "skipped" not in materialize
    # Sanity: no stray files anywhere under tmp_path.
    leftover = list(tmp_path.rglob("*"))
    assert leftover == [], (
        f"Step C materializer must not write to disk; found: {leftover}"
    )


def test_happy_path_with_optional_bodies_absent():
    """captions.html and persist.session_block are optional — both
    producers can legitimately skip (captions when transcripts absent;
    persist when assemble skipped). Materializer must succeed."""
    state = _happy_state(with_captions=False, with_persist=False)
    update = p4_materialize_disk_node(state)
    materialize = update["compose"]["materialize"]
    datetime.fromisoformat(materialize["materialized_at"])
    assert materialize["files_written"] == []


# --- mandatory missing ----------------------------------------------------

@pytest.mark.parametrize(
    "drop_path,field_name",
    [
        (("compose", "design", "design_md"), "compose.design.design_md"),
        (("compose", "expansion", "expanded_prompt"),
         "compose.expansion.expanded_prompt"),
        (("compose", "index_html"), "compose.index_html"),
    ],
)
def test_raises_on_missing_mandatory_field(drop_path, field_name):
    state = _happy_state()
    # Walk to parent and remove the leaf key.
    cur = state
    for k in drop_path[:-1]:
        cur = cur[k]
    cur.pop(drop_path[-1], None)
    with pytest.raises(RuntimeError) as exc:
        p4_materialize_disk_node(state)
    assert field_name in str(exc.value)


def test_raises_on_empty_scenes():
    state = _happy_state()
    state["scenes"] = {}
    with pytest.raises(RuntimeError) as exc:
        p4_materialize_disk_node(state)
    assert "scenes" in str(exc.value)


# --- skip propagation -----------------------------------------------------

@pytest.mark.parametrize(
    "skip_section,skip_reason_text",
    [
        ("assemble", "no scenes"),
        ("design", "design upstream broke"),
        ("expansion", "no DESIGN.md"),
    ],
)
def test_propagates_upstream_skip(skip_section, skip_reason_text):
    """Any upstream skip (assemble / design / expansion) → materializer
    returns its own skip block. No RuntimeError; no materialized_at."""
    # Don't bother populating mandatory bodies — the skip check fires first.
    state = {
        "slug": "demo",
        "compose": {
            skip_section: {"skipped": True, "skip_reason": skip_reason_text},
        },
    }
    update = p4_materialize_disk_node(state)
    materialize = update["compose"]["materialize"]
    assert materialize["skipped"] is True
    assert skip_section in materialize["skip_reason"]
    assert skip_reason_text in materialize["skip_reason"]
    assert "materialized_at" not in materialize


# --- cache-key determinism (spec §11 risk pin) ----------------------------

def test_cache_key_is_scene_order_independent():
    """Parallel ``Send`` completion order from p4_beat is
    non-deterministic; the materializer's cache key must hash scenes via
    sorted-by-key iteration so two state shapes that differ ONLY in
    scenes dict insertion order produce the same key. Spec §11 risk
    "Materializer cache key non-determinism"."""
    state_a = _happy_state()
    state_a["scenes"] = {
        "b1": {"html": "<section id='b1'>x</section>"},
        "b2": {"html": "<section id='b2'>y</section>"},
        "b3": {"html": "<section id='b3'>z</section>"},
    }
    state_b = _happy_state()
    # Same scene set, reversed insertion order.
    state_b["scenes"] = {
        "b3": {"html": "<section id='b3'>z</section>"},
        "b1": {"html": "<section id='b1'>x</section>"},
        "b2": {"html": "<section id='b2'>y</section>"},
    }
    assert _cache_key(state_a) == _cache_key(state_b)


def test_cache_key_changes_when_scene_body_changes():
    """Sanity — same scenes set but different HTML content must miss."""
    state_a = _happy_state()
    state_b = _happy_state()
    state_b["scenes"]["b1"] = {"html": "<section id='b1'>DIFFERENT</section>"}
    assert _cache_key(state_a) != _cache_key(state_b)


def test_cache_key_changes_when_optional_body_appears():
    """Including an optional body (captions / persist) when previously
    absent should miss — the materialized content changes."""
    without = _happy_state(with_captions=False)
    with_caps = _happy_state(with_captions=True)
    assert _cache_key(without) != _cache_key(with_caps)
