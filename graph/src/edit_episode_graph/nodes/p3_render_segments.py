"""p3_render_segments — deterministic ffmpeg cuts + grade + concat.

Wraps canon `~/.claude/skills/video-use/helpers/render.py` via subprocess.
Per CLAUDE.md "External skill canon" — call canon's helper, do not reimplement.

Phase 3 orchestrator policy: animations and subtitles live in Phase 4. The
EDL emerging from `gate:edl_ok` carries `overlays: []` and no `subtitles`
field, so canon's compositor degenerates to "copy base → loudnorm" — Hard
Rules 1 (subtitles last) and 4 (overlay PTS-shift) are trivially satisfied.

Hard Rules satisfied by canon `render.py` itself: HR 2 (per-segment extract
→ `-c copy` concat) and HR 3 (30ms audio fades at every boundary).

Idempotency: re-runs find `<edit>/final.mp4` and short-circuit with `cached=True`
plus an ffprobe duration check. The upstream `route_after_preflight` skip-edge
also short-circuits Phase 3 entirely when `final.mp4` exists, so this branch
is mainly for graph replay / resumed-after-failure.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .._render_constants import duration_tolerance_ms

HELPERS_DIR = Path.home() / ".claude" / "skills" / "video-use" / "helpers"
RENDER_PY = HELPERS_DIR / "render.py"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(message: str) -> dict:
    return {"errors": [{"node": "p3_render_segments", "message": message, "timestamp": _now()}]}


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env, encoding="utf-8")


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(s for s in (result.stderr, result.stdout) if s).strip()


def _ensure_tools() -> str | None:
    if shutil.which("ffmpeg") is None:
        return "ffmpeg not found on PATH"
    if shutil.which("ffprobe") is None:
        return "ffprobe not found on PATH"
    if not RENDER_PY.exists():
        return f"canon render.py not found at {RENDER_PY}"
    return None


def _probe_duration_s(path: Path, *, runner) -> float | None:
    result = runner(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            str(path),
        ],
        cwd=path.parent,
    )
    if result.returncode != 0:
        return None
    try:
        probe = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
    raw = (probe.get("format") or {}).get("duration")
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def p3_render_segments_node(state, *, runner=_run):
    episode_dir_raw = state.get("episode_dir")
    if not episode_dir_raw:
        return _error("episode_dir missing from state (pickup must run first)")

    edl_state = (state.get("edit") or {}).get("edl") or {}
    if edl_state.get("skipped"):
        return {
            "edit": {
                "render": {
                    "skipped": True,
                    "skip_reason": f"upstream EDL skipped: {edl_state.get('skip_reason') or 'unknown'}",
                },
            },
        }
    if not edl_state.get("ranges"):
        return _error("EDL missing or has no ranges in state['edit']['edl']")

    tool_error = _ensure_tools()
    if tool_error:
        return _error(tool_error)

    episode_dir = Path(episode_dir_raw)
    edit_dir = episode_dir / "edit"
    edl_path = edit_dir / "edl.json"
    final_path = edit_dir / "final.mp4"
    clips_dir = edit_dir / "clips_graded"

    if not edl_path.exists():
        return _error(f"edl.json not found at {edl_path}")

    expected = edl_state.get("total_duration_s")
    try:
        expected_f = float(expected) if expected is not None else None
    except (TypeError, ValueError):
        expected_f = None
    n_segments = len(edl_state.get("ranges") or [])

    cached = final_path.exists()
    if not cached:
        result = runner(
            [sys.executable, str(RENDER_PY), str(edl_path), "-o", str(final_path)],
            cwd=HELPERS_DIR,
        )
        if result.returncode != 0:
            return _error(_combined_output(result) or f"render.py exited {result.returncode}")
        if not final_path.exists():
            return _error(f"render.py succeeded but final.mp4 missing at {final_path}")

    duration = _probe_duration_s(final_path, runner=runner)
    if duration is None:
        return _error(f"ffprobe failed on rendered output {final_path}")

    delta_ms: int | None = None
    if expected_f is not None:
        delta_ms = int(round(abs(duration - expected_f) * 1000))
        tolerance_ms = duration_tolerance_ms(n_segments)
        if delta_ms > tolerance_ms:
            return _error(
                f"final.mp4 duration {duration:.3f}s deviates from EDL "
                f"total_duration_s {expected_f:.3f}s by {delta_ms}ms "
                f"(tolerance {tolerance_ms}ms for {n_segments} segments)"
            )

    return {
        "edit": {
            "render": {
                "final_mp4": str(final_path),
                "clips_dir": str(clips_dir),
                "duration_s": duration,
                "expected_duration_s": expected_f,
                "delta_ms": delta_ms,
                "n_segments": n_segments,
                "cached": cached,
            },
        },
    }
