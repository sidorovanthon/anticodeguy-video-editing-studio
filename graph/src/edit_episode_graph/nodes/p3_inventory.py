"""p3_inventory node - ffprobe + canon transcript helpers.

This is the deterministic half of video-use canon Step 1 (Inventory). It
collects source media metadata, invokes the canonical Scribe batch helper, then
packs cached/raw transcripts into `<edit>/takes_packed.md` for downstream LLM
nodes. The helper owns transcript caching (HR 9), so re-runs do not re-upload
sources whose `<edit>/transcripts/<stem>.json` already exists.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[4]
HELPERS_DIR = Path.home() / ".claude" / "skills" / "video-use" / "helpers"
TRANSCRIBE_BATCH = HELPERS_DIR / "transcribe_batch.py"
PACK_TRANSCRIPTS = HELPERS_DIR / "pack_transcripts.py"
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(message: str) -> dict:
    return {"errors": [{"node": "p3_inventory", "message": message, "timestamp": _now()}]}


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env, encoding="utf-8")


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(s for s in (result.stderr, result.stdout) if s).strip()


def _source_dir(episode_dir: Path) -> Path:
    edit_sources = episode_dir / "edit" / "sources"
    if edit_sources.is_dir():
        return edit_sources
    return episode_dir


def _source_files(source_dir: Path) -> list[Path]:
    return sorted(
        p for p in source_dir.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS
    )


def _ratio_to_float(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    try:
        ratio = Fraction(value)
    except (ValueError, ZeroDivisionError):
        return None
    return float(ratio)


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _probe_source(path: Path, *, runner=_run) -> dict:
    result = runner(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {_combined_output(result)}")
    try:
        probe = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ffprobe returned non-JSON for {path}: {exc}") from exc

    streams = probe.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
    duration_s = _float_or_none(video.get("duration")) or _float_or_none((probe.get("format") or {}).get("duration"))

    return {
        "path": str(path),
        "name": path.name,
        "stem": path.stem,
        "duration_s": duration_s,
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
        "fps": _ratio_to_float(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        "width": video.get("width"),
        "height": video.get("height"),
    }


def _ensure_tools() -> str | None:
    if shutil.which("ffprobe") is None:
        return "ffprobe not found on PATH"
    missing = [p for p in (TRANSCRIBE_BATCH, PACK_TRANSCRIPTS) if not p.exists()]
    if missing:
        return "missing video-use helper(s): " + ", ".join(str(p) for p in missing)
    return None


def p3_inventory_node(state, *, runner=_run):
    episode_dir_raw = state.get("episode_dir")
    if not episode_dir_raw:
        return _error("episode_dir missing from state (pickup must run first)")

    tool_error = _ensure_tools()
    if tool_error:
        return _error(tool_error)

    episode_dir = Path(episode_dir_raw)
    edit_dir = episode_dir / "edit"
    transcripts_dir = edit_dir / "transcripts"
    source_dir = _source_dir(episode_dir)
    if not source_dir.is_dir():
        return _error(f"source directory not found: {source_dir}")

    sources = _source_files(source_dir)
    if not sources:
        return _error(f"no source videos found in {source_dir}")

    try:
        inventory_sources = [_probe_source(source, runner=runner) for source in sources]
    except RuntimeError as exc:
        return _error(str(exc))

    transcribe = runner(
        [
            sys.executable,
            str(TRANSCRIBE_BATCH),
            str(source_dir),
            "--edit-dir",
            str(edit_dir),
            "--workers",
            "4",
        ],
        cwd=HELPERS_DIR,
    )
    if transcribe.returncode != 0:
        return _error(_combined_output(transcribe) or "transcribe_batch.py failed with no output")

    pack = runner(
        [sys.executable, str(PACK_TRANSCRIPTS), "--edit-dir", str(edit_dir)],
        cwd=HELPERS_DIR,
    )
    if pack.returncode != 0:
        return _error(_combined_output(pack) or "pack_transcripts.py failed with no output")

    transcript_paths = sorted(str(p) for p in transcripts_dir.glob("*.json"))
    missing_transcripts = [
        str(transcripts_dir / f"{source.stem}.json")
        for source in sources
        if not (transcripts_dir / f"{source.stem}.json").exists()
    ]
    if missing_transcripts:
        return _error("missing transcript(s) after transcribe_batch.py: " + ", ".join(missing_transcripts))

    takes_packed = edit_dir / "takes_packed.md"
    if not takes_packed.exists():
        return _error(f"takes_packed.md missing after pack_transcripts.py: {takes_packed}")

    return {
        "edit": {
            "inventory": {
                "source_dir": str(source_dir),
                "sources": inventory_sources,
                "transcript_json_paths": transcript_paths,
                "takes_packed_path": str(takes_packed),
            },
        },
        "transcripts": {
            "raw_json_paths": transcript_paths,
            "takes_packed_path": str(takes_packed),
        },
    }
