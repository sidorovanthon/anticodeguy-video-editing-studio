"""Phase 2: Audio Isolation via ElevenLabs.

Per docs/superpowers/specs/2026-04-30-audio-isolation-design.md.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_EXTS = (".mp4", ".mov", ".mkv", ".webm")
TAG_KEY = "ANTICODEGUY_AUDIO_CLEANED"
TAG_VALUE = "elevenlabs-v1"


class IsolationError(Exception):
    """Raised when isolation cannot proceed; surfaced verbatim to the user."""


def find_raw_video(episode_dir: Path) -> Path:
    """Locate the single raw.<ext> in episode_dir. Raises on 0 or >1 matches."""
    matches = [
        p for p in episode_dir.iterdir()
        if p.is_file() and p.stem == "raw" and p.suffix.lower() in SUPPORTED_EXTS
    ]
    if not matches:
        raise IsolationError(f"raw.<ext> not found in {episode_dir}")
    if len(matches) > 1:
        raise IsolationError(
            f"raw.<ext> ambiguous in {episode_dir}: matched {sorted(p.name for p in matches)}"
        )
    return matches[0]


def audio_stream_has_clean_tag(ffprobe_json: dict) -> bool:
    """Return True iff any audio stream carries ANTICODEGUY_AUDIO_CLEANED=elevenlabs-v1."""
    for stream in ffprobe_json.get("streams", []):
        if stream.get("codec_type") != "audio":
            continue
        tags = stream.get("tags") or {}
        if tags.get(TAG_KEY) == TAG_VALUE:
            return True
    return False


def _read_env_file(path: Path) -> dict[str, str]:
    """Parse a minimal .env file. Mirrors video-use/helpers/transcribe.py:load_api_key."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'").strip()
    return out


def load_api_key(
    *,
    project_env: Path,
    video_use_env: Path,
    environ: dict[str, str],
) -> str:
    """Resolve ELEVENLABS_API_KEY using the same ladder as video-use's transcribe.py."""
    for source in (project_env, video_use_env):
        parsed = _read_env_file(source)
        if "ELEVENLABS_API_KEY" in parsed and parsed["ELEVENLABS_API_KEY"]:
            return parsed["ELEVENLABS_API_KEY"]
    if environ.get("ELEVENLABS_API_KEY"):
        return environ["ELEVENLABS_API_KEY"]
    raise IsolationError("ELEVENLABS_API_KEY not found in .env or environment")


def extract_audio_cmd(src: Path, dst: Path) -> list[str]:
    """ffmpeg argv to extract stereo 48kHz PCM WAV from src into dst."""
    return [
        "ffmpeg", "-y",
        "-i", str(src),
        "-vn",
        "-ac", "2",
        "-ar", "48000",
        "-c:a", "pcm_s16le",
        str(dst),
    ]


def mux_cmd(src_video: Path, src_wav: Path, dst: Path, *, tag_value: str) -> list[str]:
    """ffmpeg argv to mux src_video's video stream with src_wav's audio, stamping the tag."""
    return [
        "ffmpeg", "-y",
        "-i", str(src_video),
        "-i", str(src_wav),
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-metadata:s:a:0", f"{TAG_KEY}={tag_value}",
        str(dst),
    ]


ISOLATION_URL = "https://api.elevenlabs.io/v1/audio-isolation"


def call_isolation_api(api_key: str, wav_bytes: bytes, *, post) -> bytes:
    """POST wav_bytes to ElevenLabs Audio Isolation; return cleaned audio bytes."""
    headers = {"xi-api-key": api_key}
    files = {"audio": ("source.wav", wav_bytes, "audio/wav")}
    try:
        resp = post(ISOLATION_URL, headers=headers, files=files, timeout=300)
    except Exception as e:
        raise IsolationError(f"Network error: {e}") from e
    if resp.status_code != 200:
        snippet = (resp.text or "")[:200]
        raise IsolationError(f"Audio Isolation API returned {resp.status_code}: {snippet}")
    if not resp.content:
        raise IsolationError("Audio Isolation API returned empty body")
    return resp.content


def normalize_to_pcm_wav_cmd(src: Path, dst: Path) -> list[str]:
    """ffmpeg argv to re-encode whatever container/codec the API returned into PCM WAV."""
    return [
        "ffmpeg", "-y",
        "-i", str(src),
        "-vn",
        "-c:a", "pcm_s16le",
        str(dst),
    ]


