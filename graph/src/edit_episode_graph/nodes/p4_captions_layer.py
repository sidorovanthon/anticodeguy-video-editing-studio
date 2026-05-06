"""p4_captions_layer — smart LLM node for tone-adaptive caption authoring (HOM-123).

Reads the Phase-3 transcript and `DESIGN.md` via the dispatched sub-agent's
`Read` tool, detects tone per HF canon `references/captions.md` §"Style
Detection", and writes a single self-contained captions HTML fragment to
`<hyperframes_dir>/captions.html` via the `Write` tool. The deterministic
`p4_assemble_index` node reads `compose.captions_block_path` and inlines the
fragment into the root `index.html` (between the beat fragments and the v4
visibility shim).

Per spec §6.3 + HOM-123 amendment:
  - tier=smart (creative — `feedback_creative_nodes_flagship_tier`; canon
    is explicitly tone-adaptive across 4 dimensions × 5 tone profiles, with
    per-word emphasis decisions; cheap models hollow out brand-defining
    creative work).
  - allowed_tools = [Read, Write].
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
from .._caching import make_key
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. See HOM-132 spec §8.
_CACHE_VERSION = 1


def _cache_key(state, *_args, **_kwargs):
    if not isinstance(state, dict):
        raise TypeError(
            f"p4_captions_layer cache key requires dict state, got {type(state).__name__}"
        )
    # See p4_design_system._cache_key for the empty-slug rationale.
    slug = state.get("slug") or "__unbound__"
    compose = state.get("compose") or {}
    transcripts = state.get("transcripts") or {}
    return make_key(
        node="p4_captions_layer",
        version=_CACHE_VERSION,
        slug=slug,
        files=[
            compose.get("design_md_path"),
            transcripts.get("final_json_path"),
        ],
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


def _captions_path(state: dict) -> Path | None:
    compose = state.get("compose") or {}
    hyperframes_dir = compose.get("hyperframes_dir")
    if not hyperframes_dir:
        episode_dir = state.get("episode_dir")
        if not episode_dir:
            return None
        hyperframes_dir = str(Path(episode_dir) / "hyperframes")
    return Path(hyperframes_dir) / "captions.html"


def _design_md_path(state: dict) -> str:
    compose = state.get("compose") or {}
    path = compose.get("design_md_path")
    if path:
        return str(path)
    design = compose.get("design") or {}
    return str(design.get("design_md_path") or "")


def _transcript_path(state: dict) -> str:
    transcripts = state.get("transcripts") or {}
    return str(transcripts.get("final_json_path") or transcripts.get("raw_json_path") or "")


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
    # output_schema=None — same FS-source-of-truth pattern as p4_beat
    # (HOM-134). The output path is deterministic
    # (`<hyperframes_dir>/captions.html`), so requiring the sub-agent to
    # echo it back as JSON adds an extraction failure mode for zero
    # structural value: smoke runs hit `SchemaValidationError` because the
    # canon-shaped reply was prose ("Wrote captions.html (...)") rather
    # than the JSON the schema expected. The post-dispatch check below
    # promotes from disk instead.
    return LLMNode(
        name="p4_captions_layer",
        requirements=NodeRequirements(tier="smart", needs_tools=True, backends=["claude"]),
        brief_template=_load_brief("p4_captions_layer"),
        output_schema=None,
        result_namespace="compose",
        result_key="_captions_unused",
        timeout_s=300,
        allowed_tools=["Read", "Write"],
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

    captions_path.parent.mkdir(parents=True, exist_ok=True)

    node = _build_node()
    update = node(state, router=router)

    # `LLMNode` always writes `compose[result_key] = {"raw_text": ...}` even
    # when `output_schema is None`, leaving a noisy `_captions_unused` key in
    # every checkpoint. Drop it: the FS-source-of-truth model below carries
    # the only signal we want downstream nodes to see.
    compose_namespace = update.get("compose")
    if isinstance(compose_namespace, dict):
        compose_namespace.pop("_captions_unused", None)

    # FS source-of-truth promotion (mirrors p4_beat / p4_assemble_index).
    # If the file landed, stamp the deterministic path into compose.* —
    # `p4_assemble_index` reads it from there. If the dispatch errored or
    # the sub-agent never wrote, leave the path unset; assemble proceeds
    # without captions and surfaces the absence in the halt notice.
    try:
        wrote = captions_path.is_file() and captions_path.stat().st_size > 0
    except OSError:
        wrote = False
    if wrote:
        compose_update = update.setdefault("compose", {})
        compose_update["captions_block_path"] = str(captions_path)
        compose_update["captions"] = {
            "captions_block_path": str(captions_path),
            "cached": False,
        }
    return update
