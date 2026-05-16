"""p4_beat — smart LLM node for per-scene Pattern A authoring (HOM-134).

One Send per beat from `p4_dispatch_beats`. Each invocation reads the
upstream design system + expanded-prompt + canon docs via the `Read`
tool and returns the full Pattern A fragment in ``BeatOutput.html``
(HOM-234 — state-first artifacts, HOM-230 epic Step B3). The
orchestrator dual-writes the body to ``compositions/<scene_id>.html``
so today's disk-readers (`p4_assemble_index.py:588`) keep working
until HOM-230 Step D switches the consumer-side to read from
``state['scenes'][scene_id]['html']`` (top-level channel; see
``state.py::_scenes_merge`` + spec §10 Step B amendment). The
deterministic `p4_assemble_index` node fans in and inlines those
fragments into the root `index.html`.

Per spec `2026-05-04-hom-122-p4-beats-fan-out-design.md`:
  - tier=smart (creative — `feedback_creative_nodes_flagship_tier`)
  - allowed_tools = [Read]
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

from langgraph.types import CachePolicy

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from .._caching import make_llm_key, stable_fingerprint
from .._paths import EpisodePaths
from ..schemas.p4_beat import BeatOutput
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. See HOM-132 spec §8.
# v2 (HOM-165): brief gained "Explicit anti-patterns (DO NOT DO)" section
# (GSAP repeat math → Math.floor; caption exit kill-tween) + repeat example
# switched from Math.ceil-1 to Math.floor.
# v3 (HOM-201): brief gained "Palette discipline (strict ⊆)" hard-rule —
# beats may use ONLY hexes from `state.compose.design.palette[*].hex` (now
# pre-baked with gradient-stop / highlight derivatives upstream). Failing
# example pinned to the HOM-154 `linear-gradient(#2a221c, #1f1a16, #14100e)`
# regression that prompted the change.
# v4 (HOM-202): brief gained "Typography fallback discipline" hard-rule —
# `font-family` stacks may use ONLY families from
# `state.compose.design.typography[*].family`, generic CSS keywords, and the
# system-UI whitelist. Failing example pinned to the HOM-154
# `font-family: "Playfair Display", "Georgia", serif` regression that
# halted gate:design_adherence at iter 3.
# v5 (HOM-213): anti-pattern 2 (HOM-165 exit-pair) rewritten to make the
# generalisation explicit — applies to every scene element with a non-
# trivial entrance, not just captions. Adds the symptom citation (thesis
# main text stuck 8s past scene-end on canonical fixture), the
# "exit-pair lives in scene IIFE not root" clarification (root transitions
# fade the scene container, not per-element nodes), and the canonical
# fixture's payoff scene as positive control. Triggered by HOM-211 finding:
# hook + thesis missing the pair while payoff has it.
# v6 (HOM-213 review S1): cut verbatim canon recital from anti-pattern 2;
# brief now points at canon path + bullet name only (no quoted phrasing).
# Per CLAUDE.md §"Decomposition via brief-references-canon" — verbatim
# quotes still count as canon-fork risk if upstream wording shifts.
# v7 (HOM-224): cache_key + render ctx derive design.md / expanded-prompt.md
# via `EpisodePaths(slug)`; `compose.design_md_path` / `compose.expanded_prompt_path`
# state echoes dropped upstream.
# v8 (HOM-234): state-first artifacts (Step B3 of HOM-230 epic). Brief no
# longer instructs the sub-agent to call `Write`; the full scene fragment
# now comes back in `BeatOutput.html` and the orchestrator dual-writes the
# file to `scene_html_path` so today's disk-readers (`p4_assemble_index.py:588`)
# keep working. `Write` dropped from `allowed_tools`. Output schema and
# brief both changed → cache invalidation.
# v9 (HOM-239 / Step D2 of HOM-230): per-beat dual-write to
# `compositions/<scene_id>.html` stripped. The fragment body lives in
# `state["scenes"][scene_id]["html"]` (top-level channel via the
# `_scenes_merge` reducer) and `p4_materialize_disk_node` is the single
# deterministic writer. Node output contract changed → cache invalidation.
_CACHE_VERSION = 9


def _cache_key(state, *_args, **_kwargs):
    if not isinstance(state, dict):
        raise TypeError(
            f"p4_beat cache key requires dict state, got {type(state).__name__}"
        )
    # Per-Send invocation: each beat's `_beat_dispatch.scene_id` namespaces
    # the key. See p4_design_system._cache_key for the empty-slug rationale.
    slug = state.get("slug") or "__unbound__"
    bd = state.get("_beat_dispatch") or {}
    beat_id = bd.get("scene_id") or bd.get("beat_id") or "__unbound__"
    # `plan_beat_json` (concept / mood / energy / duration for THIS beat) is
    # rendered verbatim into the brief (line 12 of briefs/p4_beat.j2). It
    # lives in-memory on `_beat_dispatch.plan_beat`, NOT on disk —
    # transitive design_md / expanded_prompt invalidation does not catch a
    # plan-only change for the same beat_id (e.g. p4_plan re-runs and
    # produces different concept/mood for the same scene).
    plan_beat = bd.get("plan_beat") or {}
    # HOM-224: derive paths via EpisodePaths(slug) — identity-only state.
    if slug and slug != "__unbound__":
        paths = EpisodePaths(slug)
        design_md_path: str | None = str(paths.design_md_path)
        expanded_prompt_path: str | None = str(paths.expanded_prompt_path)
    else:
        design_md_path = None
        expanded_prompt_path = None
    return make_llm_key(
        node="p4_beat",
        version=_CACHE_VERSION,
        slug=slug,
        files=[
            design_md_path,
            expanded_prompt_path,
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
    # HOM-224: derive design.md / expanded-prompt.md via slug.
    slug = state.get("slug")
    if slug:
        paths = EpisodePaths(slug)
        design_md_path = str(paths.design_md_path)
        expanded_prompt_path = str(paths.expanded_prompt_path)
    else:
        design_md_path = compose.get("design_md_path") or ""
        expanded_prompt_path = compose.get("expanded_prompt_path") or ""
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
        "design_md_path": design_md_path,
        "expanded_prompt_path": expanded_prompt_path,
        "catalog_summary": _catalog_summary(state),
        "scene_html_path": bd.get("scene_html_path", ""),
    }


def _build_node() -> LLMNode:
    return LLMNode(
        name="p4_beat",
        requirements=NodeRequirements(tier="expensive", needs_tools=True, backends=["claude"]),
        brief_template=_load_brief("p4_beat"),
        output_schema=BeatOutput,
        result_namespace="compose",
        result_key="_beat_raw",
        timeout_s=300,
        allowed_tools=["Read"],
        extra_render_ctx=_render_ctx,
    )


def p4_beat_node(state, *, router: BackendRouter | None = None):
    bd = state.get("_beat_dispatch") or {}
    scene_id = bd.get("scene_id")

    result = _build_node()(state, router=router)

    # HOM-234 state-shape correction (kept post-HOM-239). LLMNode returns
    # the structured `BeatOutput` under `result["compose"]["_beat_raw"]`;
    # re-route it into the top-level `scenes[scene_id].html` channel
    # (promoted from `compose.scenes` by the HOM-234 pre-check — see
    # `tests/test_compose_scenes_fanout.py`: LangGraph reducers do NOT
    # walk nested Annotated channels, so `_scenes_merge` only fires when
    # `scenes` lives at the top level).
    # HOM-239 (Step D2 of HOM-230): per-beat dual-write to
    # `compositions/<scene_id>.html` stripped. The body lives in state
    # only; `p4_materialize_disk_node` writes the file from state.
    compose = result.get("compose") or {}
    raw = compose.pop("_beat_raw", None) or {}
    body = raw.get("html") if isinstance(raw, dict) else None

    out: dict = {"llm_runs": result.get("llm_runs", [])}
    if isinstance(body, str) and body and scene_id:
        out["scenes"] = {scene_id: {"html": body}}
    return out
