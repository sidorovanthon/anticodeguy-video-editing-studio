"""p4_prompt_expansion — smart LLM node for canonical Step 2 prompt expansion.

Implements hyperframes SKILL.md §"Step 2: Prompt expansion" via a brief that
REFERENCES the canon path rather than embedding it (per
`feedback_graph_decomposition_brief_references_canon`). The dispatched
sub-agent reads canon at call time, consumes DESIGN.md from disk, and
returns a structured `ExpandedPrompt` with the full per-scene production
spec body in the `expanded_prompt` field; the orchestrator writes the file
to `.hyperframes/expanded-prompt.md` (HOM-233 — state-first artifacts,
Step B of HOM-230). Downstream disk-readers (`p4_plan`, `p4_beats`) keep
working off the dual-written file until Step D2 strips the dual-write.

Tier: smart. Canon `references/prompt-expansion.md` is explicit that "the
quality gap between a single-pass composition and a multi-scene-pipeline
composition comes from this step" — this is the highest-leverage creative
node in Phase 4 and is never cheap (per `feedback_creative_nodes_flagship_tier`).
"""

from __future__ import annotations

import json
from pathlib import Path

from langgraph.types import CachePolicy

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from .._caching import make_llm_key, stable_fingerprint
from .._paths import EpisodePaths
from ..schemas.p4_prompt_expansion import ExpandedPrompt
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. See HOM-132 spec §8.
# v2 (HOM-224): identity-only state writes — `compose.expanded_prompt_path`
# top-level mirror dropped; brief no longer renders `episode_dir`. Paths
# derived via `EpisodePaths(slug)` at use-sites.
# v3 (HOM-233): state-first artifacts (Step B of HOM-230 epic). Brief no
# longer instructs the sub-agent to call `Write`; the full expanded-prompt
# body now comes back in the structured `ExpandedPrompt.expanded_prompt`
# field and the orchestrator dual-writes the file to `expanded_prompt_path`
# so today's disk-readers (`p4_plan`, `p4_beats`) keep working. `Write`
# dropped from `allowed_tools`. Output schema and brief both changed →
# cache invalidation.
_CACHE_VERSION = 3


