"""p4_beat — smart LLM node for per-scene Pattern A authoring (HOM-134).

One Send per beat from `p4_dispatch_beats`. Each invocation reads the
upstream design system + expanded-prompt + canon docs via the `Read` tool
and writes a single Pattern A fragment to
`compositions/<scene_id>.html` via the `Write` tool. The deterministic
`p4_assemble_index` node fans in and inlines those fragments into the
root `index.html`.

Per spec `2026-05-04-hom-122-p4-beats-fan-out-design.md`:
  - tier=smart (creative — `feedback_creative_nodes_flagship_tier`)
  - allowed_tools = [Read, Write]
  - briefs reference canon paths, never embed canon
    (`feedback_graph_decomposition_brief_references_canon`)

Caching: `CACHE_POLICY` keyed on (slug, design_md_path,
expanded_prompt_path) with `extras=(beat_id,)` per HOM-150 / spec §6.
The prior poor-man's "skip if file exists" stub is replaced by the
native LangGraph cache.

Smoke + production model selection happens in `graph/config.yaml` via
per-node `model:` override; the dataclass below sets only the tier ceiling.
"""

from __future__ import annotations

import json
from pathlib import Path

from langgraph.types import CachePolicy

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from .._caching import make_key, stable_fingerprint
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. See HOM-132 spec §8.
_CACHE_VERSION = 1


def _cache_key(state, *_args, **_kwargs):
    if not isinstance(state, dict):
        raise TypeError(
            f"p4_beat cache key requires dict state, got {type(state).__name__}"
        )
    # Per-Send invocation: each beat's `_beat_dispatch.scene_id` namespaces
    # the key. See p4_design_system._cache_key for the empty-slug rationale.
    slug = state.get("slug") or "__unbound__"
    compose = state.get("compose") or {}
    bd = state.get("_beat_dispatch") or {}
    beat_id = bd.get("scene_id") or bd.get("beat_id") or "__unbound__"
    # `plan_beat_json` (concept / mood / energy / duration for THIS beat) is
    # rendered verbatim into the brief (line 12 of briefs/p4_beat.j2). It
    # lives in-memory on `_beat_dispatch.plan_beat`, NOT on disk —
    # transitive design_md / expanded_prompt invalidation does not catch a
    # plan-only change for the same beat_id (e.g. p4_plan re-runs and
    # produces different concept/mood for the same scene).
    plan_beat = bd.get("plan_beat") or {}
    return make_key(
        node="p4_beat",
        version=_CACHE_VERSION,
        slug=slug,
        files=[
            compose.get("design_md_path"),
            compose.get("expanded_prompt_path"),
        ],
        extras=(beat_id, stable_fingerprint(plan_beat)),
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


def _catalog_summary(state: dict) -> str:
    """Compact one-line-per-item summary for the brief.

    Catalog is ~8 KB JSON in state; we don't need to dump it whole into
    every Send's brief — names + paths are enough for the sub-agent to
    decide whether to `Read` the source.
    """
    catalog = (state.get("compose") or {}).get("catalog") or {}
    blocks = catalog.get("blocks") or []
    components = catalog.get("components") or []
    lines: list[str] = []
    if blocks:
        lines.append("Blocks:")
        for b in blocks:
            name = b.get("name") or "?"
            path = b.get("path") or "?"
            lines.append(f"  - {name} ({path})")
    if components:
        lines.append("Components:")
        for c in components:
            name = c.get("name") or "?"
            path = c.get("path") or "?"
            lines.append(f"  - {name} ({path})")
    if not lines:
        lines.append("(catalog empty — no blocks/components installed)")
    return "\n".join(lines)


def _render_ctx(state: dict) -> dict:
    bd = state.get("_beat_dispatch") or {}
    compose = state.get("compose") or {}
    return {
        "scene_id": bd.get("scene_id", ""),
        "beat_index": bd.get("beat_index", 0),
        "total_beats": bd.get("total_beats", 0),
        "is_final": bool(bd.get("is_final", False)),
        "data_start_s": bd.get("data_start_s", 0.0),
        "data_duration_s": bd.get("data_duration_s", 0.0),
        "data_track_index": bd.get("data_track_index", 1),
        "data_width": bd.get("data_width", 1920),
        "data_height": bd.get("data_height", 1080),
        "plan_beat_json": json.dumps(bd.get("plan_beat") or {}, ensure_ascii=False),
        "design_md_path": compose.get("design_md_path") or "",
        "expanded_prompt_path": compose.get("expanded_prompt_path") or "",
        "catalog_summary": _catalog_summary(state),
        "scene_html_path": bd.get("scene_html_path", ""),
    }


def _build_node() -> LLMNode:
    return LLMNode(
        name="p4_beat",
        requirements=NodeRequirements(tier="smart", needs_tools=True, backends=["claude"]),
        brief_template=_load_brief("p4_beat"),
        output_schema=None,
        result_namespace="compose",
        result_key="_beat_unused",
        timeout_s=300,
        allowed_tools=["Read", "Write"],
        extra_render_ctx=_render_ctx,
    )


def p4_beat_node(state, *, router: BackendRouter | None = None):
    bd = state.get("_beat_dispatch") or {}
    scene_html_path = bd.get("scene_html_path")

    # Ensure the destination directory exists so the sub-agent's `Write`
    # call lands in a real folder.
    if scene_html_path:
        Path(scene_html_path).parent.mkdir(parents=True, exist_ok=True)

    node = _build_node()
    return node(state, router=router)
