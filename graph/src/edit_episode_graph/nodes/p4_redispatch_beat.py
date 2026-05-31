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

from .._canon_loader import load_canon_blocks
from .._paths import EpisodePaths
from .._scene_id import scene_id_for
from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from ..gates._base import latest_gate_result
from ..schemas.p4_beat import BeatOutput
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


def _design_md_body(state: dict) -> str:
    """HOM-265: read DESIGN.md body from state."""
    compose = state.get("compose") or {}
    design = compose.get("design") or {}
    body = design.get("design_md")
    return body if isinstance(body, str) else ""


def _expanded_prompt_body(state: dict) -> str:
    """HOM-265: read expanded-prompt.md body from state."""
    compose = state.get("compose") or {}
    expansion = compose.get("expansion") or {}
    body = expansion.get("expanded_prompt")
    return body if isinstance(body, str) else ""


def _index_html_body(state: dict) -> str:
    """HOM-265: read assembled root index.html body from state.

    Post-D2 (HOM-239) the assembled body lives at top-level
    `state["index_html"]` (see state.py docstring §"HOM-231 Step A").
    The disk file is written by `p4_materialize_disk_node` at chain end —
    while this node runs, the in-state body is the source of truth.
    """
    body = state.get("index_html")
    return body if isinstance(body, str) else ""


def _scene_bodies(state: dict) -> dict[str, str]:
    """HOM-265: per-scene HTML bodies from the top-level `scenes` channel.

    Populated by `p4_beat` Sends (HOM-234 / _scenes_merge reducer). On a
    redispatch loop the prior beat output(s) live here keyed by scene_id;
    the sub-agent reads from this dict instead of the per-scene
    `compositions/<scene_id>.html` files (which `p4_materialize_disk_node`
    writes at chain end, NOT while this redispatch runs).
    """
    scenes = state.get("scenes") or {}
    out: dict[str, str] = {}
    if isinstance(scenes, dict):
        for sid, entry in scenes.items():
            if isinstance(entry, dict):
                body = entry.get("html")
                if isinstance(body, str):
                    out[sid] = body
    return out


def _render_ctx(state: dict) -> dict:
    failure = _latest_cluster_failure(state) or {}
    compose = state.get("compose") or {}
    # HOM-224: derive index.html via slug; legacy state echo gone.
    slug = state.get("slug")
    if slug:
        ep = EpisodePaths(slug)
        index_html_path = str(ep.index_html_path)
    else:
        index_html_path = compose.get("index_html_path") or ""

    scene_ids, scene_starts, scene_durations = _scene_metadata(state)
    # Viewport dimensions: `p4_assemble_index` always runs upstream of any
    # cluster-gate failure, so by the time we land here `compose.assemble`
    # carries the previous lap's `data_width`/`data_height` — those reflect
    # the episode's actual viewport (parsed from the scaffolded root index.html
    # by `p4_dispatch_beats`). Defaults below cover the synthetic-state path
    # only (smokes / hand-injected state in Studio); they are not a code-path
    # the production graph traverses.
    bd_dims = ((state.get("compose") or {}).get("assemble") or {})
    data_width = bd_dims.get("data_width") or 1920
    data_height = bd_dims.get("data_height") or 1080

    return {
        "failed_gate": failure.get("gate") or "",
        "prior_violations": list(failure.get("violations") or []),
        "prior_iteration": int(failure.get("iteration") or 0),
        "index_html_path": index_html_path,
        # HOM-224: derive via slug; compose echo dropped.
        "design_md_path": str(EpisodePaths(slug).design_md_path) if slug else (compose.get("design_md_path") or ""),
        "expanded_prompt_path": str(EpisodePaths(slug).expanded_prompt_path) if slug else (compose.get("expanded_prompt_path") or ""),
        # HOM-265: inline body strings — sub-agent no longer Reads from disk.
        # `index_html_body` is the assembled root composition; `scene_bodies`
        # maps each scene_id to its prior-attempt fragment so the sub-agent
        # can read what the previous iteration produced without touching
        # `compositions/<scene_id>.html` on disk.
        "design_md_body": _design_md_body(state),
        "expanded_prompt_body": _expanded_prompt_body(state),
        "index_html_body": _index_html_body(state),
        "scene_bodies": _scene_bodies(state),
        "catalog_summary": _catalog_summary(state),
        "scene_ids_json": json.dumps(scene_ids, ensure_ascii=False),
        "scene_starts_json": json.dumps(scene_starts),
        "scene_durations_json": json.dumps(scene_durations),
        "data_width": data_width,
        "data_height": data_height,
        "data_track_index": 1,
        # HOM-377: verbatim canon blocks pulled live from the skill by anchor
        # (same load-bearing set as p4_beat). No cache fingerprint — this
        # retry node carries no CachePolicy (must re-run each iteration).
        "canon": load_canon_blocks("p4_redispatch_beat"),
    }


