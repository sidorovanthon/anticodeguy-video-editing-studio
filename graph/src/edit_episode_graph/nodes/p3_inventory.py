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

from langgraph.types import CachePolicy

from .._caching import make_key

PROJECT_ROOT = Path(__file__).resolve().parents[4]
HELPERS_DIR = Path.home() / ".claude" / "skills" / "video-use" / "helpers"

# Bump on transcribe/pack helper-version / parser / output-shape change. Spec §8.
_CACHE_VERSION = 1


def _cache_key(state, *_args, **_kwargs):
    """Cache key for `p3_inventory` (HOM-132.4).

    Outputs (`takes_packed.md`, per-source transcript JSON files) are
    deterministic in the upstream raw video; replacing the raw input
    invalidates, everything else (ffprobe, transcribe_batch.py,
    pack_transcripts.py) is pure given that input.

    Spec §6 originally listed `[audio.cleaned_path]`. No such field exists
    on `AudioState`; the canonical upstream artifact tracked in state is
    `pickup.raw_path`. HOM-132.4 amends to `pickup.raw_path` (with
    `audio.wav_path` as a secondary signal so a re-isolated WAV under the
    same raw still invalidates).
    """
    if not isinstance(state, dict):
        raise TypeError(
            f"p3_inventory cache key requires dict state, got {type(state).__name__}"
        )
    slug = state.get("slug") or "__unbound__"
    raw_path = (state.get("pickup") or {}).get("raw_path")
    wav_path = (state.get("audio") or {}).get("wav_path")
    return make_key(
        node="p3_inventory",
        version=_CACHE_VERSION,
        slug=slug,
        files=[raw_path, wav_path],
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)
TRANSCRIBE_BATCH = HELPERS_DIR / "transcribe_batch.py"
PACK_TRANSCRIPTS = HELPERS_DIR / "pack_transcripts.py"
TIMELINE_VIEW = HELPERS_DIR / "timeline_view.py"
# Keep aligned with video-use/helpers/transcribe_batch.py. Notably, raw .webm
# is accepted earlier in the pipeline but is not transcribable by that helper.
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".m4v"}
UNSUPPORTED_VIDEO_EXTS = {".webm"}
# Sampling for the canon Step 1 visual first impression. Canon SKILL.md
# §"The process" Step 1 says "Sample one or two `timeline_view`s for a
# visual first impression" without specifying window size — the implied
# intent is "see the whole video", which for a short source means rendering
# the entire timeline. For long sources, a single full-length PNG would be
# unreadably wide and slow, so we sample two representative windows.
SHORT_SOURCE_THRESHOLD_S = 600.0  # ≤10 min: one full-overview window
LONG_SOURCE_WINDOW_S = 120.0       # >10 min: two ±60s windows around quartiles


def _inventory_windows(duration: float) -> list[tuple[float, float, str]]:
    """Return list of (start, end, label) windows for canon Step 1 sampling.

    label is appended to the output filename (`{stem}{label}.png`).
    Empty label → `{stem}.png` (the single-window short-source case).
    """
    if duration <= SHORT_SOURCE_THRESHOLD_S:
        return [(0.0, float(duration), "")]
    half = LONG_SOURCE_WINDOW_S / 2.0
    q1 = duration * 0.25
    q3 = duration * 0.75
    return [
        (max(0.0, q1 - half), min(float(duration), q1 + half), "_q1"),
        (max(0.0, q3 - half), min(float(duration), q3 + half), "_q3"),
    ]


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
        if duration < 0.5:
            warnings.append(
                f"timeline_view skipped for {source.name}: source too short ({duration:.2f}s)"
            )
            continue
        for start, end, label in _inventory_windows(duration):
            if end - start < 0.5:
                continue
            out_png = verify_dir / f"{source.stem}{label}.png"
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
                warnings.append(f"timeline_view failed for {source.name}{label}: {exc}")
                continue
            if result.returncode != 0 or not out_png.exists():
                preview = (_combined_output(result) or "")[:200]
                warnings.append(
                    f"timeline_view failed for {source.name}{label}: "
                    f"rc={result.returncode} {preview}"
                )
                continue
            paths.append(str(out_png))
    return paths, warnings
