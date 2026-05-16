"""p4_design_system — smart LLM node for the canonical Step 1 visual identity.

Implements hyperframes SKILL.md §"Step 1: Design system" via a brief that
REFERENCES the canon path rather than embedding it (per
`feedback_graph_decomposition_brief_references_canon`). The dispatched
sub-agent reads canon at call time using the `Read` tool and returns a
structured `DesignDoc` with the full DESIGN.md body in the `design_md`
field; the orchestrator writes the file to disk (HOM-232 — state-first
artifacts, Step B of HOM-230). `gate:design_ok` validates the structured
substance bounds; downstream disk-readers (`p4_assemble_index.py:588`
etc.) keep working off the dual-written file until Step D2 strips the
dual-write.

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
from .._paths import EpisodePaths
from ..schemas.p4_design_system import DesignDoc
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. See HOM-132 spec §8 review
# checkpoint and `feedback_code_review_before_merge` memory.
# v2 (HOM-201): brief now mandates pre-baked gradient-stop / highlight
# derivatives in the palette so downstream `p4_beat` never improvises
# off-palette hexes for gradients / shadows. Shape unchanged ({role, hex}).
# v3 (HOM-224): identity-only state writes — `compose.design_md_path`
# top-level mirror dropped; brief no longer renders the absolute path
# context for episode_dir / design_md_path (path derived via slug at
# read sites). Brief context shape changed → cache invalidation.
# v4 (HOM-232): state-first artifacts (Step B of HOM-230 epic). Brief
# no longer instructs the sub-agent to call `Write`; the full DESIGN.md
# body now comes back in the structured `DesignDoc.design_md` field and
# the orchestrator dual-writes the file to `design_md_path` so today's
# disk-readers (e.g. `p4_assemble_index.py:588`) keep working. `Write`
# dropped from `allowed_tools`. Output schema and brief both changed →
# cache invalidation.
# v5 (HOM-239 / Step D2 of HOM-230): dual-write stripped. The DESIGN.md
# body remains in `compose.design.design_md`; `p4_materialize_disk_node`
# is now the single deterministic writer and regenerates the file from
# state on demand. Node output contract changed (no more disk side-effect)
# → cache invalidation.
_CACHE_VERSION = 5


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
    edit = state.get("edit") or {}
    strategy = edit.get("strategy") or {}
    # HOM-224: derive paths via EpisodePaths(slug) — primary read path. p3
    # state echoes (`transcripts.final_json_path`, `edl.edl_path`) are gone
    # post-HOM-223. The unbound-slug case (graph introspection) still needs
    # to produce a stable key, so fall through with `None` paths and let
    # `make_llm_key` fingerprint the missing files as a stable nonce.
    if slug and slug != "__unbound__":
        paths = EpisodePaths(slug)
        final_json_path = str(paths.transcripts_final_json_path)
        edl_path = str(paths.edit_dir / "edl.json")
    else:
        final_json_path = None
        edl_path = None
    return make_llm_key(
        node="p4_design_system",
        version=_CACHE_VERSION,
        slug=slug,
        files=[final_json_path, edl_path],
        extras=(strategy_fingerprint(strategy),),
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


def _design_md_path(state: dict) -> Path:
    # HOM-224: derive from slug; no state echo.
    slug = state.get("slug")
    if not slug:
        # Legacy fallback used only when slug is missing (synthetic-state
        # unit tests pre-pickup). Production graph always has slug post-pickup.
        episode_dir = state.get("episode_dir")
        if episode_dir:
            return Path(episode_dir) / "hyperframes" / "DESIGN.md"
        raise RuntimeError("p4_design_system: slug missing from state (pickup must run first)")
    return EpisodePaths(slug).design_md_path


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
    # `design_md_path` is rendered into the brief so the sub-agent can echo
    # it back in `DesignDoc.design_md_path` for `gate:design_ok`; the
    # orchestrator (not the sub-agent) does the file write post-HOM-232.
    # Path derived via `EpisodePaths(slug)` (HOM-224); state echo dropped.
    return {
        "design_md_path": str(_design_md_path(state)),
        "strategy_json": json.dumps(_strategy(state), ensure_ascii=False),
        "edl_beats_json": json.dumps(_edl_beats(state), ensure_ascii=False),
    }


def _build_node() -> LLMNode:
    return LLMNode(
        name="p4_design_system",
        requirements=NodeRequirements(tier="expensive", needs_tools=True, backends=["claude"]),
        brief_template=_load_brief("p4_design_system"),
        output_schema=DesignDoc,
        result_namespace="compose",
        result_key="design",
        timeout_s=240,
        allowed_tools=["Read"],
        extra_render_ctx=_render_ctx,
    )


def p4_design_system_node(state, *, router: BackendRouter | None = None):
    slug = state.get("slug")
    if not slug:
        return {"compose": {"design": {"skipped": True, "skip_reason": "no slug in state"}}}
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

    # HOM-224: no longer mirror `compose.design_md_path` from the structured
    # output. Identity-only state — downstream nodes derive the path via
    # `EpisodePaths(slug).design_md_path` at use-site.
    # HOM-239 (Step D2 of HOM-230 state-first artifacts): dual-write to
    # `design_md_path` stripped. The DESIGN.md body lives in
    # `compose.design.design_md` and `p4_materialize_disk_node` is the
    # single deterministic writer downstream.
    return _build_node()(state, router=router)