@dataclass
class IsolateResult:
    cached: bool
    api_called: bool
    raw_path: Path
    wav_path: Path
    reason: str | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "cached": self.cached,
                "api_called": self.api_called,
                "raw_path": str(self.raw_path),
                "wav_path": str(self.wav_path),
                "reason": self.reason,
            },
            ensure_ascii=False,
        )


def _run(runner, cmd: list[str]) -> None:
    """Run a subprocess; raise IsolationError on failure with a useful tail."""
    try:
        result = runner(cmd, capture_output=True, check=False)
    except FileNotFoundError as e:
        raise IsolationError(f"executable not found: {cmd[0]}") from e
    if getattr(result, "returncode", 0) != 0:
        tail = (getattr(result, "stderr", b"") or b"").decode("utf-8", errors="replace")[-400:]
        raise IsolationError(f"{cmd[0]} failed: {tail}")


def _ffprobe_json(runner, video: Path) -> dict:
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(video)]
    try:
        result = runner(cmd, capture_output=True, check=False)
    except FileNotFoundError as e:
        raise IsolationError("ffprobe not found on PATH") from e
    if getattr(result, "returncode", 0) != 0:
        raise IsolationError(f"ffprobe failed on {video}")
    raw = getattr(result, "stdout", b"") or b""
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as e:
        raise IsolationError(f"ffprobe returned non-JSON: {e}") from e


def isolate(
    *,
    episode_dir: Path,
    runner,
    post,
    key_loader,
) -> IsolateResult:
    """Phase 2 orchestration. Pure I/O; all side-effecting deps injected."""
    raw = find_raw_video(episode_dir)
    audio_dir = episode_dir / "audio"
    wav_path = audio_dir / "raw.cleaned.wav"

    # Layer 1: tag check (full no-op).
    probe = _ffprobe_json(runner, raw)
    if audio_stream_has_clean_tag(probe):
        return IsolateResult(
            cached=True, api_called=False, raw_path=raw, wav_path=wav_path,
            reason="tag-present",
        )

    audio_dir.mkdir(parents=True, exist_ok=True)

    # Layer 2: WAV cache check.
    api_called = False
    if not wav_path.exists():
        api_key = key_loader()
        with tempfile.TemporaryDirectory(dir=episode_dir) as td:
            tmp = Path(td)
            extracted = tmp / "source.wav"
            _run(runner, extract_audio_cmd(raw, extracted))
            wav_bytes = extracted.read_bytes()
            cleaned_bytes = call_isolation_api(api_key, wav_bytes, post=post)
            api_called = True
            # Normalize whatever came back into PCM WAV in the cache slot, atomically.
            api_blob = tmp / "api.bin"
            api_blob.write_bytes(cleaned_bytes)
            tmp_wav = tmp / "cleaned.wav"
            _run(runner, normalize_to_pcm_wav_cmd(api_blob, tmp_wav))
            os.replace(tmp_wav, wav_path)

    # Mux (always runs when tag absent — cheap and stamps the tag).
    with tempfile.TemporaryDirectory(dir=episode_dir) as td:
        tmp = Path(td)
        muxed = tmp / f"raw.muxed{raw.suffix}"
        _run(runner, mux_cmd(raw, wav_path, muxed, tag_value=TAG_VALUE))
        os.replace(muxed, raw)

    return IsolateResult(
        cached=False, api_called=api_called, raw_path=raw, wav_path=wav_path,
        reason="api-cache-hit" if not api_called else "isolated",
    )


import argparse
import subprocess
import sys

import requests


def _default_runner(cmd, *, capture_output=False, check=False):
    return subprocess.run(cmd, capture_output=capture_output, check=check)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 2: ElevenLabs Audio Isolation.")
    parser.add_argument("--episode-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    project_env = Path(".env").resolve()
    video_use_env = (Path.home() / ".claude" / "skills" / "video-use" / ".env").resolve()

    try:
        result = isolate(
            episode_dir=args.episode_dir,
            runner=_default_runner,
            post=requests.post,
            key_loader=lambda: load_api_key(
                project_env=project_env,
                video_use_env=video_use_env,
                environ=dict(os.environ),
            ),
        )
    except IsolationError as e:
        print(f"isolation error: {e}", file=sys.stderr)
        return 2

    print(result.to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
