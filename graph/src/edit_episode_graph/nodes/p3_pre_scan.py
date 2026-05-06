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

from langgraph.types import CachePolicy

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from .._caching import make_key
from ..schemas.p3_pre_scan import PreScanReport
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. Spec §8 review checkpoint.
_CACHE_VERSION = 1


def _takes_packed_path(state: dict) -> str | None:
    """Resolve the path whose content drives this node's output.

    Cache-key path lookup (NOT the production body — `p3_pre_scan_node`
    always reads `<episode_dir>/edit/takes_packed.md` regardless of state).
    For the cache key we additionally honor `transcripts.takes_packed_path`
    when set, mirroring `p3_strategy` / `p3_edl_select`: this way a
    smoke/test that pins the takes path explicitly invalidates the entry
    on content edits, and the override (if ever wired to the body) stays
    consistent across all three Phase 3 LLM nodes.
    """
    if not isinstance(state, dict):
        return None
    explicit = (state.get("transcripts") or {}).get("takes_packed_path")
    if explicit:
        return str(explicit)
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return None
    return str(Path(episode_dir) / "edit" / "takes_packed.md")


def _cache_key(state, *_args, **_kwargs):
    """Cache key for `p3_pre_scan`.

    Brief input is a single file (`takes_packed.md`) read via the `Read`
    tool; edits or deletions invalidate via content hashing.
    """
    if not isinstance(state, dict):
        raise TypeError(
            f"p3_pre_scan cache key requires dict state, got {type(state).__name__}"
        )
    # Empty slug tolerated (`__unbound__` sentinel) — see p4_design_system
    # for the LangGraph introspection rationale.
    slug = state.get("slug") or "__unbound__"
    return make_key(
        node="p3_pre_scan",
        version=_CACHE_VERSION,
        slug=slug,
        files=[_takes_packed_path(state)],
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


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
