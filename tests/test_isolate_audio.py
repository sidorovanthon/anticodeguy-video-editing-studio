"""Tests for scripts.isolate_audio."""
from pathlib import Path

import json
import pytest

from scripts.isolate_audio import find_raw_video, IsolationError
from scripts.isolate_audio import audio_stream_has_clean_tag
from scripts.isolate_audio import load_api_key
from scripts.isolate_audio import extract_audio_cmd, mux_cmd
from scripts.isolate_audio import call_isolation_api, ISOLATION_URL
from scripts.isolate_audio import normalize_to_pcm_wav_cmd
from scripts.isolate_audio import isolate, IsolateResult


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


def test_extract_audio_cmd_shape():
    src = Path("/ep/raw.mp4")
    dst = Path("/tmp/source.wav")
    cmd = extract_audio_cmd(src, dst)
    assert cmd[0] == "ffmpeg"
    assert "-y" in cmd
    assert "-i" in cmd and str(src) in [str(x) for x in cmd]
    assert "-vn" in cmd
    assert "-ac" in cmd and "2" in cmd
    assert "-ar" in cmd and "48000" in cmd
    assert "-c:a" in cmd and "pcm_s16le" in cmd
    assert str(cmd[-1]) == str(dst)


def test_mux_cmd_includes_metadata_tag():
    src_video = Path("/ep/raw.mp4")
    src_wav = Path("/ep/audio/raw.cleaned.wav")
    dst = Path("/ep/raw.muxed.mp4")
    cmd = mux_cmd(src_video, src_wav, dst, tag_value="elevenlabs-v1")
    assert cmd[0] == "ffmpeg"
    cmd_str = [str(x) for x in cmd]
    # both inputs present, in order
    i_indices = [i for i, x in enumerate(cmd_str) if x == "-i"]
    assert len(i_indices) == 2
    assert cmd_str[i_indices[0] + 1] == str(src_video)
    assert cmd_str[i_indices[1] + 1] == str(src_wav)
    # video copy, audio re-encoded
    assert "-c:v" in cmd_str and "copy" in cmd_str
    assert "-c:a" in cmd_str and "aac" in cmd_str
    # mapping: video from input 0, audio from input 1
    assert "0:v" in cmd_str
    assert "1:a" in cmd_str
    # metadata tag
    assert any(
        x == "ANTICODEGUY_AUDIO_CLEANED=elevenlabs-v1" for x in cmd_str
    ), f"tag missing in {cmd_str}"
    # output last
    assert cmd_str[-1] == str(dst)


class _FakeResponse:
    def __init__(self, *, status_code: int, content: bytes = b"", text: str = ""):
        self.status_code = status_code
        self.content = content
        self.text = text or content.decode("latin-1", errors="replace")


