"""Schema-level invariants for EDL / Range / Overlay."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from edit_episode_graph.schemas.p3_edl_select import EDL, Range


def _ok_range(**overrides) -> dict:
    base = {"source": "raw", "start": 1.0, "end": 2.0,
            "beat": "X", "quote": "x", "reason": "x"}
    base.update(overrides)
    return base


def test_range_rejects_end_le_start():
    with pytest.raises(ValidationError, match="end .* must be greater than start"):
        Range.model_validate(_ok_range(start=2.0, end=2.0))
    with pytest.raises(ValidationError, match="end .* must be greater than start"):
        Range.model_validate(_ok_range(start=3.0, end=1.0))


def test_range_accepts_normal_ordering():
    r = Range.model_validate(_ok_range(start=1.0, end=1.001))
    assert r.end > r.start


def test_edl_rejects_subtitles_field():
    with pytest.raises(ValidationError, match="subtitles"):
        EDL.model_validate({
            "version": 1,
            "sources": {"raw": "/x"},
            "ranges": [_ok_range()],
            "grade": "neutral",
            "overlays": [],
            "total_duration_s": 1.0,
            "subtitles": "edit/master.srt",
        })


def test_edl_overlays_default_empty():
    edl = EDL.model_validate({
        "version": 1,
        "sources": {"raw": "/x"},
        "ranges": [_ok_range()],
        "grade": "neutral",
        "total_duration_s": 1.0,
    })
    assert edl.overlays == []
