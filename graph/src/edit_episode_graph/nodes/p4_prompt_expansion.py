"""p4_prompt_expansion — smart LLM node for canonical Step 2 prompt expansion.

Implements hyperframes SKILL.md §"Step 2: Prompt expansion" via a brief that
REFERENCES the canon path rather than embedding it (per
`feedback_graph_decomposition_brief_references_canon`). The dispatched
sub-agent reads canon at call time, consumes DESIGN.md from disk, and writes
the per-scene production spec to `.hyperframes/expanded-prompt.md`. The
structured return surfaces the artifact path back into state.

Tier: smart. Canon `references/prompt-expansion.md` is explicit that "the
quality gap between a single-pass composition and a multi-scene-pipeline
composition comes from this step" — this is the highest-leverage creative
node in Phase 4 and is never cheap (per `feedback_creative_nodes_flagship_tier`).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from ..schemas.p4_prompt_expansion import ExpandedPrompt
from ._llm import LLMNode, _load_brief


def _expanded_prompt_path(state: dict) -> Path:
    return Path(state["episode_dir"]) / "hyperframes" / ".hyperframes" / "expanded-prompt.md"


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


def _transcript_path(state: dict) -> str:
    transcripts = state.get("transcripts") or {}
    return str(transcripts.get("final_json_path") or transcripts.get("raw_json_path") or "")


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
        requirements=NodeRequirements(tier="smart", needs_tools=True, backends=["claude"]),
        brief_template=_load_brief("p4_prompt_expansion"),
        output_schema=ExpandedPrompt,
        result_namespace="compose",
        result_key="expansion",
        timeout_s=300,
        allowed_tools=["Read", "Write"],
        extra_render_ctx=_render_ctx,
    )


def p4_prompt_expansion_node(state, *, router: BackendRouter | None = None):
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return {"compose": {"expansion": {"skipped": True, "skip_reason": "no episode_dir in state"}}}

    design_md_path = _design_md_path(state)
    if not design_md_path:
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

    # Ensure the destination dir exists so the sub-agent's `Write` lands.
    # `.hyperframes/` is the canonical HF dotdir per memory
    # `feedback_hf_step2_prompt_expansion`.
    _expanded_prompt_path(state).parent.mkdir(parents=True, exist_ok=True)

    node = _build_node()
    update = node(state, router=router)
    expansion = (update.get("compose") or {}).get("expansion") or {}
    if "skipped" not in expansion and "raw_text" not in expansion:
        update.setdefault("compose", {})["expanded_prompt_path"] = expansion.get("expanded_prompt_path")
    return update