def test_call_isolation_api_posts_to_endpoint_with_key_and_audio():
    captured = {}

    def fake_post(url, headers=None, files=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["files"] = files
        captured["timeout"] = timeout
        return _FakeResponse(status_code=200, content=b"OK_BYTES")

    out = call_isolation_api("api-key-xyz", b"WAV_BYTES", post=fake_post)
    assert out == b"OK_BYTES"
    assert captured["url"] == ISOLATION_URL
    assert captured["headers"]["xi-api-key"] == "api-key-xyz"
    assert "audio" in captured["files"]
    # files["audio"] is a tuple of (filename, bytes, content_type) per requests convention
    name, payload, *_ = captured["files"]["audio"]
    assert payload == b"WAV_BYTES"
    assert captured["timeout"] is not None and captured["timeout"] > 0


def test_call_isolation_api_raises_on_non_200():
    def fake_post(*a, **kw):
        return _FakeResponse(status_code=429, text="rate limited")

    with pytest.raises(IsolationError, match="429"):
        call_isolation_api("k", b"x", post=fake_post)


def test_call_isolation_api_raises_on_empty_body():
    def fake_post(*a, **kw):
        return _FakeResponse(status_code=200, content=b"")

    with pytest.raises(IsolationError, match="empty"):
        call_isolation_api("k", b"x", post=fake_post)


def test_normalize_cmd_re_encodes_to_pcm_wav():
    src = Path("/tmp/api.bin")
    dst = Path("/tmp/cleaned.wav")
    cmd = normalize_to_pcm_wav_cmd(src, dst)
    cmd_str = [str(x) for x in cmd]
    assert cmd_str[0] == "ffmpeg"
    assert "-y" in cmd_str
    assert cmd_str[cmd_str.index("-i") + 1] == str(src)
    assert "-c:a" in cmd_str and "pcm_s16le" in cmd_str
    assert "-vn" in cmd_str
    assert cmd_str[-1] == str(dst)


def _make_runner(*, ffprobe_json: dict, fixture_wav: bytes):
    """Build a runner stub that inspects argv and writes outputs as ffmpeg/ffprobe would."""
    calls: list[list[str]] = []

    def runner(cmd: list[str], *, capture_output: bool = False, check: bool = True):
        calls.append(list(cmd))
        if cmd[0] == "ffprobe":
            class R:
                returncode = 0
                stdout = json.dumps(ffprobe_json).encode("utf-8")
                stderr = b""
            return R()
        if cmd[0] == "ffmpeg":
            # write output file (last argv) so downstream existence checks pass
            out = Path(cmd[-1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(fixture_wav if out.suffix == ".wav" else b"\x00")
            class R:
                returncode = 0
                stdout = b""
                stderr = b""
            return R()
        raise AssertionError(f"unexpected cmd: {cmd[0]}")

    runner.calls = calls  # type: ignore[attr-defined]
    return runner


def test_isolate_happy_path_calls_api_and_muxes(tmp_path: Path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "raw.mp4").write_bytes(b"FAKE_VIDEO")

    fixture = (Path(__file__).parent / "fixtures" / "elevenlabs_response_tiny.wav").read_bytes()
    runner = _make_runner(
        ffprobe_json={"streams": [{"codec_type": "audio"}]},  # no tag → must call API
        fixture_wav=fixture,
    )

    posts: list[tuple] = []

    def post(url, headers=None, files=None, timeout=None):
        posts.append((url, headers, files, timeout))
        class R:
            status_code = 200
            content = fixture  # API returns valid WAV bytes
            text = ""
        return R()

    result = isolate(
        episode_dir=ep,
        runner=runner,
        post=post,
        key_loader=lambda: "test-key",
    )

    assert result.cached is False
    assert result.api_called is True
    assert result.wav_path == ep / "audio" / "raw.cleaned.wav"
    assert result.wav_path.exists()
    assert result.raw_path == ep / "raw.mp4"

    # API was called once
    assert len(posts) == 1
    # Exactly three ffmpeg invocations: extract, normalize, mux (unconditionally).
    ffmpegs = [c for c in runner.calls if c[0] == "ffmpeg"]
    assert len(ffmpegs) == 3
    # extract: reads raw.mp4, output ends with .wav, no metadata tag
    extract = ffmpegs[0]
    assert "raw.mp4" in extract[extract.index("-i") + 1]
    assert extract[-1].endswith(".wav")
    assert not any("ANTICODEGUY_AUDIO_CLEANED=" in str(x) for x in extract)
    # normalize: output ends with .wav, input does not end with .wav
    normalize = ffmpegs[1]
    assert normalize[-1].endswith(".wav")
    assert not normalize[normalize.index("-i") + 1].endswith(".wav")
    # mux: last call, includes the metadata tag
    mux = ffmpegs[2]
    assert any("ANTICODEGUY_AUDIO_CLEANED=" in str(x) for x in mux)


def test_isolate_short_circuits_when_tag_present(tmp_path: Path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "raw.mp4").write_bytes(b"x")

    runner = _make_runner(
        ffprobe_json={
            "streams": [
                {"codec_type": "audio", "tags": {"ANTICODEGUY_AUDIO_CLEANED": "elevenlabs-v1"}}
            ]
        },
        fixture_wav=b"",
    )

    posts: list = []

    def post(*a, **kw):
        posts.append(1)
        raise AssertionError("must not call API when tag present")

    result = isolate(
        episode_dir=ep, runner=runner, post=post, key_loader=lambda: "k",
    )
    assert result.cached is True
    assert result.api_called is False
    assert result.reason == "tag-present"
    # Only ffprobe ran; no ffmpeg
    assert all(c[0] == "ffprobe" for c in runner.calls)
    # audio/ dir not created
    assert not (ep / "audio").exists()
    assert posts == []


def test_isolate_skips_api_when_wav_cached(tmp_path: Path):
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "raw.mp4").write_bytes(b"x")
    audio_dir = ep / "audio"
    audio_dir.mkdir()
    fixture = (Path(__file__).parent / "fixtures" / "elevenlabs_response_tiny.wav").read_bytes()
    (audio_dir / "raw.cleaned.wav").write_bytes(fixture)

    runner = _make_runner(
        ffprobe_json={"streams": [{"codec_type": "audio"}]},  # tag absent → mux still runs
        fixture_wav=fixture,
    )

    def post(*a, **kw):
        raise AssertionError("must not call API when WAV cached")

    result = isolate(
        episode_dir=ep, runner=runner, post=post, key_loader=lambda: "k",
    )
    assert result.cached is False
    assert result.api_called is False
    assert result.reason == "api-cache-hit"
    # Mux ran (one ffmpeg call), no extract, no normalize
    ffmpegs = [c for c in runner.calls if c[0] == "ffmpeg"]
    assert len(ffmpegs) == 1
    assert any("ANTICODEGUY_AUDIO_CLEANED=elevenlabs-v1" in str(x) for x in ffmpegs[0])
