"""Tests for scripts.isolate_audio."""
from pathlib import Path

import pytest

from scripts.isolate_audio import find_raw_video, IsolationError
from scripts.isolate_audio import audio_stream_has_clean_tag
from scripts.isolate_audio import load_api_key


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


def test_load_api_key_from_environ_when_no_files(tmp_path: Path):
    project_env = tmp_path / "p.env"
    video_use_env = tmp_path / "v.env"
    key = load_api_key(
        project_env=project_env,
        video_use_env=video_use_env,
        environ={"ELEVENLABS_API_KEY": "k-from-env"},
    )
    assert key == "k-from-env"


def test_load_api_key_project_env_takes_precedence(tmp_path: Path):
    project_env = tmp_path / "p.env"
    project_env.write_text('ELEVENLABS_API_KEY="k-project"\n', encoding="utf-8")
    video_use_env = tmp_path / "v.env"
    video_use_env.write_text("ELEVENLABS_API_KEY=k-video-use\n", encoding="utf-8")
    key = load_api_key(
        project_env=project_env,
        video_use_env=video_use_env,
        environ={"ELEVENLABS_API_KEY": "k-environ"},
    )
    assert key == "k-project"


def test_load_api_key_falls_back_to_video_use_env(tmp_path: Path):
    project_env = tmp_path / "p.env"  # absent
    video_use_env = tmp_path / "v.env"
    video_use_env.write_text("ELEVENLABS_API_KEY=k-video-use\n", encoding="utf-8")
    key = load_api_key(project_env=project_env, video_use_env=video_use_env, environ={})
    assert key == "k-video-use"


def test_load_api_key_strips_quotes_and_whitespace(tmp_path: Path):
    project_env = tmp_path / "p.env"
    project_env.write_text("  ELEVENLABS_API_KEY = '  k-quoted  '  \n", encoding="utf-8")
    key = load_api_key(project_env=project_env, video_use_env=tmp_path / "absent", environ={})
    assert key == "k-quoted"


def test_load_api_key_raises_when_nowhere(tmp_path: Path):
    with pytest.raises(IsolationError, match="ELEVENLABS_API_KEY not found"):
        load_api_key(
            project_env=tmp_path / "absent1",
            video_use_env=tmp_path / "absent2",
            environ={},
        )


def test_load_api_key_ignores_comments_and_blank_lines(tmp_path: Path):
    project_env = tmp_path / "p.env"
    project_env.write_text(
        "# comment\n\nOTHER=1\nELEVENLABS_API_KEY=k-real\n", encoding="utf-8"
    )
    key = load_api_key(project_env=project_env, video_use_env=tmp_path / "absent", environ={})
    assert key == "k-real"
