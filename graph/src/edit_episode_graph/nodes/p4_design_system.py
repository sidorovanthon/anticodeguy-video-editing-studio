"""p4_design_system — smart LLM node for the canonical Step 1 visual identity.

Implements hyperframes SKILL.md §"Step 1: Design system" via a brief that
REFERENCES the canon path rather than embedding it (per
`feedback_graph_decomposition_brief_references_canon`). The dispatched
sub-agent reads canon at call time using the `Read` tool, writes a real
`DESIGN.md` to disk via the `Write` tool, and returns a structured
`DesignDoc` for `gate:design_ok` to validate.

Tier: smart. Visual identity is creative — palette, typography,
references, alternatives, anti-patterns, beat→visual mapping. Cheap models
empirically hollow it out (per `feedback_creative_nodes_flagship_tier`).
"""

from __future__ import annotations

import json
from pathlib import Path

from langgraph.types import CachePolicy

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from .._caching import make_llm_key, strategy_fingerprint
from ..schemas.p4_design_system import DesignDoc
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. See HOM-132 spec §8 review
# checkpoint and `feedback_code_review_before_merge` memory.
_CACHE_VERSION = 1


def _cache_key(state, *_args, **_kwargs):
    """Cache key for `p4_design_system`.

    Captures every upstream input the brief consumes (`p4_design_system.j2`
    renders `strategy_json`, `edl_beats_json`, `design_md_path`):

    * `slug` — per-episode namespace; missing/empty → fail fast.
    * `transcripts.final_json_path` — final transcript content drives
      copy/voice decisions in the design.
    * `edit.edl.edl_path` — content fingerprint covers beat changes
      (the brief feeds `edl_beats_json` derived from `edl.ranges`).
    * strategy hash via `extras` — captures in-memory strategy edits
      that don't necessarily change `edl.json` (e.g. `length_estimate_s`
      tweaks that the brief still echoes through `strategy_json`).

    Spec §6 row for `p4_design_system` reflects this shape.
    """
    if not isinstance(state, dict):
        # Defensive — every realistic call path passes a dict. Anything
        # else is a programming error worth surfacing immediately.
        raise TypeError(
            f"p4_design_system cache key requires dict state, got {type(state).__name__}"
        )
    # NOTE: empty slug is tolerated here (`__unbound__` sentinel) because
    # LangGraph's `compiled.get_graph()` evaluates `key_func` against the
    # state-channel default during graph introspection (verified against
    # `langgraph/pregel/_algo.py:648`). Raising on empty slug breaks every
    # topology test + Studio's static graph rendering. In production, an
    # empty slug at execution time fails downstream in the node body
    # (which requires `episode_dir`), so safety is preserved.
    slug = state.get("slug") or "__unbound__"
    transcripts = state.get("transcripts") or {}
    edit = state.get("edit") or {}
    edl = edit.get("edl") or {}
    strategy = edit.get("strategy") or {}
    return make_llm_key(
        node="p4_design_system",
        version=_CACHE_VERSION,
        slug=slug,
        files=[transcripts.get("final_json_path"), edl.get("edl_path")],
        extras=(strategy_fingerprint(strategy),),
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


def _design_md_path(state: dict) -> Path:
    return Path(state["episode_dir"]) / "hyperframes" / "DESIGN.md"


def _strategy(state: dict) -> dict:
    strat = (state.get("edit") or {}).get("strategy") or {}
    return {k: v for k, v in strat.items() if k not in {"skipped", "skip_reason", "source_path"}}


def _edl_beats(state: dict) -> list[str]:
    edl = (state.get("edit") or {}).get("edl") or {}
    ranges = edl.get("ranges") or []
    seen: list[str] = []
    for r in ranges:
        beat = r.get("beat")
        if beat and beat not in seen:
            seen.append(beat)
    return seen


def _render_ctx(state: dict) -> dict:
    return {
        "design_md_path": str(_design_md_path(state)),
        "strategy_json": json.dumps(_strategy(state), ensure_ascii=False),
        "edl_beats_json": json.dumps(_edl_beats(state), ensure_ascii=False),
    }


def _build_node() -> LLMNode:
    return LLMNode(
        name="p4_design_system",
        requirements=NodeRequirements(tier="smart", needs_tools=True, backends=["claude"]),
        brief_template=_load_brief("p4_design_system"),
        output_schema=DesignDoc,
        result_namespace="compose",
        result_key="design",
        timeout_s=240,
        allowed_tools=["Read", "Write"],
        extra_render_ctx=_render_ctx,
    )


def p4_design_system_node(state, *, router: BackendRouter | None = None):
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return {"compose": {"design": {"skipped": True, "skip_reason": "no episode_dir in state"}}}
    edl = (state.get("edit") or {}).get("edl") or {}
    if edl.get("skipped") or not edl.get("ranges"):
        return {
            "compose": {
                "design": {
                    "skipped": True,
                    "skip_reason": "no EDL beats to map (upstream skip or empty ranges)",
                },
            },
        }

    # Ensure the destination directory exists so the sub-agent's `Write`
    # call lands in a real folder. The hyperframes scaffold (p4_scaffold)
    # also creates this dir, but design_system runs upstream of scaffold
    # in the v4 topology — scaffold then consumes DESIGN.md.
    _design_md_path(state).parent.mkdir(parents=True, exist_ok=True)

    node = _build_node()
    update = node(state, router=router)
    design = (update.get("compose") or {}).get("design") or {}
    if "skipped" not in design and "raw_text" not in design:
        # Mirror the design_md_path from the structured output up to the
        # `compose.design_md_path` ergonomic field referenced by the spec.
        update.setdefault("compose", {})["design_md_path"] = design.get("design_md_path")
    return update
