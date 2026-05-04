"""Conditional-edge routing helpers — pure-function decisions on graph state.

LangGraph conditional edges return the name of the next node (or `END`).
These functions are imported by `graph.py` and exercised directly by unit
tests. They MUST NOT mutate state — state deltas are emitted by nodes.

`skip_phase2?` reads the container tag deterministically (per spec §4.1),
not the script's own tag layer. The script *also* checks the tag when it
runs, but the conditional-edge form makes the decision visible in Studio
(idempotency observable, ElevenLabs not invoked) — that's the v1 DoD.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from langgraph.graph import END

# Mirrors scripts/isolate_audio.py — kept in sync by convention; the graph is
# allowed to know the tag it's gating on.
SUPPORTED_EXTS = (".mp4", ".mov", ".mkv", ".webm")
TAG_KEY = "ANTICODEGUY_AUDIO_CLEANED"
TAG_VALUE = "elevenlabs-v1"


def _find_raw_video(episode_dir: Path) -> Path | None:
    if not episode_dir.exists():
        return None
    matches = [
        p for p in episode_dir.iterdir()
        if p.is_file() and p.stem == "raw" and p.suffix.lower() in SUPPORTED_EXTS
    ]
    return matches[0] if len(matches) == 1 else None


def _container_has_clean_tag(video: Path) -> bool:
    """Return True iff ffprobe reports the clean-audio tag at the container level.

    Conservative: any failure (missing ffprobe, malformed JSON, missing file)
    returns False, which routes through `isolate_audio`. The script will then
    raise its own clear error — better than masking a bad raw with a skip.
    """
    if shutil.which("ffprobe") is None:
        return False
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(video)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    if result.returncode != 0:
        return False
    try:
        probe = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return False
    tags = (probe.get("format") or {}).get("tags") or {}
    return any(k.lower() == TAG_KEY.lower() and v == TAG_VALUE for k, v in tags.items())


def route_after_pickup(state) -> str:
    """pickup → END | isolate_audio | preflight_canon (skip_phase2 baked in)."""
    if state.get("errors"):
        return END
    if state.get("pickup", {}).get("idle"):
        return END
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return END
    raw = _find_raw_video(Path(episode_dir))
    if raw is not None and _container_has_clean_tag(raw):
        return "preflight_canon"
    return "isolate_audio"


def route_after_preflight(state) -> str:
    """preflight_canon -> glue_remap_transcript | p3_pre_scan | p3_inventory."""
    if state.get("errors"):
        return END
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return END
    edit_dir = Path(episode_dir) / "edit"
    if (edit_dir / "final.mp4").exists():
        return "glue_remap_transcript"
    if (edit_dir / "takes_packed.md").exists():
        return "p3_pre_scan"
    return "p3_inventory"


def route_after_inventory(state) -> str:
    """p3_inventory -> END on error | p3_pre_scan on success."""
    if state.get("errors"):
        return END
    return "p3_pre_scan"


def route_after_pre_scan(state) -> str:
    """p3_pre_scan -> END on error | p3_strategy on success."""
    if state.get("errors"):
        return END
    return "p3_strategy"


def route_after_strategy(state) -> str:
    """p3_strategy -> END on error | p3_edl_select on success."""
    if state.get("errors"):
        return END
    return "p3_edl_select"


def route_after_edl_select(state) -> str:
    """p3_edl_select -> END on error/skip | gate:edl_ok on success."""
    if state.get("errors"):
        return END
    edl = (state.get("edit") or {}).get("edl") or {}
    if edl.get("skipped"):
        return END
    return "gate_edl_ok"


def route_after_edl_ok(state) -> str:
    """gate:edl_ok -> p3_render_segments on pass | edl_failure_interrupt on fail.

    The interrupt node suspends the graph (HITL) so an operator can inspect
    `state["gate_results"]`, fix the EDL, and resume. Per spec §6.2 the gate
    itself stays pure (state-update only); routing decides what to do with
    the recorded outcome. The retry-loop variant (re-call p3_edl_select with
    violations fed back into the brief) is tracked separately under HOM-75.
    """
    from ..gates._base import latest_gate_result
    result = latest_gate_result(state, "gate:edl_ok")
    if result and result.get("passed"):
        return "p3_render_segments"
    return "edl_failure_interrupt"


def route_after_render_segments(state) -> str:
    """p3_render_segments -> END on error | halt_llm_boundary on success.

    Downstream of render the spec calls for `p3_self_eval` → `p3_persist_session`
    → `glue_remap_transcript`; those are future tickets (HOM-104..107). Until
    they land we route to the existing `halt_llm_boundary` so Studio surfaces
    a clean stop with a notice rather than an unexplained terminal.
    """
    if state.get("errors"):
        return END
    return "halt_llm_boundary"


def route_after_remap(state) -> str:
    """glue_remap_transcript → END | p4_scaffold (skip_phase4 = idempotent)."""
    if state.get("errors"):
        return END
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return END
    if (Path(episode_dir) / "hyperframes" / "index.html").exists():
        return END
    return "p4_scaffold"
