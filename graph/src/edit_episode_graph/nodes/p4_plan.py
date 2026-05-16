"""p4_plan — smart LLM node for the canonical Step 3 composition plan.

Implements hyperframes SKILL.md §"Step 3: Plan" via a brief that
REFERENCES the canon path rather than embedding it (per
`feedback_graph_decomposition_brief_references_canon`). The dispatched
sub-agent reads canon (SKILL.md + `references/beat-direction.md` +
`references/transitions.md`) plus DESIGN.md and expanded-prompt.md from
disk, then returns a `CompositionPlan` purely as structured JSON. No
on-disk artifact at this step — plan is "thinking" upstream of HTML, not
a downstream-readable file (downstream beat sub-agents consume it via the
`compose.plan` state slice).

Tier: smart. Plan determines pacing, energy peaks, scene rhythm, and
per-boundary transition choice — all creative direction. Spec §6.3
originally marked `cheap`; HOM-120 amends to `smart` (memory
`feedback_creative_nodes_flagship_tier`).
"""

from __future__ import annotations

import json

from langgraph.types import CachePolicy

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from .._caching import make_llm_key, stable_fingerprint, strategy_fingerprint
from .._paths import EpisodePaths
from ..schemas.p4_plan import CompositionPlan
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. See HOM-132 spec §8.
# v2: HOM-190 — relaxed CompositionPlan.beats min_length 3→1, transitions
# min_length 1→0 (schemas encode invariants, not creative-direction targets).
# v3 (HOM-224): identity-only state writes — paths derived via
# `EpisodePaths(slug)` at use-sites; brief no longer renders `episode_dir`.
# v4 (HOM-265 / Step E partial of HOM-230): consumer-side gates switched
# from disk-presence to state-body presence. Brief migrated from
# "Read these paths" to embedded bodies — DESIGN.md and expanded-prompt.md
# are inlined directly in the brief context so the sub-agent no longer
# calls `Read` on either file. Cache-key inputs (`files=[...]`) unchanged
# in this PR — full Step E refactor deferred.
_CACHE_VERSION = 4


def _cache_key(state, *_args, **_kwargs):
    if not isinstance(state, dict):
        raise TypeError(
            f"p4_plan cache key requires dict state, got {type(state).__name__}"
        )
    # See p4_design_system._cache_key for the empty-slug rationale.
    slug = state.get("slug") or "__unbound__"
    edit = state.get("edit") or {}
    # `strategy_json` and `edl_beats_json` are rendered verbatim into the
    # brief (lines 30-32 of briefs/p4_plan.j2). They live in-memory on
    # `state.edit.strategy` / `state.edit.edl.ranges`, NOT on disk — so
    # transitive file-fingerprint invalidation does not cover them.
    # Hashed as `extras` per spec §6 row update in this PR.
    strategy = edit.get("strategy") or {}
    edl_beats = _edl_beats(state)
    # HOM-224: derive paths via EpisodePaths(slug) — identity-only state.
    if slug and slug != "__unbound__":
        paths = EpisodePaths(slug)
        design_md_path: str | None = str(paths.design_md_path)
        expanded_prompt_path: str | None = str(paths.expanded_prompt_path)
        final_json_path: str | None = str(paths.transcripts_final_json_path)
    else:
        design_md_path = None
        expanded_prompt_path = None
        final_json_path = None
    return make_llm_key(
        node="p4_plan",
        version=_CACHE_VERSION,
        slug=slug,
        files=[
            design_md_path,
            expanded_prompt_path,
            final_json_path,
        ],
        extras=(
            strategy_fingerprint(strategy),
            stable_fingerprint(edl_beats),
        ),
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


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


def _design_md_path(state: dict) -> str:
    """HOM-224: derive via slug; legacy fallback for pre-pickup synthetic state."""
    slug = state.get("slug")
    if slug:
        return str(EpisodePaths(slug).design_md_path)
    compose = state.get("compose") or {}
    path = compose.get("design_md_path")
    if path:
        return str(path)
    design = compose.get("design") or {}
    return str(design.get("design_md_path") or "")


def _expanded_prompt_path(state: dict) -> str:
    """HOM-224: derive via slug; legacy fallback for pre-pickup synthetic state."""
    slug = state.get("slug")
    if slug:
        return str(EpisodePaths(slug).expanded_prompt_path)
    compose = state.get("compose") or {}
    path = compose.get("expanded_prompt_path")
    if path:
        return str(path)
    expansion = compose.get("expansion") or {}
    return str(expansion.get("expanded_prompt_path") or "")


def _design_md_body(state: dict) -> str:
    """HOM-265: read DESIGN.md body from state (post Step-D2 source of truth)."""
    compose = state.get("compose") or {}
    design = compose.get("design") or {}
    body = design.get("design_md")
    return body if isinstance(body, str) else ""


def _expanded_prompt_body(state: dict) -> str:
    """HOM-265: read expanded-prompt.md body from state."""
    compose = state.get("compose") or {}
    expansion = compose.get("expansion") or {}
    body = expansion.get("expanded_prompt")
    return body if isinstance(body, str) else ""


def _render_ctx(state: dict) -> dict:
    return {
        "design_md_path": _design_md_path(state),
        "expanded_prompt_path": _expanded_prompt_path(state),
        # HOM-265: inline body strings — sub-agent no longer Reads from disk.
        "design_md_body": _design_md_body(state),
        "expanded_prompt_body": _expanded_prompt_body(state),
        "strategy_json": json.dumps(_strategy(state), ensure_ascii=False),
        "edl_beats_json": json.dumps(_edl_beats(state), ensure_ascii=False),
    }


def _build_node() -> LLMNode:
    return LLMNode(
        name="p4_plan",
        requirements=NodeRequirements(tier="expensive", needs_tools=True, backends=["claude"]),
        brief_template=_load_brief("p4_plan"),
        output_schema=CompositionPlan,
        result_namespace="compose",
        result_key="plan",
        timeout_s=240,
        allowed_tools=["Read"],
        extra_render_ctx=_render_ctx,
    )


def p4_plan_node(state, *, router: BackendRouter | None = None):
    slug = state.get("slug")
    if not slug:
        return {"compose": {"plan": {"skipped": True, "skip_reason": "no slug in state"}}}

    # HOM-265 (Step E partial of HOM-230): gate on STATE-BODY presence, not
    # disk-file presence. The post-D2 source of truth for these artifacts
    # is `state.compose.design.design_md` / `state.compose.expansion.expanded_prompt`
    # respectively — `p4_materialize_disk_node` writes the files at chain
    # end, but they are NOT on disk while this node runs.
    if not _design_md_body(state):
        return {
            "compose": {
                "plan": {
                    "skipped": True,
                    "skip_reason": (
                        "no DESIGN.md body in state — upstream p4_design_system "
                        "must run first"
                    ),
                },
            },
        }

    if not _expanded_prompt_body(state):
        return {
            "compose": {
                "plan": {
                    "skipped": True,
                    "skip_reason": (
                        "no expanded-prompt.md body in state — upstream "
                        "p4_prompt_expansion must run first"
                    ),
                },
            },
        }

    edl = (state.get("edit") or {}).get("edl") or {}
    if edl.get("skipped") or not edl.get("ranges"):
        return {
            "compose": {
                "plan": {
                    "skipped": True,
                    "skip_reason": "no EDL beats to plan (upstream skip or empty ranges)",
                },
            },
        }

    node = _build_node()
    return node(state, router=router)
