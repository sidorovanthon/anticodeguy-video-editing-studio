"""p4_dispatch_beats — deterministic Send fan-out into p4_beat (HOM-133).

Builds one `Send("p4_beat", payload)` per beat in `state.compose.plan.beats`.
LangGraph fans the Sends out in parallel (backend semaphore caps real
concurrency); `p4_assemble_index` waits at the static fan-in.

Skip cases route to `p4_assemble_index` (which itself skips on no fragments)
so the run reaches `halt_llm_boundary` cleanly. Empty `plan.beats` routes
to `END` — there is genuinely nothing to do, and there is no fragment to
assemble either.

Per spec `2026-05-04-hom-122-p4-beats-fan-out-design.md` §"Send payload":
the payload is `{**state, "_beat_dispatch": {...}}`. `_beat_dispatch` is a
transient namespace not declared on `GraphState` — it lives only inside
the Send-spawned state branches and never reaches the parent thread
checkpoint.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langgraph.constants import END
from langgraph.types import Command, Send

from .._scene_id import scene_id_for


_VIEWPORT_RE = re.compile(
    r'<meta\s+name=["\']viewport["\']\s+content=["\']\s*width=(\d+)\s*,\s*height=(\d+)\s*["\']',
    re.IGNORECASE,
)
_DATA_WIDTH_RE = re.compile(r'data-width=["\'](\d+)["\']', re.IGNORECASE)
_DATA_HEIGHT_RE = re.compile(r'data-height=["\'](\d+)["\']', re.IGNORECASE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _notice(reason: str) -> Command:
    return Command(goto="p4_assemble_index", update={"notices": [f"p4_dispatch_beats: {reason}"]})


def _error(message: str) -> Command:
    return Command(
        goto="p4_assemble_index",
        update={"errors": [{"node": "p4_dispatch_beats", "message": message, "timestamp": _now()}]},
    )


def _parse_dimensions(html: str) -> tuple[int, int] | None:
    """Return (width, height) parsed from root index.html, or None if not found.

    Tries the viewport meta first (canonical scaffold output), falls back to
    the root `data-width`/`data-height` attrs. Both are written by
    `scripts/scaffold_hyperframes.py:patch_index_html`, so either succeeding
    is sufficient.
    """
    m = _VIEWPORT_RE.search(html)
    if m:
        return int(m.group(1)), int(m.group(2))
    w = _DATA_WIDTH_RE.search(html)
    h = _DATA_HEIGHT_RE.search(html)
    if w and h:
        return int(w.group(1)), int(h.group(1))
    return None


def p4_dispatch_beats_node(state: dict[str, Any]) -> Command:
    compose = state.get("compose") or {}
    plan = compose.get("plan")
    if not plan:
        return _notice("no compose.plan in state — routing to assemble (will skip)")

    beats = plan.get("beats") or []
    if not beats:
        return Command(goto=END, update={"notices": ["p4_dispatch_beats: plan has 0 beats — END"]})

    if not compose.get("catalog"):
        return _notice("compose.catalog missing (p4_catalog_scan must run first)")

    index_html_path = compose.get("index_html_path")
    if not index_html_path:
        return _notice("compose.index_html_path missing (p4_scaffold must run first)")
    index_path = Path(index_html_path)
    if not index_path.is_file():
        return _notice(f"root index.html not found at {index_path}")

    try:
        root_html = index_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _error(f"failed to read root index.html: {exc!r}")

    dims = _parse_dimensions(root_html)
    if dims is None:
        return _notice(
            "could not parse viewport dimensions from root index.html "
            "(no <meta name=viewport> or data-width/data-height)"
        )
    data_width, data_height = dims

    hf_dir = index_path.parent
    compositions_dir = hf_dir / "compositions"

    # Scene-id derivation + collision detection — surface BOTH labels.
    seen: dict[str, str] = {}
    sends: list[Send] = []
    cumulative_s = 0.0
    n = len(beats)
    for idx, beat in enumerate(beats):
        if not isinstance(beat, dict):
            return _error(f"beat at index {idx} is not a dict: {type(beat).__name__}")
        label = beat.get("beat") or beat.get("name") or ""
        if not label:
            return _error(f"beat at index {idx} has no 'beat' label")
        sid = scene_id_for(label)
        if sid in seen:
            return _error(
                f"scene_id collision: beat labels {seen[sid]!r} and {label!r} "
                f"both sanitise to {sid!r}"
            )
        seen[sid] = label

        duration_s = float(beat.get("duration_s") or 0.0)
        is_final = idx == n - 1
        scene_html_path = str(compositions_dir / f"{sid}.html")

        payload = {
            **state,
            "_beat_dispatch": {
                "scene_id": sid,
                "beat_index": idx,
                "total_beats": n,
                "is_final": is_final,
                "data_start_s": cumulative_s,
                "data_duration_s": duration_s,
                "data_track_index": 1,
                "data_width": data_width,
                "data_height": data_height,
                "plan_beat": beat,
                "scene_html_path": scene_html_path,
            },
        }
        sends.append(Send("p4_beat", payload))
        cumulative_s += duration_s

    return Command(goto=sends)
