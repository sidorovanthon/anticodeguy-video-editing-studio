"""p4_captions_layer — smart LLM node for tone-adaptive caption authoring (HOM-123).

Reads the Phase-3 transcript and `DESIGN.md` via the dispatched sub-agent's
`Read` tool, detects tone per HF canon `references/captions.md` §"Style
Detection", and returns a single self-contained captions HTML fragment in
the structured `CaptionsOutput.html` field. The orchestrator dual-writes
the body to `<hyperframes_dir>/captions.html` (HOM-235 — state-first
artifacts, Step B of HOM-230); the deterministic `p4_assemble_index` node
keeps reading from disk and inlining the fragment into the root
`index.html` (between the beat fragments and the v4 visibility shim)
until Step D2 of the HOM-230 epic strips the dual-write.

Per spec §6.3 + HOM-123 amendment:
  - tier=expensive (creative — `feedback_creative_nodes_flagship_tier`; canon
    is explicitly tone-adaptive across 4 dimensions × 5 tone profiles, with
    per-word emphasis decisions; cheap models hollow out brand-defining
    creative work).
  - allowed_tools = [Read]. `Write` removed in HOM-235 (state-first); the
    orchestrator handles the file write from the returned body.
  - briefs reference canon paths, never embed canon
    (`feedback_graph_decomposition_brief_references_canon`).
  - caching: `CACHE_POLICY` keyed on (slug, design_md_path,
    transcripts.final_json_path) per HOM-150 / spec §6. Replaces the prior
    poor-man's "skip if file exists" stub.

Captions are produced **exclusively** in Phase 4 — Phase 3 (HOM-75
amendment) emits no subtitles. Absence in the final composition is a bug
(see `gate:captions_track`, future ticket).
"""

from __future__ import annotations

from pathlib import Path

from langgraph.types import CachePolicy

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from ..schemas.p4_captions_layer import CaptionsOutput
from .._caching import make_llm_key
from .._paths import EpisodePaths
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. See HOM-132 spec §8.
# v2 (HOM-215): brief gained the caption-block exit-before-next-entrance
# imperative — the GROUPS table is now declared a non-overlapping ordered
# partition (`group[i].end ≤ group[i+1].start`). The canon-mandated
# `tl.set(...)` kill at group.end was already present but not sufficient
# on its own: if the GROUPS literal overlaps in time, the next entrance
# fires mid-exit and two captions paint together (HOM-210 fixture symptom
# at t=11s). The brief now mandates a clamp `group[i].end =
# min(group[i].end, group[i+1].start)` to enforce the partition.
# v3 (HOM-224): identity-only state writes — `compose.captions_block_path`
# top-level mirror dropped (downstream nodes derive via
# `EpisodePaths(slug).captions_block_path`); state.captions echo also
# dropped. Brief unchanged but cache key inputs derive via slug.
# v4 (HOM-235): state-first artifacts (Step B of HOM-230 epic). Brief no
# longer instructs the sub-agent to call `Write`; the full captions HTML
# fragment now comes back in the structured `CaptionsOutput.html` field
# and the orchestrator dual-writes the file to `captions_block_path` so
# today's `p4_assemble_index` disk-reader keeps working. `Write` dropped
# from `allowed_tools`. Output schema and brief both changed → cache
# invalidation.
# v5 (HOM-239 / Step D2 of HOM-230): dual-write to `captions_block_path`
# stripped. The body remains in `compose.captions.html`;
# `p4_materialize_disk_node` is the single deterministic writer. Node
# output contract changed → cache invalidation.
_CACHE_VERSION = 5


