"""p3_inventory node - ffprobe + canon transcript helpers + sample timeline_view.

This is the deterministic half of video-use canon Step 1 (Inventory). It
collects source media metadata, invokes the canonical Scribe batch helper, then
packs cached/raw transcripts into `<edit>/takes_packed.md` for downstream LLM
nodes. The helper owns transcript caching (HR 9), so re-runs do not re-upload
sources whose `<edit>/transcripts/<stem>.json` already exists.

Per canon §"The process" Step 1 — "Sample one or two `timeline_view`s for a
visual first impression" — we also produce a single mid-source filmstrip+waveform
PNG per source under `<edit>/verify/inventory/`. This is best-effort: if the
helper fails (missing deps, etc.) the node logs a warning notice but does not
fail the inventory step. Strategy/EDL nodes can read these PNGs via Read for
visual context; self-eval (Step 7) produces the rigorous per-cut sampling.
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
TIMELINE_VIEW = HELPERS_DIR / "timeline_view.py"
# Keep aligned with video-use/helpers/transcribe_batch.py. Notably, raw .webm
# is accepted earlier in the pipeline but is not transcribable by that helper.
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".m4v"}
UNSUPPORTED_VIDEO_EXTS = {".webm"}
# Sampling window for the canon Step 1 visual first impression: 5s slice
# centered on source midpoint. Wide enough to show waveform shape and a few
# frames; narrow enough to render fast.
SAMPLE_WINDOW_S = 5.0


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


def _unsupported_source_files(source_dir: Path) -> list[Path]:
    return sorted(
        p for p in source_dir.iterdir()
        if p.is_file() and p.suffix.lower() in UNSUPPORTED_VIDEO_EXTS
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

    unsupported = _unsupported_source_files(source_dir)
    if unsupported:
        return _error(
            "unsupported source extension(s) for canonical transcribe_batch.py: "
            + ", ".join(str(p) for p in unsupported)
        )

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

    sample_paths, sample_warnings = _sample_timeline_views(
        sources=sources,
        inventory_sources=inventory_sources,
        edit_dir=edit_dir,
        transcripts_dir=transcripts_dir,
        runner=runner,
    )

    update: dict = {
        "edit": {
            "inventory": {
                "source_dir": str(source_dir),
                "sources": inventory_sources,
                "transcript_json_paths": transcript_paths,
                "takes_packed_path": str(takes_packed),
                "timeline_view_samples": sample_paths,
            },
        },
        "transcripts": {
            "raw_json_paths": transcript_paths,
            "takes_packed_path": str(takes_packed),
        },
    }
    if sample_warnings:
        update["notices"] = sample_warnings
    return update


def _sample_timeline_views(
    *,
    sources: list[Path],
    inventory_sources: list[dict],
    edit_dir: Path,
    transcripts_dir: Path,
    runner,
) -> tuple[list[str], list[str]]:
    """Generate one timeline_view PNG per source. Best-effort, never fatal.

    Returns (paths, warnings). Paths are absolute strings of generated PNGs;
    warnings are human-readable notices when sampling failed for any source.
    """
    if not TIMELINE_VIEW.exists():
        return [], [f"timeline_view sampling skipped: helper missing at {TIMELINE_VIEW}"]

    verify_dir = edit_dir / "verify" / "inventory"
    verify_dir.mkdir(parents=True, exist_ok=True)

    duration_by_stem = {
        s["stem"]: s.get("duration_s") for s in inventory_sources
    }
    paths: list[str] = []
    warnings: list[str] = []
    for source in sources:
        duration = duration_by_stem.get(source.stem)
        if not isinstance(duration, (int, float)) or duration <= 0:
            warnings.append(
                f"timeline_view skipped for {source.name}: unknown or zero duration"
            )
            continue
        # Center a SAMPLE_WINDOW_S window on the midpoint, clamped to source.
        half = SAMPLE_WINDOW_S / 2.0
        mid = duration / 2.0
        start = max(0.0, mid - half)
        end = min(float(duration), start + SAMPLE_WINDOW_S)
        if end - start < 0.5:
            warnings.append(
                f"timeline_view skipped for {source.name}: source too short ({duration:.2f}s)"
            )
            continue
        out_png = verify_dir / f"{source.stem}_mid.png"
        cmd = [
            sys.executable,
            str(TIMELINE_VIEW),
            str(source),
            f"{start:.3f}",
            f"{end:.3f}",
            "-o",
            str(out_png),
        ]
        transcript = transcripts_dir / f"{source.stem}.json"
        if transcript.is_file():
            cmd += ["--transcript", str(transcript)]
        try:
            result = runner(cmd, cwd=HELPERS_DIR)
        except OSError as exc:
            warnings.append(f"timeline_view failed for {source.name}: {exc}")
            continue
        if result.returncode != 0 or not out_png.exists():
            preview = (_combined_output(result) or "")[:200]
            warnings.append(
                f"timeline_view failed for {source.name}: rc={result.returncode} {preview}"
            )
            continue
        paths.append(str(out_png))
    return paths, warnings
