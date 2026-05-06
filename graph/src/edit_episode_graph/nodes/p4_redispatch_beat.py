"""p4_redispatch_beat — re-author one scene fragment after a cluster gate fail.

Wires the post-assemble cluster (gate:lint, gate:validate, gate:inspect,
gate:design_adherence, gate:animation_map, gate:snapshot, gate:captions_track)
into the generic retry-with-feedback helper from HOM-147
(`route_after_gate_with_retry`). On a gate fail with `iteration < 3`, routing
lands here; this node re-dispatches a single per-scene authoring brief whose
context carries the prior violations, then routes to `p4_assemble_index` so
the rewritten fragment is inlined back into the root `index.html` and the
gate re-runs.

Beat-owner identification is delegated to the LLM sub-agent (the brief
instructs it to read `index.html`, locate the violations against the
`<!-- beat: <scene_id> -->` marker pairs, and pick ONE owner). The Python
side just supplies:

  - the latest cluster-gate failure (which gate, what violations, iteration N)
  - the canonical plan beats (scene-ids + cumulative starts + durations) so
    the brief can mirror the right `data-start`/`data-duration` values
  - paths to design.md / expanded-prompt.md / index.html / compositions dir

Per spec `2026-05-02-langgraph-pipeline-design.md` §6.2 + per CLAUDE.md
"briefs reference canon, do not embed it" — the brief cites HF SKILL.md
paths and the dispatched sub-agent reads canon at call time.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .._scene_id import scene_id_for
from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from ..gates._base import latest_gate_result
from ._llm import LLMNode, _load_brief
from .p4_beat import _catalog_summary


# Cluster gates whose failure routes here. Order matters only for the
# halt-notice formatting upstream — this list mirrors `_POST_ASSEMBLE_GATES`
# in `halt_llm_boundary.py`.
_CLUSTER_GATES = (
    "gate:lint",
    "gate:validate",
    "gate:inspect",
    "gate:design_adherence",
    "gate:animation_map",
    "gate:snapshot",
    "gate:captions_track",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _latest_cluster_failure(state: dict) -> dict | None:
    """Return the most recent cluster-gate failure record, or None.

    The retry helper only routes here on a fail, so a None return means
    state was hand-injected without a record — we surface a skip rather
    than dispatching against empty context.
    """
    results = state.get("gate_results") or []
    for record in reversed(results):
        if record.get("gate") in _CLUSTER_GATES and not record.get("passed"):
            return record
    return None


def _scene_metadata(state: dict) -> tuple[list[str], list[float], list[float]]:
    """Walk `compose.plan.beats` and return (ids, starts, durations) parallel arrays.

    Mirrors the cumulative-start computation done by `p4_dispatch_beats` and
    `p4_assemble_index`; we pass these to the brief so the rewritten fragment
    carries the canonical timing values rather than guessing.
    """
    plan = ((state.get("compose") or {}).get("plan") or {})
    beats = plan.get("beats") or []
    ids: list[str] = []
    starts: list[float] = []
    durations: list[float] = []
    cumulative = 0.0
    for beat in beats:
        if not isinstance(beat, dict):
            continue
        label = beat.get("beat") or beat.get("name") or ""
        if not label:
            continue
        sid = scene_id_for(label)
        duration = float(beat.get("duration_s") or 0.0)
        ids.append(sid)
        starts.append(cumulative)
        durations.append(duration)
        cumulative += duration
    return ids, starts, durations


def _render_ctx(state: dict) -> dict:
    failure = _latest_cluster_failure(state) or {}
    compose = state.get("compose") or {}
    index_html_path = compose.get("index_html_path") or ""
    compositions_dir = ""
    if index_html_path:
        compositions_dir = str(Path(index_html_path).parent / "compositions")

    scene_ids, scene_starts, scene_durations = _scene_metadata(state)
    # Read scaffold dimensions from the first beat's record if present;
    # otherwise leave defaults. The brief mirrors these literally.
    bd_dims = ((state.get("compose") or {}).get("assemble") or {})
    data_width = bd_dims.get("data_width") or 1920
    data_height = bd_dims.get("data_height") or 1080

    return {
        "failed_gate": failure.get("gate") or "",
        "prior_violations": list(failure.get("violations") or []),
        "prior_iteration": int(failure.get("iteration") or 0),
        "index_html_path": index_html_path,
        "compositions_dir": compositions_dir,
        "design_md_path": compose.get("design_md_path") or "",
        "expanded_prompt_path": compose.get("expanded_prompt_path") or "",
        "catalog_summary": _catalog_summary(state),
        "scene_ids_json": json.dumps(scene_ids, ensure_ascii=False),
        "scene_starts_json": json.dumps(scene_starts),
        "scene_durations_json": json.dumps(scene_durations),
        "data_width": data_width,
        "data_height": data_height,
        "data_track_index": 1,
    }


def _build_node() -> LLMNode:
    return LLMNode(
        name="p4_redispatch_beat",
        requirements=NodeRequirements(tier="smart", needs_tools=True, backends=["claude"]),
        brief_template=_load_brief("p4_redispatch_beat"),
        output_schema=None,
        result_namespace="compose",
        result_key="redispatch",
        timeout_s=300,
        allowed_tools=["Read", "Write"],
        extra_render_ctx=_render_ctx,
    )


def p4_redispatch_beat_node(state, *, router: BackendRouter | None = None):
    failure = _latest_cluster_failure(state)
    if failure is None:
        return {
            "notices": [
                "p4_redispatch_beat: no failed cluster-gate record in state — "
                "nothing to retry; routing back to p4_assemble_index"
            ],
        }

    compose = state.get("compose") or {}
    index_html_path = compose.get("index_html_path")
    if not index_html_path or not Path(index_html_path).is_file():
        return {
            "errors": [{
                "node": "p4_redispatch_beat",
                "message": f"index.html missing at {index_html_path!r}; cannot identify beat owner",
                "timestamp": _now(),
            }],
            "notices": ["p4_redispatch_beat: index.html missing — see errors[]"],
        }

    scene_ids, _, _ = _scene_metadata(state)
    if not scene_ids:
        return {
            "notices": [
                "p4_redispatch_beat: compose.plan.beats empty — cannot rewrite a scene; "
                "routing back to p4_assemble_index (which will skip)"
            ],
        }

    return _build_node()(state, router=router)
