"""Tests for remap_transcript."""
import json
import math
from pathlib import Path

import pytest

from scripts.remap_transcript import remap

FIXTURES = Path(__file__).parent / "fixtures"


def _approx_equal(a: list[dict], b: list[dict]) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x["text"] != y["text"]:
            return False
        if not math.isclose(x["start"], y["start"], abs_tol=1e-6):
            return False
        if not math.isclose(x["end"], y["end"], abs_tol=1e-6):
            return False
    return True


def test_golden_remap():
    raw = json.loads((FIXTURES / "scribe_raw.json").read_text(encoding="utf-8"))
    edl = json.loads((FIXTURES / "sample_edl.json").read_text(encoding="utf-8"))
    expected = json.loads((FIXTURES / "expected_final.json").read_text(encoding="utf-8"))
    actual = remap(raw=raw, edl=edl)
    assert _approx_equal(actual, expected), f"mismatch:\nactual={actual}\nexpected={expected}"


def test_audio_events_dropped():
    raw = {"words": [
        {"text": "(laughs)", "type": "audio_event", "start": 1.0, "end": 1.5, "speaker_id": "S0"},
        {"text": "hi", "type": "word", "start": 2.0, "end": 2.2, "speaker_id": "S0"},
    ]}
    edl = {"sources": {"r": "x"}, "ranges": [{"source": "r", "start": 0.0, "end": 3.0}]}
    out = remap(raw=raw, edl=edl)
    assert out == [{"text": "hi", "start": 2.0, "end": 2.2}]


def test_spacing_dropped():
    raw = {"words": [
        {"text": "hi", "type": "word", "start": 1.0, "end": 1.2, "speaker_id": "S0"},
        {"text": " ", "type": "spacing", "start": 1.2, "end": 1.3, "speaker_id": "S0"},
        {"text": "you", "type": "word", "start": 1.3, "end": 1.5, "speaker_id": "S0"},
    ]}
    edl = {"sources": {"r": "x"}, "ranges": [{"source": "r", "start": 0.0, "end": 2.0}]}
    out = remap(raw=raw, edl=edl)
    assert [w["text"] for w in out] == ["hi", "you"]


def test_word_in_cut_zone_dropped():
    raw = {"words": [
        {"text": "kept", "type": "word", "start": 1.0, "end": 1.5, "speaker_id": "S0"},
        {"text": "cut", "type": "word", "start": 3.0, "end": 3.5, "speaker_id": "S0"},
        {"text": "kept2", "type": "word", "start": 5.0, "end": 5.5, "speaker_id": "S0"},
    ]}
    edl = {"sources": {"r": "x"}, "ranges": [
        {"source": "r", "start": 1.0, "end": 2.0},
        {"source": "r", "start": 5.0, "end": 6.0},
    ]}
    out = remap(raw=raw, edl=edl)
    assert [w["text"] for w in out] == ["kept", "kept2"]


def test_output_only_has_text_start_end():
    raw = {"words": [{"text": "hi", "type": "word", "start": 1.0, "end": 1.2, "speaker_id": "S0"}]}
    edl = {"sources": {"r": "x"}, "ranges": [{"source": "r", "start": 0.0, "end": 2.0}]}
    out = remap(raw=raw, edl=edl)
    assert set(out[0].keys()) == {"text", "start", "end"}
