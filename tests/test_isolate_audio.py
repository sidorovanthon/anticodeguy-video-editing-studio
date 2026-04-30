"""Tests for scripts.isolate_audio."""
from pathlib import Path

import pytest

from scripts.isolate_audio import find_raw_video, IsolationError
from scripts.isolate_audio import audio_stream_has_clean_tag


def test_find_raw_video_picks_unique_match(tmp_path: Path):
    (tmp_path / "raw.mp4").write_bytes(b"")
    assert find_raw_video(tmp_path) == tmp_path / "raw.mp4"


def test_find_raw_video_case_insensitive(tmp_path: Path):
    (tmp_path / "raw.MOV").write_bytes(b"")
    assert find_raw_video(tmp_path) == tmp_path / "raw.MOV"


def test_find_raw_video_errors_on_zero_matches(tmp_path: Path):
    with pytest.raises(IsolationError, match="not found"):
        find_raw_video(tmp_path)


def test_find_raw_video_errors_on_ambiguous(tmp_path: Path):
    (tmp_path / "raw.mp4").write_bytes(b"")
    (tmp_path / "raw.mov").write_bytes(b"")
    with pytest.raises(IsolationError, match="ambiguous"):
        find_raw_video(tmp_path)


def test_tag_detected_when_present_on_audio_stream():
    ffprobe_out = {
        "streams": [
            {"codec_type": "video"},
            {"codec_type": "audio", "tags": {"ANTICODEGUY_AUDIO_CLEANED": "elevenlabs-v1"}},
        ]
    }
    assert audio_stream_has_clean_tag(ffprobe_out) is True


def test_tag_absent_when_no_tags_dict():
    ffprobe_out = {"streams": [{"codec_type": "audio"}]}
    assert audio_stream_has_clean_tag(ffprobe_out) is False


def test_tag_absent_when_wrong_value():
    ffprobe_out = {
        "streams": [{"codec_type": "audio", "tags": {"ANTICODEGUY_AUDIO_CLEANED": "elevenlabs-v0"}}]
    }
    assert audio_stream_has_clean_tag(ffprobe_out) is False


def test_tag_ignored_on_video_stream():
    ffprobe_out = {
        "streams": [{"codec_type": "video", "tags": {"ANTICODEGUY_AUDIO_CLEANED": "elevenlabs-v1"}}]
    }
    assert audio_stream_has_clean_tag(ffprobe_out) is False


def test_tag_absent_when_no_streams_key():
    assert audio_stream_has_clean_tag({}) is False
