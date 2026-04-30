"""Phase 2: Audio Isolation via ElevenLabs.

Per docs/superpowers/specs/2026-04-30-audio-isolation-design.md.
"""
from __future__ import annotations

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