def _cache_key(state, *_args, **_kwargs):
    if not isinstance(state, dict):
        raise TypeError(
            f"p4_captions_layer cache key requires dict state, got {type(state).__name__}"
        )
    # See p4_design_system._cache_key for the empty-slug rationale.
    slug = state.get("slug") or "__unbound__"
    # HOM-224: derive paths via EpisodePaths(slug) — identity-only state.
    if slug and slug != "__unbound__":
        paths = EpisodePaths(slug)
        design_md_path: str | None = str(paths.design_md_path)
        final_json_path: str | None = str(paths.transcripts_final_json_path)
    else:
        design_md_path = None
        final_json_path = None
    return make_llm_key(
        node="p4_captions_layer",
        version=_CACHE_VERSION,
        slug=slug,
        files=[
            design_md_path,
            final_json_path,
        ],
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


def _captions_path(state: dict) -> Path | None:
    """HOM-224: derive via slug; legacy fallback for pre-pickup synthetic state."""
    slug = state.get("slug")
    if slug:
        return EpisodePaths(slug).captions_block_path
    episode_dir = state.get("episode_dir")
    if episode_dir:
        return Path(episode_dir) / "hyperframes" / "captions.html"
    return None


def _design_md_path(state: dict) -> str:
    """HOM-224: derive via slug; legacy fallback for pre-pickup synthetic state."""
    slug = state.get("slug")
    if slug:
        return str(EpisodePaths(slug).design_md_path)
    compose = state.get("compose") or {}
    path = compose.get("design_md_path")
    if path:
        return str(path)
    design = compose.get("design") or {}
    return str(design.get("design_md_path") or "")


def _transcript_path(state: dict) -> str:
    """HOM-224: derive via slug. Final wins over raw."""
    slug = state.get("slug")
    if not slug:
        return ""
    paths = EpisodePaths(slug)
    if paths.transcripts_final_json_path.exists():
        return str(paths.transcripts_final_json_path)
    if paths.transcripts_raw_json_path.exists():
        return str(paths.transcripts_raw_json_path)
    return ""


def _composition_dims(state: dict) -> tuple[int, int]:
    """Pull viewport from compose.plan.beats[0] if present, else defaults.

    Plan beats carry `data_width`/`data_height` (set by p4_dispatch_beats);
    falling back to 1920×1080 keeps the brief renderable for runs that
    skipped beats (the captions block will still be authored, just for the
    landscape default).
    """
    plan = (state.get("compose") or {}).get("plan") or {}
    beats = plan.get("beats") or []
    if beats and isinstance(beats[0], dict):
        w = beats[0].get("data_width") or beats[0].get("width") or 1920
        h = beats[0].get("data_height") or beats[0].get("height") or 1080
        try:
            return int(w), int(h)
        except (TypeError, ValueError):
            pass
    return 1920, 1080


def _composition_duration(state: dict) -> float:
    """Total composition duration (seconds) — sum of plan beat durations."""
    plan = (state.get("compose") or {}).get("plan") or {}
    beats = plan.get("beats") or []
    total = 0.0
    for b in beats:
        if not isinstance(b, dict):
            continue
        try:
            total += float(b.get("duration_s") or 0.0)
        except (TypeError, ValueError):
            continue
    return total


def _render_ctx(state: dict) -> dict:
    captions_path = _captions_path(state)
    transcript_path = _transcript_path(state)
    width, height = _composition_dims(state)
    return {
        "captions_block_path": str(captions_path) if captions_path else "",
        "design_md_path": _design_md_path(state),
        "transcript_json_path": transcript_path,
        "transcript_json_filename": Path(transcript_path).name if transcript_path else "",
        "data_width": width,
        "data_height": height,
        "data_duration_s": _composition_duration(state),
    }


def _build_node() -> LLMNode:
    # HOM-235 (Step B of HOM-230 state-first-artifacts): the sub-agent
    # returns the full captions HTML fragment in `CaptionsOutput.html`
    # rather than calling `Write`. The orchestrator dual-writes the body
    # to `<hyperframes_dir>/captions.html` below so today's
    # `p4_assemble_index` disk-reader keeps working until Step D2 strips
    # the dual-write. HOM-134's previous FS-source-of-truth rationale was
    # validated against the current model tier by the HOM-243 spike
    # (docs/spikes/hom-243-results.json — 6/6 paid attempts on `p4_beat`
    # returned 5–7 KB html cleanly, no SchemaValidationError, no
    # truncation, no retry loops) and reversed for the HOM-230 epic.
    return LLMNode(
        name="p4_captions_layer",
        requirements=NodeRequirements(tier="expensive", needs_tools=True, backends=["claude"]),
        brief_template=_load_brief("p4_captions_layer"),
        output_schema=CaptionsOutput,
        result_namespace="compose",
        result_key="captions",
        timeout_s=300,
        allowed_tools=["Read"],
        extra_render_ctx=_render_ctx,
    )


def p4_captions_layer_node(state, *, router: BackendRouter | None = None):
    captions_path = _captions_path(state)
    if captions_path is None:
        return {
            "compose": {
                "captions": {
                    "skipped": True,
                    "skip_reason": "no episode_dir / hyperframes_dir in state",
                },
            },
        }

    transcript_path = _transcript_path(state)
    if not transcript_path or not Path(transcript_path).is_file():
        return {
            "compose": {
                "captions": {
                    "skipped": True,
                    "skip_reason": (
                        "no transcript JSON available (transcripts.final_json_path / "
                        "raw_json_path missing) — Phase 3 must run first"
                    ),
                },
            },
        }

    design_md = _design_md_path(state)
    if not design_md or not Path(design_md).is_file():
        return {
            "compose": {
                "captions": {
                    "skipped": True,
                    "skip_reason": (
                        "no DESIGN.md available — upstream p4_design_system must run first"
                    ),
                },
            },
        }

    node = _build_node()
    update = node(state, router=router)

    # HOM-239 (Step D2 of HOM-230 state-first artifacts): dual-write to
    # `captions_block_path` stripped. The captions HTML body lives in
    # `compose.captions.html` (HOM-235); `p4_materialize_disk_node` is
    # the single deterministic writer downstream.
    return update
