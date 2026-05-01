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


import hashlib
import subprocess
import sys


def _edl_hash(edl_dict: dict) -> str:
    """Stable SHA-256 of EDL JSON content (sort_keys for determinism)."""
    blob = json.dumps(edl_dict, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def test_main_writes_envelope_with_edl_hash(tmp_path: Path):
    """final.json on disk is an envelope {edl_hash, words}, not a bare array."""
    edl = {"ranges": [{"start": 0.0, "end": 1.0}], "sources": [{"file": "raw.mp4"}]}
    raw = {"words": [{"type": "word", "text": "hi", "start": 0.1, "end": 0.4}]}

    edl_path = tmp_path / "edl.json"
    raw_path = tmp_path / "raw.json"
    out_path = tmp_path / "final.json"
    edl_path.write_text(json.dumps(edl), encoding="utf-8")
    raw_path.write_text(json.dumps(raw), encoding="utf-8")

    rc = subprocess.run(
        [sys.executable, "-m", "scripts.remap_transcript",
         "--raw", str(raw_path), "--edl", str(edl_path), "--out", str(out_path)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True,
    ).returncode
    assert rc == 0

    on_disk = json.loads(out_path.read_text(encoding="utf-8"))
    assert isinstance(on_disk, dict)
    assert "edl_hash" in on_disk
    assert on_disk["edl_hash"] == _edl_hash(edl)
    assert isinstance(on_disk["words"], list)
    assert len(on_disk["words"]) == 1


def test_main_regens_on_edl_hash_mismatch(tmp_path: Path):
    """Re-running with different EDL produces new hash + new words (not stale cache)."""
    edl_a = {"ranges": [{"start": 0.0, "end": 1.0}], "sources": []}
    edl_b = {"ranges": [{"start": 5.0, "end": 6.0}], "sources": []}
    raw = {"words": [
        {"type": "word", "text": "early", "start": 0.1, "end": 0.4},
        {"type": "word", "text": "late",  "start": 5.1, "end": 5.4},
    ]}

    edl_path = tmp_path / "edl.json"
    raw_path = tmp_path / "raw.json"
    out_path = tmp_path / "final.json"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")

    # First run with edl_a — captures "early"
    edl_path.write_text(json.dumps(edl_a), encoding="utf-8")
    subprocess.run(
        [sys.executable, "-m", "scripts.remap_transcript",
         "--raw", str(raw_path), "--edl", str(edl_path), "--out", str(out_path)],
        cwd=Path(__file__).resolve().parents[1], check=True,
    )
    first = json.loads(out_path.read_text(encoding="utf-8"))
    assert first["edl_hash"] == _edl_hash(edl_a)
    assert first["words"][0]["text"] == "early"

    # Second run with edl_b — must regen (hash differs from on-disk cache)
    edl_path.write_text(json.dumps(edl_b), encoding="utf-8")
    subprocess.run(
        [sys.executable, "-m", "scripts.remap_transcript",
         "--raw", str(raw_path), "--edl", str(edl_path), "--out", str(out_path)],
        cwd=Path(__file__).resolve().parents[1], check=True,
    )
    second = json.loads(out_path.read_text(encoding="utf-8"))
    assert second["edl_hash"] == _edl_hash(edl_b)
    assert second["words"][0]["text"] == "late"
