"""Unit tests for gate:animation_map flag extraction — HOM-284 trailing
dead-zone carve-out.

Per CLAUDE.md DoD, fresh-tier `record_fixture` runs on
`canonical-portrait-talking-head` produced a dead zone of 22.5s–26.5s
(duration 4.0s) on a 26.283s composition, blocking the run with
"max duration 4.0s exceeds threshold 2.0s (HOM-212)". Root cause:
upstream `animation-map.mjs` enumerates tween end-times as
``start + node.duration()`` which excludes GSAP ``repeat`` cycles, so
ambient yoyo+repeat decoratives that play the full scene length
under-report their total time and create phantom trailing dead zones
at the last scene's tail.

These tests pin the carve-out behaviour: trailing dead zones whose end
touches composition duration AND whose own duration is within the
trailing-max grace are demoted from blocking to advisory; mid-comp
dead zones remain blocking.
"""

from __future__ import annotations

from edit_episode_graph.gates.animation_map import _extract_flags


def _zone(start: float, end: float) -> dict:
    return {"start": start, "end": end, "duration": round(end - start, 1)}


def test_trailing_dead_zone_below_grace_is_advisory_not_blocking():
    """The canonical HOM-284 repro: dead zone 22.5–26.5 (4.0s) on a 26.283s
    composition. End is within tolerance of duration, duration <= grace
    (5.0s default). Should land in advisory dead_zones, NOT in blocking."""
    report = {
        "duration": 26.283,
        "tweens": [],
        "deadZones": [_zone(22.5, 26.5)],
    }
    always_fix, pending, dead_zones, blocking = _extract_flags(report)
    assert blocking == [], f"trailing dead zone should not block: {blocking}"
    assert len(dead_zones) == 1
    assert "trailing dead zone" in dead_zones[0]
    assert "HOM-284" in dead_zones[0]


def test_midcomp_dead_zone_still_blocks():
    """A dead zone that does NOT touch composition end is real — the
    helper's bbox-density measurement is trustworthy mid-comp because
    nothing about a yoyo+repeat tween makes a tween disappear before
    its first cycle. Must still flip to blocking above threshold."""
    report = {
        "duration": 26.283,
        "tweens": [],
        "deadZones": [_zone(5.0, 9.5)],  # 4.5s gap mid-comp
    }
    always_fix, pending, dead_zones, blocking = _extract_flags(report)
    assert len(blocking) == 1
    assert "blocking dead zone" in blocking[0]
    assert "HOM-212" in blocking[0]


def test_trailing_dead_zone_exceeding_grace_still_blocks():
    """If the trailing dead zone is longer than ``dead_zone_trailing_max_s``
    the carve-out does NOT apply — operator wants to see runs where the
    final scene is, say, 8s of pure hold flagged as blocking by default."""
    report = {
        "duration": 26.283,
        "tweens": [],
        "deadZones": [_zone(20.0, 26.5)],  # 6.5s tail, > 5.0s grace
    }
    always_fix, pending, dead_zones, blocking = _extract_flags(report)
    assert len(blocking) == 1, f"expected blocking, got: {blocking}"


def test_trailing_carve_out_disabled_when_grace_zero():
    """Strict-mode operator escape hatch: setting trailing_max=0 disables
    the carve-out entirely, so even sub-grace trailing dead zones block."""
    report = {
        "duration": 26.283,
        "tweens": [],
        "deadZones": [_zone(22.5, 26.5)],
    }
    _, _, dead_zones, blocking = _extract_flags(
        report,
        dead_zone_trailing_max_s=0.0,
    )
    assert len(blocking) == 1, "carve-out must respect strict-mode override"
    # The dead-zone advisory string falls back to the non-carve format.
    assert "trailing dead zone" not in dead_zones[0]


def test_trailing_carve_out_requires_end_at_duration():
    """A dead zone that ends well before composition end is NOT a trailing
    artifact, even if its own duration is short. The carve-out is keyed on
    end-position-near-duration, not on duration-magnitude alone."""
    report = {
        "duration": 26.283,
        "tweens": [],
        # Ends at 24.0, composition ends at 26.283 — 2.3s gap > tolerance
        "deadZones": [_zone(21.0, 24.0)],
    }
    _, _, dead_zones, blocking = _extract_flags(report)
    assert len(blocking) == 1
    assert "trailing" not in blocking[0]


def test_no_dead_zones_clean():
    report = {"duration": 26.283, "tweens": [], "deadZones": []}
    always_fix, pending, dead_zones, blocking = _extract_flags(report)
    assert blocking == []
    assert dead_zones == []


def test_missing_composition_duration_falls_back_to_strict():
    """If the helper output is missing ``duration``, the trailing carve-out
    cannot prove "near end" and falls through to standard blocking. Better
    to false-block than false-pass on a malformed report."""
    report = {
        "tweens": [],
        "deadZones": [_zone(22.5, 26.5)],  # duration field absent
    }
    _, _, dead_zones, blocking = _extract_flags(report)
    assert len(blocking) == 1, "missing duration must not enable carve-out"
