"""p3_pre_scan — first production LLM node.

Reads `episodes/<slug>/edit/takes_packed.md` (produced by the v3-future
`p3_inventory` node, but already present on episodes that ran video-use
manually) and emits `PreScanReport`.

If `takes_packed.md` does not exist yet, the node returns a "skipped" marker
without calling any backend — this is the v2 path during the LLM-boundary
halt where the inventory step has not yet run. v3 will remove the skip.
"""

from __future__ import annotations

from pathlib import Path

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from ..schemas.p3_pre_scan import PreScanReport
from ._llm import LLMNode, _load_brief


def _build_node() -> LLMNode:
    return LLMNode(
        name="p3_pre_scan",
        requirements=NodeRequirements(tier="cheap", needs_tools=True, backends=["claude", "codex"]),
        brief_template=_load_brief("p3_pre_scan"),
        output_schema=PreScanReport,
        result_namespace="edit",
        result_key="pre_scan",
        timeout_s=90,
        allowed_tools=["Read"],
        extra_render_ctx=lambda state: {
            "takes_packed_path": str(Path(state["episode_dir"]) / "edit" / "takes_packed.md"),
        },
    )


def p3_pre_scan_node(state, *, router: BackendRouter | None = None):
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return {"edit": {"pre_scan": {"skipped": True, "skip_reason": "no episode_dir in state"}}}
    takes = Path(episode_dir) / "edit" / "takes_packed.md"
    if not takes.exists():
        return {"edit": {"pre_scan": {"skipped": True, "skip_reason": f"takes_packed.md missing at {takes}"}}}

    node = _build_node()
    update = node(state, router=router)
    # Ensure the "slips" key is present even when the brief returned an empty list,
    # and tag the source path for traceability.
    pre_scan = (update.get("edit") or {}).get("pre_scan") or {}
    if "slips" not in pre_scan and "skipped" not in pre_scan:
        pre_scan["slips"] = []
    pre_scan["source_path"] = str(takes)
    update.setdefault("edit", {})["pre_scan"] = pre_scan
    return update
