"""p3_strategy - smart LLM node for Phase 3 cut strategy."""

from __future__ import annotations

import json
from pathlib import Path

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from ..schemas.p3_strategy import Strategy
from ._llm import LLMNode, _load_brief


def _takes_packed_path(state: dict) -> Path:
    explicit = (state.get("transcripts") or {}).get("takes_packed_path")
    if explicit:
        return Path(explicit)
    return Path(state["episode_dir"]) / "edit" / "takes_packed.md"


def _pre_scan_slips(state: dict) -> list[dict]:
    pre_scan = (state.get("edit") or {}).get("pre_scan") or {}
    slips = pre_scan.get("slips") or []
    return slips if isinstance(slips, list) else []


def _render_ctx(state: dict) -> dict:
    takes = _takes_packed_path(state)
    revisions = state.get("strategy_revisions") or []
    return {
        "takes_packed_path": str(takes),
        "takes_packed_text": takes.read_text(encoding="utf-8"),
        "pre_scan_slips_json": json.dumps(_pre_scan_slips(state), ensure_ascii=False),
        "strategy_revisions": revisions,
        "strategy_revisions_json": json.dumps(revisions, ensure_ascii=False),
    }


def _build_node() -> LLMNode:
    return LLMNode(
        name="p3_strategy",
        requirements=NodeRequirements(tier="smart", needs_tools=False, backends=["claude"]),
        brief_template=_load_brief("p3_strategy"),
        output_schema=Strategy,
        result_namespace="edit",
        result_key="strategy",
        timeout_s=120,
        allowed_tools=[],
        extra_render_ctx=_render_ctx,
    )


def p3_strategy_node(state, *, router: BackendRouter | None = None):
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return {"edit": {"strategy": {"skipped": True, "skip_reason": "no episode_dir in state"}}}
    takes = _takes_packed_path(state)
    if not takes.exists():
        return {"edit": {"strategy": {"skipped": True, "skip_reason": f"takes_packed.md missing at {takes}"}}}
    node = _build_node()
    update = node(state, router=router)
    strategy = (update.get("edit") or {}).get("strategy") or {}
    if "skipped" not in strategy:
        strategy["source_path"] = str(takes)
        update.setdefault("edit", {})["strategy"] = strategy
    return update