def _build_node() -> LLMNode:
    return LLMNode(
        name="p4_redispatch_beat",
        requirements=NodeRequirements(tier="expensive", needs_tools=True, backends=["claude"]),
        brief_template=_load_brief("p4_redispatch_beat"),
        # HOM-266: structured BeatOutput return — parity with p4_beat.
        # Sub-agent no longer Writes to disk; body flows back through state
        # via the `_scenes_merge` reducer and `p4_materialize_disk` writes
        # the file at chain end.
        output_schema=BeatOutput,
        result_namespace="compose",
        result_key="redispatch",
        timeout_s=300,
        allowed_tools=["Read"],
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

    # HOM-266: gate on the in-state assembled root composition body, not
    # the on-disk file. Post-HOM-239 (state-first artifacts) the disk
    # `index.html` is the scaffolded baseline written by `p4_scaffold` —
    # NOT the assembled root the sub-agent needs to read to identify
    # which scene owns the violations. The assembled body lives at
    # `state["compose"]["index_html"]` (populated by `p4_assemble_index`;
    # see `p4_transitions.py:136` for the same access pattern). If it's
    # missing, `p4_assemble_index` hasn't run yet — surface the misorder
    # rather than dispatching against an empty inline body.
    compose = state.get("compose") or {}
    index_html_body = compose.get("index_html")
    if not isinstance(index_html_body, str) or not index_html_body:
        return {
            "errors": [{
                "node": "p4_redispatch_beat",
                "message": (
                    "compose.index_html missing from state — "
                    "p4_assemble_index must run before redispatch; cannot "
                    "identify beat owner without the assembled root body"
                ),
                "timestamp": _now(),
            }],
            "notices": [
                "p4_redispatch_beat: compose.index_html missing — see errors[]"
            ],
        }

    scene_ids, _, _ = _scene_metadata(state)
    if not scene_ids:
        return {
            "notices": [
                "p4_redispatch_beat: compose.plan.beats empty — cannot rewrite a scene; "
                "routing back to p4_assemble_index (which will skip)"
            ],
        }

    # HOM-266: structured BeatOutput return. The LLMNode lands the parsed
    # body at `result["compose"]["redispatch"] = {"html": "..."}`; re-route
    # it through the top-level `scenes` channel keyed by scene_id so the
    # `_scenes_merge` reducer (state.py L91 — last-write-wins per key,
    # other scenes preserved) overlays the corrected fragment over the
    # prior attempt. `p4_assemble_index` re-runs downstream and re-inlines
    # the body into the root composition.
    #
    # Beat-owner identification: pre-HOM-266 the sub-agent Wrote to
    # `<scene_id>.html` and the filename told us which scene was rewritten.
    # Now the sub-agent picks one scene_id internally (per the brief) and
    # returns only the body — we can't unambiguously identify which scene
    # was rewritten from the body alone. Match by scanning the returned
    # body for the `id="scene-<sid>"` attribute. If zero markers match we
    # emit a hard error rather than silently overwriting the first scene
    # (HOM-266 review BLOCKER: silent misattribution is the same bug class
    # this PR was opened to fix; the gate retry-loop cannot detect a wrong
    # overwrite). The follow-up refactor — pre-resolving the failing
    # scene_id Python-side from gate `violations[]` — is tracked as a
    # separate ticket (see PR #150 review thread).
    result = _build_node()(state, router=router)
    raw = (result.get("compose") or {}).pop("redispatch", None) or {}
    body = raw.get("html") if isinstance(raw, dict) else None

    out: dict = {"llm_runs": result.get("llm_runs", [])}
    # Preserve any side-channel writes LLMNode emitted (e.g. notices,
    # errors). The reroute below replaces only the structured `compose`
    # return path; everything else flows through.
    for key in ("notices", "errors"):
        passthrough = result.get(key)
        if passthrough:
            out[key] = passthrough

    if not (isinstance(body, str) and body):
        # HOM-266 review: align empty-body with marker-miss — both are
        # un-attributable failure modes that the gate-retry loop must see
        # as a failed attempt (not a silent no-op).
        out.setdefault("errors", []).append({
            "node": "p4_redispatch_beat",
            "message": (
                "sub-agent returned empty BeatOutput.html — "
                "no scene merged into state['scenes']"
            ),
            "timestamp": _now(),
        })
        out.setdefault("notices", []).append(
            "p4_redispatch_beat: sub-agent returned empty BeatOutput.html — see errors[]"
        )
        return out

    matched: list[str] = []
    for sid in scene_ids:
        if f'id="scene-{sid}"' in body or f"id='scene-{sid}'" in body:
            matched.append(sid)

    if not matched:
        # HOM-266 review BLOCKER: do NOT silently default to scene_ids[0].
        # An un-attributable body is a failed attempt — push to errors[]
        # so the gate retry-loop counts it and `halt_llm_boundary` carries
        # the explicit notice after `max_attempts`.
        out.setdefault("errors", []).append({
            "node": "p4_redispatch_beat",
            "message": (
                "sub-agent returned un-attributable body — no recognisable "
                "id=\"scene-<sid>\" marker matching plan-order scene_ids "
                f"{scene_ids!r}"
            ),
            "timestamp": _now(),
        })
        out.setdefault("notices", []).append(
            "p4_redispatch_beat: un-attributable body — see errors[]; "
            "no scene merged into state['scenes']"
        )
        return out

    # Attribute to the first plan-order match. Multiple markers in one
    # body is suspicious (sub-agent should target exactly one scene) but
    # not necessarily wrong — the rewritten fragment may legitimately
    # reference other scenes in HTML comments or transition refs. Surface
    # a notice and proceed with the first match.
    picked_sid = matched[0]
    if len(matched) > 1:
        out.setdefault("notices", []).append(
            f"p4_redispatch_beat: returned body matches multiple plan-order "
            f"scene_ids {matched!r}; attributing to first match "
            f"scene_id={picked_sid!r} (sub-agent should target exactly one "
            f"scene — extra matches may be comments / transition refs)"
        )

    # Concern 2: `_scenes_merge` is a shallow reducer that REPLACES the
    # whole per-scene dict on a key collision. Today the per-scene entry
    # is single-field (`{"html": ...}`) so no regression, but preserve
    # siblings explicitly to defend against future per-scene metadata
    # (attempt count, model, beat_id) being wiped on a redispatch.
    # shallow reducer replaces whole per-scene dict — preserve siblings explicitly
    prev = (state.get("scenes") or {}).get(picked_sid) or {}
    out["scenes"] = {picked_sid: {**prev, "html": body}}
    return out
