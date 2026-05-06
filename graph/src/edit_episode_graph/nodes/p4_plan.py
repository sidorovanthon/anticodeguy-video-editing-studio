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
from pathlib import Path

from langgraph.types import CachePolicy

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from .._caching import make_llm_key, stable_fingerprint, strategy_fingerprint
from ..schemas.p4_plan import CompositionPlan
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. See HOM-132 spec §8.
_CACHE_VERSION = 1


def _cache_key(state, *_args, **_kwargs):
    if not isinstance(state, dict):
        raise TypeError(
            f"p4_plan cache key requires dict state, got {type(state).__name__}"
        )
    # See p4_design_system._cache_key for the empty-slug rationale.
    slug = state.get("slug") or "__unbound__"
    compose = state.get("compose") or {}
    transcripts = state.get("transcripts") or {}
    edit = state.get("edit") or {}
    # `strategy_json` and `edl_beats_json` are rendered verbatim into the
    # brief (lines 30-32 of briefs/p4_plan.j2). They live in-memory on
    # `state.edit.strategy` / `state.edit.edl.ranges`, NOT on disk — so
    # transitive file-fingerprint invalidation does not cover them.
    # Hashed as `extras` per spec §6 row update in this PR.
    strategy = edit.get("strategy") or {}
    edl_beats = _edl_beats(state)
    return make_llm_key(
        node="p4_plan",
        version=_CACHE_VERSION,
        slug=slug,
        files=[
            compose.get("design_md_path"),
            compose.get("expanded_prompt_path"),
            transcripts.get("final_json_path"),
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
    compose = state.get("compose") or {}
    path = compose.get("design_md_path")
    if path:
        return str(path)
    design = compose.get("design") or {}
    return str(design.get("design_md_path") or "")


def _expanded_prompt_path(state: dict) -> str:
    compose = state.get("compose") or {}
    path = compose.get("expanded_prompt_path")
    if path:
        return str(path)
    expansion = compose.get("expansion") or {}
    return str(expansion.get("expanded_prompt_path") or "")


def _render_ctx(state: dict) -> dict:
    return {
        "design_md_path": _design_md_path(state),
        "expanded_prompt_path": _expanded_prompt_path(state),
        "strategy_json": json.dumps(_strategy(state), ensure_ascii=False),
        "edl_beats_json": json.dumps(_edl_beats(state), ensure_ascii=False),
    }


def _build_node() -> LLMNode:
    return LLMNode(
        name="p4_plan",
        requirements=NodeRequirements(tier="smart", needs_tools=True, backends=["claude"]),
        brief_template=_load_brief("p4_plan"),
        output_schema=CompositionPlan,
        result_namespace="compose",
        result_key="plan",
        timeout_s=240,
        allowed_tools=["Read"],
        extra_render_ctx=_render_ctx,
    )


def p4_plan_node(state, *, router: BackendRouter | None = None):
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return {"compose": {"plan": {"skipped": True, "skip_reason": "no episode_dir in state"}}}

    if not _design_md_path(state):
        return {
            "compose": {
                "plan": {
                    "skipped": True,
                    "skip_reason": "no DESIGN.md available — upstream p4_design_system must run first",
                },
            },
        }

    if not _expanded_prompt_path(state):
        return {
            "compose": {
                "plan": {
                    "skipped": True,
                    "skip_reason": (
                        "no expanded-prompt.md available — upstream p4_prompt_expansion must "
                        "run first"
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
