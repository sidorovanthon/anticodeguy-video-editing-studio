"""Unit tests for `duration_tolerance_ms` (HOM-116d cap)."""

from __future__ import annotations

from edit_episode_graph._render_constants import duration_tolerance_ms


def test_baseline_one_segment():
    assert duration_tolerance_ms(1) == 150


def test_grows_linearly_below_cap():
    # N=2..7: linear formula 100 + 50*N stays under the 500ms cap.
    assert duration_tolerance_ms(2) == 200
    assert duration_tolerance_ms(5) == 350
    assert duration_tolerance_ms(7) == 450


def test_cap_engages_at_n_eight():
    # 100 + 50*8 == 500 — exactly on the cap, stays at 500.
    assert duration_tolerance_ms(8) == 500


def test_cap_clamps_long_form():
    # N=20: linear would give 1100ms (wide enough to mask render bugs);
    # cap holds it at 500ms.
    assert duration_tolerance_ms(20) == 500
    assert duration_tolerance_ms(30) == 500
    assert duration_tolerance_ms(100) == 500


def test_cap_is_500ms():
    """Lock the cap value — changing it requires updating the rationale
    in the docstring and the genuine-failure detection assumptions."""
    from edit_episode_graph._render_constants import _TOLERANCE_CAP_MS
    assert _TOLERANCE_CAP_MS == 500
