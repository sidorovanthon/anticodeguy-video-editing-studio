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
  - cached skip when fragment file already exists with non-zero size
    (poor-man's cache — full CachePolicy + SqliteCache lands under HOM-132)
  - briefs reference canon paths, never embed canon
    (`feedback_graph_decomposition_brief_references_canon`)

Smoke + production model selection happens in `graph/config.yaml` via
per-node `model:` override; the dataclass below sets only the tier ceiling.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from ._llm import LLMNode, _load_brief


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
    scene_id = bd.get("scene_id") or "?"
    scene_html_path = bd.get("scene_html_path")

    # Cached skip: if the fragment already exists with non-zero size, the
    # previous run authored it. Re-running is free under this gate. Brief
    # drift requires the operator to delete the file — documented in PR.
    if scene_html_path:
        scene_path = Path(scene_html_path)
        try:
            if scene_path.is_file() and scene_path.stat().st_size > 0:
                return {"notices": [f"p4_beat[{scene_id}]: cached, skipping"]}
        except OSError:
            # stat failure is genuinely unusual; fall through and let the
            # LLM dispatch run, which will overwrite or surface the error
            # via its own Write tool path.
            pass

    # Ensure the destination directory exists so the sub-agent's `Write`
    # call lands in a real folder.
    if scene_html_path:
        Path(scene_html_path).parent.mkdir(parents=True, exist_ok=True)

    node = _build_node()
    return node(state, router=router)