def _cache_key(state, *_args, **_kwargs):
    if not isinstance(state, dict):
        raise TypeError(
            f"p4_prompt_expansion cache key requires dict state, got {type(state).__name__}"
        )
    # See p4_design_system._cache_key for the empty-slug rationale (LangGraph
    # introspects `compiled.get_graph()` against the channel default).
    slug = state.get("slug") or "__unbound__"
    compose = state.get("compose") or {}
    style_request = compose.get("style_request") or ""
    # HOM-224: derive paths via EpisodePaths(slug) — identity-only state.
    if slug and slug != "__unbound__":
        paths = EpisodePaths(slug)
        design_md_path: str | None = str(paths.design_md_path)
        final_json_path: str | None = str(paths.transcripts_final_json_path)
    else:
        design_md_path = None
        final_json_path = None
    return make_llm_key(
        node="p4_prompt_expansion",
        version=_CACHE_VERSION,
        slug=slug,
        files=[
            design_md_path,
            final_json_path,
        ],
        extras=(stable_fingerprint(style_request),),
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


def _expanded_prompt_path(state: dict) -> Path:
    # HOM-224: derive from slug; no state echo.
    slug = state.get("slug")
    if not slug:
        episode_dir = state.get("episode_dir")
        if episode_dir:
            return Path(episode_dir) / "hyperframes" / ".hyperframes" / "expanded-prompt.md"
        raise RuntimeError("p4_prompt_expansion: slug missing from state (pickup must run first)")
    return EpisodePaths(slug).expanded_prompt_path


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
    """HOM-224: derive via slug; legacy fallback retained for pre-pickup states."""
    slug = state.get("slug")
    if slug:
        return str(EpisodePaths(slug).design_md_path)
    compose = state.get("compose") or {}
    path = compose.get("design_md_path")
    if path:
        return str(path)
    design = compose.get("design") or {}
    return str(design.get("design_md_path") or "")


def _transcript_path(state: dict) -> str:
    """Resolve transcript JSON path via EpisodePaths(slug). Final wins over raw."""
    slug = state.get("slug")
    if not slug:
        return ""
    paths = EpisodePaths(slug)
    if paths.transcripts_final_json_path.exists():
        return str(paths.transcripts_final_json_path)
    if paths.transcripts_raw_json_path.exists():
        return str(paths.transcripts_raw_json_path)
    return str(paths.transcripts_final_json_path)


def _render_ctx(state: dict) -> dict:
    compose = state.get("compose") or {}
    return {
        "expanded_prompt_path": str(_expanded_prompt_path(state)),
        "design_md_path": _design_md_path(state),
        "strategy_json": json.dumps(_strategy(state), ensure_ascii=False),
        "edl_beats_json": json.dumps(_edl_beats(state), ensure_ascii=False),
        "transcript_json_path": _transcript_path(state),
        "style_request_json": json.dumps(compose.get("style_request") or "", ensure_ascii=False),
    }


def _build_node() -> LLMNode:
    return LLMNode(
        name="p4_prompt_expansion",
        requirements=NodeRequirements(tier="expensive", needs_tools=True, backends=["claude"]),
        brief_template=_load_brief("p4_prompt_expansion"),
        output_schema=ExpandedPrompt,
        result_namespace="compose",
        result_key="expansion",
        timeout_s=300,
        allowed_tools=["Read"],
        extra_render_ctx=_render_ctx,
    )


def p4_prompt_expansion_node(state, *, router: BackendRouter | None = None):
    slug = state.get("slug")
    if not slug:
        return {"compose": {"expansion": {"skipped": True, "skip_reason": "no slug in state"}}}

    design_md_path = _design_md_path(state)
    # HOM-224: derived path is always non-empty when slug is present; gate
    # on disk existence (the meaningful precondition — "DESIGN.md must be
    # on disk before expansion runs"). Pre-HOM-224 the same outcome was
    # achieved by the absence of the state echo.
    if not design_md_path or not Path(design_md_path).is_file():
        return {
            "compose": {
                "expansion": {
                    "skipped": True,
                    "skip_reason": "no DESIGN.md available — upstream p4_design_system must run first",
                },
            },
        }

    edl = (state.get("edit") or {}).get("edl") or {}
    if edl.get("skipped") or not edl.get("ranges"):
        return {
            "compose": {
                "expansion": {
                    "skipped": True,
                    "skip_reason": "no EDL beats to expand (upstream skip or empty ranges)",
                },
            },
        }

    # Ensure the destination dir exists so the orchestrator's dual-write
    # below lands in a real folder. `.hyperframes/` is the canonical HF
    # dotdir per memory `feedback_hf_step2_prompt_expansion`.
    expanded_prompt_path = _expanded_prompt_path(state)
    expanded_prompt_path.parent.mkdir(parents=True, exist_ok=True)

    # HOM-224: no longer mirror `compose.expanded_prompt_path` — identity-only
    # state. Downstream nodes derive via `EpisodePaths(slug).expanded_prompt_path`.
    result = _build_node()(state, router=router)

    # HOM-233 dual-write: the sub-agent returns the expanded-prompt body
    # in `compose.expansion.expanded_prompt` (state-first artifacts, Step B
    # of HOM-230). Today's downstream readers still expect the file on disk
    # (`p4_plan`, `p4_beats` read `.hyperframes/expanded-prompt.md`), so the
    # orchestrator writes from the returned body. Step D2 strips this
    # dual-write once the read-switch has soaked.
    compose = result.get("compose") or {}
    expansion = compose.get("expansion") or {}
    body = expansion.get("expanded_prompt")
    if isinstance(body, str) and body:
        expanded_prompt_path.write_text(body, encoding="utf-8")
    return result
