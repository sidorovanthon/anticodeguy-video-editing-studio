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

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from ..schemas.p4_design_system import DesignDoc
from ._llm import LLMNode, _load_brief


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
