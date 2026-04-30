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
