"""p3_self_eval — cheap LLM node that runs canon §"The process" Step 7.

Inspects the rendered final.mp4 at every cut boundary (±1.5s window) using
the canon `timeline_view.py` helper. Phase 3 produces no overlays/subtitles,
so HR 1 and HR 4 checks are out of scope here (Phase 4 owns them). The
remaining canon checks are visual discontinuity at the cut, audio-pop past
the 30ms fade (HR 3), and grade consistency.

Deterministic duration verification (ffprobe vs EDL `total_duration_s`
±100ms) lives in the downstream `gate:eval_ok`, not in the brief — keeps
the LLM focused on perceptual checks where its visual judgment matters.
"""

from __future__ import annotations

import json
from pathlib import Path

from langgraph.types import CachePolicy

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from .._caching import make_llm_key
from ..schemas.p3_self_eval import EvalReport
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. Spec §8 review checkpoint.
_CACHE_VERSION = 1

TIMELINE_VIEW_PATH = Path.home() / ".claude" / "skills" / "video-use" / "helpers" / "timeline_view.py"


def _final_mp4_path(state: dict) -> str | None:
    render = (state.get("edit") or {}).get("render") or {}
    explicit = render.get("final_mp4")
    if explicit:
        return str(explicit)
    if not state.get("episode_dir"):
        return None
    return str(Path(state["episode_dir"]) / "edit" / "final.mp4")


def _edl_path(state: dict) -> str | None:
    edl = (state.get("edit") or {}).get("edl") or {}
    explicit = edl.get("edl_path")
    if explicit:
        return str(explicit)
    if not state.get("episode_dir"):
        return None
    return str(Path(state["episode_dir"]) / "edit" / "edl.json")


def _eval_iteration(state: dict) -> int:
    """Render-eval iteration — number of `gate:eval_ok` records so far.

    Spec §6 lists `extras=(edit.iteration,)` for `p3_self_eval`. There is
    no `edit.iteration` field on `GraphState`; the de-facto counter is
    derived from `gate_results` (the same logic `p3_persist_session` uses
    via `_iteration_count`). Including it ensures a forced re-eval on
    iteration N+1 cache-misses even when `final.mp4`/`edl.json` content
    are byte-identical (operator's "judge again" intent).
    """
    n = 0
    for rec in state.get("gate_results") or []:
        if rec.get("gate") == "gate:eval_ok":
            n += 1
    return n


def _cache_key(state, *_args, **_kwargs):
    """Cache key for `p3_self_eval`.

    Brief inputs are `final_mp4_path` (Read/Bash) and `edl_path` (Read);
    derived `cut_boundaries_json` is a function of EDL content (covered by
    `edl_path` fingerprint) and so does not need its own extra. The
    `iteration` extra defends against forced re-runs on identical artifacts.
    """
    if not isinstance(state, dict):
        raise TypeError(
            f"p3_self_eval cache key requires dict state, got {type(state).__name__}"
        )
    slug = state.get("slug") or "__unbound__"
    return make_llm_key(
        node="p3_self_eval",
        version=_CACHE_VERSION,
        slug=slug,
        files=[_final_mp4_path(state), _edl_path(state)],
        extras=(_eval_iteration(state),),
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


def _cut_boundaries(state: dict) -> tuple[list[float], list[dict]]:
    """Return (output_time_boundaries, per_range_source_boundaries).

    Output-time boundaries are the timestamps where adjacent ranges meet in
    the rendered output: cumulative sum of range durations. The first cut is
    at the end of range 0; the last cut is at the start of the final range.
    Per-source boundaries pair each range's source key with its (start, end)
    in the source — useful when the sub-agent wants to drill into the source
    rather than the rendered output.
    """
    edl = (state.get("edit") or {}).get("edl") or {}
    ranges = edl.get("ranges") or []
    out_times: list[float] = []
    cursor = 0.0
    for r in ranges[:-1]:
        try:
            dur = float(r.get("end")) - float(r.get("start"))
        except (TypeError, ValueError):
            continue
        cursor += dur
        out_times.append(round(cursor, 3))
    source_pairs = [
        {"index": i, "source": r.get("source"), "start": r.get("start"), "end": r.get("end")}
        for i, r in enumerate(ranges)
    ]
    return out_times, source_pairs


def _render_ctx(state: dict) -> dict:
    edit = state.get("edit") or {}
    render = edit.get("render") or {}
    final_mp4 = render.get("final_mp4") or str(
        Path(state.get("episode_dir") or ".") / "edit" / "final.mp4"
    )
    edl_path = str(Path(state.get("episode_dir") or ".") / "edit" / "edl.json")
    boundaries, sources = _cut_boundaries(state)
    return {
        "final_mp4_path": final_mp4,
        "edl_path": edl_path,
        "cut_boundaries_json": json.dumps(boundaries),
        "source_cut_boundaries_json": json.dumps(sources, ensure_ascii=False),
        "timeline_view_path": str(TIMELINE_VIEW_PATH),
    }


def _build_node() -> LLMNode:
    return LLMNode(
        name="p3_self_eval",
        requirements=NodeRequirements(tier="cheap", needs_tools=True, backends=["claude", "codex"]),
        brief_template=_load_brief("p3_self_eval"),
        output_schema=EvalReport,
        result_namespace="edit",
        result_key="eval",
        timeout_s=180,
        allowed_tools=["Read", "Bash"],
        extra_render_ctx=_render_ctx,
    )


def p3_self_eval_node(state, *, router: BackendRouter | None = None):
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return {"edit": {"eval": {"skipped": True, "skip_reason": "no episode_dir in state"}}}
    render = (state.get("edit") or {}).get("render") or {}
    if render.get("skipped"):
        return {
            "edit": {
                "eval": {
                    "skipped": True,
                    "skip_reason": f"upstream render skipped: {render.get('skip_reason') or 'unknown'}",
                },
            },
        }
    final_mp4 = render.get("final_mp4")
    if not final_mp4 or not Path(final_mp4).exists():
        return {"edit": {"eval": {"skipped": True, "skip_reason": f"final.mp4 missing at {final_mp4}"}}}

    node = _build_node()
    update = node(state, router=router)
    eval_report = (update.get("edit") or {}).get("eval") or {}
    if "skipped" not in eval_report and "raw_text" not in eval_report:
        eval_report.setdefault("issues", [])
        eval_report["final_mp4_path"] = final_mp4
    update.setdefault("edit", {})["eval"] = eval_report
    return update
