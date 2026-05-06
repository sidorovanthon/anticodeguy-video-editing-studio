"""p4_persist_session — cheap LLM node that runs canon §"Memory" persistence
for the Phase 4 (HF composition) leg of the pipeline.

Mirrors `p3_persist_session` (HOM-105) shape: dispatched sub-agent reads
the video-use §"Memory — `project.md`" canon, scans existing Session
headings, and appends a new `## Session N — <date>` block dated today.
Numbering is monotonic across the whole file — Phase 3 + Phase 4 share
the same N space.

Idempotency is monotonic-by-N (re-runs add a new block, not overwrite),
matching p3. The compose.session_persisted flag is set on success so
downstream callers can observe completion without reading the file.

Skip cleanly when upstream artifacts are missing:
  - no episode_dir,
  - no assembled index (compose.assemble.skipped or missing assembled_at).
The graph wires this node downstream of `p4_assemble_index` on the
success leg, so in normal flow these inputs are always present.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from langgraph.types import CachePolicy

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from .._caching import make_llm_key
from ..schemas.p4_persist_session import PersistSessionResult
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. See HOM-132 spec §8.
_CACHE_VERSION = 1


def _cache_key(state, *_args, **_kwargs):
    if not isinstance(state, dict):
        raise TypeError(
            f"p4_persist_session cache key requires dict state, got {type(state).__name__}"
        )
    # See p4_design_system._cache_key for the empty-slug rationale.
    slug = state.get("slug") or "__unbound__"
    compose = state.get("compose") or {}
    assemble = compose.get("assemble") or {}
    # Spec §6 specifies `compose.index_html_path`; the assembled artifact is
    # actually carried as `compose.assemble.index_html_path` (with
    # `assembled_at` as a legacy fallback). A re-run with identical
    # `index.html` content cache-hits and skips appending a duplicate
    # Session block — desirable: nothing changed, no new session.
    index_html_path = (
        assemble.get("index_html_path")
        or assemble.get("assembled_at")
    )
    # `today` (UTC YYYY-MM-DD) is rendered into the brief (line 33 of
    # briefs/p4_persist_session.j2) and dictates the date stamped on the
    # appended Session block. Including it in `extras` means a same-day
    # re-run with unchanged `index.html` cache-hits (no duplicate Session
    # block — desirable, nothing changed); a next-day re-run misses
    # exactly when the brief would write a different date.
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return make_llm_key(
        node="p4_persist_session",
        version=_CACHE_VERSION,
        slug=slug,
        files=[index_html_path],
        extras=(today,),
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)

# Phase 4 gates whose records belong in the persisted Session block. Filtering
# narrows the brief input to relevant context (design / plan / static_guard,
# plus the future cluster from HOM-127); Phase 3 gates (edl_ok, eval_ok)
# already belong to that phase's own Session block.
_PHASE4_GATES = {
    "gate:design_ok",
    "gate:plan_ok",
    "gate:lint",
    "gate:validate",
    "gate:inspect",
    "gate:design_adherence",
    "gate:animation_map",
    "gate:snapshot",
    "gate:captions_track",
    "gate:static_guard",
}


def _project_md_path(state: dict) -> Path:
    return Path(state["episode_dir"]) / "edit" / "project.md"


def _phase4_gate_records(state: dict) -> list[dict]:
    return [
        rec for rec in (state.get("gate_results") or [])
        if rec.get("gate") in _PHASE4_GATES
    ]


def _beats_summary(compose: dict) -> list[dict]:
    """Compact one-entry-per-beat list for the brief.

    The full BeatState shape carries scene-fragment HTML and per-beat tool
    traces; the persist sub-agent only needs identifying metadata to write
    a meaningful Session block. We keep this narrow on purpose — the brief
    is task input, not a state dump.
    """
    plan = compose.get("plan") or {}
    plan_beats = plan.get("beats") or []
    out: list[dict] = []
    state_beats = compose.get("beats") or []
    by_id = {b.get("beat_id"): b for b in state_beats if isinstance(b, dict)}
    for pb in plan_beats:
        beat_id = pb.get("id") or pb.get("beat_id")
        sb = by_id.get(beat_id) or {}
        out.append({
            "beat_id": beat_id,
            "title": pb.get("title") or pb.get("name"),
            "duration_s": pb.get("duration_s"),
            "scene_path": sb.get("scene_path"),
            "status": sb.get("status") or ("planned" if not sb else "unknown"),
        })
    return out


def _render_ctx(state: dict) -> dict:
    compose = state.get("compose") or {}
    design = compose.get("design") or {}
    expansion = compose.get("expansion") or {}
    plan = compose.get("plan") or {}
    captions = compose.get("captions") or {}
    assemble = compose.get("assemble") or {}
    return {
        "project_md_path": str(_project_md_path(state)),
        "design_md_path": design.get("design_md_path") or "",
        "expanded_prompt_path": expansion.get("expanded_prompt_path") or "",
        "plan_json": json.dumps(plan, ensure_ascii=False),
        "beats_json": json.dumps(_beats_summary(compose), ensure_ascii=False),
        "captions_block_path": (
            compose.get("captions_block_path")
            or captions.get("captions_block_path")
            or ""
        ),
        "index_html_path": assemble.get("index_html_path") or assemble.get("assembled_at") or "",
        "gate_results_json": json.dumps(_phase4_gate_records(state), ensure_ascii=False),
        "today": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }


def _build_node() -> LLMNode:
    return LLMNode(
        name="p4_persist_session",
        requirements=NodeRequirements(tier="cheap", needs_tools=True, backends=["claude", "codex"]),
        brief_template=_load_brief("p4_persist_session"),
        output_schema=PersistSessionResult,
        result_namespace="compose",
        result_key="persist",
        timeout_s=120,
        allowed_tools=["Read", "Write"],
        extra_render_ctx=_render_ctx,
    )


def p4_persist_session_node(state, *, router: BackendRouter | None = None):
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return {"compose": {"persist": {"skipped": True, "skip_reason": "no episode_dir in state"}}}
    compose = state.get("compose") or {}
    assemble = compose.get("assemble") or {}
    if assemble.get("skipped"):
        return {
            "compose": {
                "persist": {
                    "skipped": True,
                    "skip_reason": (
                        f"upstream assemble skipped: "
                        f"{assemble.get('skip_reason') or 'unknown'}"
                    ),
                },
            },
        }
    if not assemble.get("assembled_at") and not assemble.get("index_html_path"):
        return {
            "compose": {
                "persist": {
                    "skipped": True,
                    "skip_reason": "no assembled index.html — nothing to persist",
                },
            },
        }

    node = _build_node()
    update = node(state, router=router)
    persist = (update.get("compose") or {}).get("persist") or {}
    update_compose = update.setdefault("compose", {})
    if "skipped" not in persist and "raw_text" not in persist:
        persist.setdefault("persisted_at", str(_project_md_path(state)))
        update_compose["session_persisted"] = True
    update_compose["persist"] = persist
    return update
