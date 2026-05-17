"""p4_prompt_expansion — smart LLM node for canonical Step 2 prompt expansion.

Implements hyperframes SKILL.md §"Step 2: Prompt expansion" via a brief that
REFERENCES the canon path rather than embedding it (per
`feedback_graph_decomposition_brief_references_canon`). The dispatched
sub-agent reads canon at call time, consumes DESIGN.md from disk, and
returns a structured `ExpandedPrompt` with the full per-scene production
spec body in the `expanded_prompt` field; the orchestrator writes the file
to `.hyperframes/expanded-prompt.md` (HOM-233 — state-first artifacts,
Step B of HOM-230). Downstream disk-readers (`p4_plan`, `p4_beats`) keep
working off the dual-written file until Step D2 strips the dual-write.

Tier: smart. Canon `references/prompt-expansion.md` is explicit that "the
quality gap between a single-pass composition and a multi-scene-pipeline
composition comes from this step" — this is the highest-leverage creative
node in Phase 4 and is never cheap (per `feedback_creative_nodes_flagship_tier`).
"""

from __future__ import annotations

import json
from pathlib import Path

from langgraph.types import CachePolicy

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from .._caching import make_llm_key, stable_fingerprint
from .._paths import EpisodePaths
from ..schemas.p4_prompt_expansion import ExpandedPrompt
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. See HOM-132 spec §8.
# v2 (HOM-224): identity-only state writes — `compose.expanded_prompt_path`
# top-level mirror dropped; brief no longer renders `episode_dir`. Paths
# derived via `EpisodePaths(slug)` at use-sites.
# v3 (HOM-233): state-first artifacts (Step B of HOM-230 epic). Brief no
# longer instructs the sub-agent to call `Write`; the full expanded-prompt
# body now comes back in the structured `ExpandedPrompt.expanded_prompt`
# field and the orchestrator dual-writes the file to `expanded_prompt_path`
# so today's disk-readers (`p4_plan`, `p4_beats`) keep working. `Write`
# dropped from `allowed_tools`. Output schema and brief both changed →
# cache invalidation.
# v4 (HOM-239 / Step D2 of HOM-230): dual-write stripped. The expanded-
# prompt body remains in `compose.expansion.expanded_prompt`;
# `p4_materialize_disk_node` is the single deterministic writer. Node
# output contract changed (no more disk side-effect) → cache invalidation.
# v5 (HOM-265 / Step E partial of HOM-230): consumer-side gate switched
# from disk-presence (`Path(design_md_path).is_file()`) to state-body
# presence (`compose.design.design_md`). Brief migrated from
# "Read this path" to embedded body — DESIGN.md is inlined directly in
# the brief context so the sub-agent no longer calls `Read` on disk.
# Cache-key inputs (`files=[design_md_path, ...]`) intentionally
# unchanged in this PR — full Step E refactor deferred.
# v6 (HOM-240 / Step E of HOM-230): cache-key migration — `design_md_path`
# dropped from `files=` (the file is no longer on disk while this node
# runs post-HOM-239); replaced with `stable_fingerprint` of the in-state
# DESIGN.md body. `transcripts/final.json` stays in `files=` (Phase 3
# disk artifact, legitimate file-fingerprint).
# v7 (HOM-279): transcript body migrated from disk-read to state-read.
# Brief now inlines `transcript_json_body` (the JSON text) directly in
# the render context — the dispatched sub-agent no longer calls `Read`
# on the transcript file. Cache key swaps the transcript file
# fingerprint for an in-state `stable_fingerprint(transcript_body)`.
_CACHE_VERSION = 7


def _cache_key(state, *_args, **_kwargs):
    if not isinstance(state, dict):
        raise TypeError(
            f"p4_prompt_expansion cache key requires dict state, got {type(state).__name__}"
        )
    # See p4_design_system._cache_key for the empty-slug rationale (LangGraph
    # introspects `compiled.get_graph()` against the channel default).
    slug = state.get("slug") or "__unbound__"
    compose = state.get("compose") or {}
    style_request = compose.get("style_request") or ""
    design = compose.get("design") or {}
    design_md_body = design.get("design_md") or ""
    # HOM-279: transcript body fingerprint replaces final_json_path
    # file_fingerprint (the body is what the LLM consumes via the
    # inlined brief; the disk file remains authoritative on Phase 3
    # side).
    transcript_body = _transcript_body(state)
    return make_llm_key(
        node="p4_prompt_expansion",
        version=_CACHE_VERSION,
        slug=slug,
        files=[],
        extras=(
            stable_fingerprint(style_request),
            stable_fingerprint(design_md_body),
            stable_fingerprint(transcript_body),
        ),
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


def _expanded_prompt_path(state: dict) -> Path:
    # HOM-224: derive from slug; no state echo.
    slug = state.get("slug")
    if not slug:
        episode_dir = state.get("episode_dir")
        if episode_dir:
            return Path(episode_dir) / "hyperframes" / ".hyperframes" / "expanded-prompt.md"
        raise RuntimeError("p4_prompt_expansion: slug missing from state (pickup must run first)")
    return EpisodePaths(slug).expanded_prompt_path


def _strategy(state: dict) -> dict:
    strat = (state.get("edit") or {}).get("strategy") or {}
    return {k: v for k, v in strat.items() if k not in {"skipped", "skip_reason", "source_path"}}


def _edl_beats(state: dict) -> list[str]:
    edl = (state.get("edit") or {}).get("edl") or {}
    ranges = edl.get("ranges") or []
    seen: list[str] = []
    for r in ranges:
        beat = r.get("beat")
        if beat and beat not in seen:
            seen.append(beat)
    return seen


def _design_md_path(state: dict) -> str:
    """HOM-224: derive via slug; legacy fallback retained for pre-pickup states."""
    slug = state.get("slug")
    if slug:
        return str(EpisodePaths(slug).design_md_path)
    compose = state.get("compose") or {}
    path = compose.get("design_md_path")
    if path:
        return str(path)
    design = compose.get("design") or {}
    return str(design.get("design_md_path") or "")


def _design_md_body(state: dict) -> str:
    """HOM-265: read DESIGN.md body from state (post Step-D2 source of truth).

    The body lives at `compose.design.design_md` (set by `p4_design_system`
    in HOM-232 / Step B of HOM-230). Returns empty string when missing —
    the node body uses that as the skip gate, replacing the prior
    `Path(design_md_path).is_file()` disk-presence check.
    """
    compose = state.get("compose") or {}
    design = compose.get("design") or {}
    body = design.get("design_md")
    return body if isinstance(body, str) else ""


def _transcript_path(state: dict) -> str:
    """Resolve transcript JSON path via EpisodePaths(slug). Final wins over raw.

    HOM-279: when `transcripts.bodies.{final,raw}_path` is set in state
    (post-`glue_remap_transcript`), prefer that — keeps the brief's
    citation matching the body actually hoisted into state.
    """
    transcripts = state.get("transcripts") or {}
    bodies = transcripts.get("bodies") or {}
    final_path = bodies.get("final_path")
    if isinstance(final_path, str) and final_path:
        return final_path
    raw_path = bodies.get("raw_path")
    if isinstance(raw_path, str) and raw_path:
        return raw_path
    slug = state.get("slug")
    if not slug:
        return ""
    paths = EpisodePaths(slug)
    if paths.transcripts_final_json_path.exists():  # disk-io-allow: select on-disk transcript path to surface in brief; body itself comes from state
        return str(paths.transcripts_final_json_path)
    if paths.transcripts_raw_json_path.exists():  # disk-io-allow: fallback path selection; body itself comes from state
        return str(paths.transcripts_raw_json_path)
    return str(paths.transcripts_final_json_path)


def _transcript_body(state: dict) -> str:
    """HOM-279: read transcript JSON body from state.

    `glue_remap_transcript` hydrates `transcripts.bodies.{raw|final}` at
    the Phase 3 → Phase 4 boundary. Prefer `final` (EDL-remapped — beat
    timings line up with the EDL ranges this node expands); fall back
    to `raw` if `final` is missing. Empty string when neither is
    present — the node body skip-gates on that.
    """
    transcripts = state.get("transcripts") or {}
    bodies = transcripts.get("bodies") or {}
    final_body = bodies.get("final")
    if isinstance(final_body, str) and final_body:
        return final_body
    raw_body = bodies.get("raw")
    if isinstance(raw_body, str) and raw_body:
        return raw_body
    return ""


def _render_ctx(state: dict) -> dict:
    compose = state.get("compose") or {}
    return {
        "expanded_prompt_path": str(_expanded_prompt_path(state)),
        "design_md_path": _design_md_path(state),
        # HOM-265: inline the DESIGN.md body into the brief (sub-agent no
        # longer calls `Read` on the file). Step Step-E partial migration.
        "design_md_body": _design_md_body(state),
        "strategy_json": json.dumps(_strategy(state), ensure_ascii=False),
        "edl_beats_json": json.dumps(_edl_beats(state), ensure_ascii=False),
        "transcript_json_path": _transcript_path(state),
        # HOM-279: inline the transcript JSON body. Body source:
        # `state.transcripts.bodies` hoisted by `glue_remap_transcript`.
        "transcript_json_body": _transcript_body(state),
        "style_request_json": json.dumps(compose.get("style_request") or "", ensure_ascii=False),
    }


def _build_node() -> LLMNode:
    return LLMNode(
        name="p4_prompt_expansion",
        requirements=NodeRequirements(tier="expensive", needs_tools=True, backends=["claude"]),
        brief_template=_load_brief("p4_prompt_expansion"),
        output_schema=ExpandedPrompt,
        result_namespace="compose",
        result_key="expansion",
        timeout_s=300,
        allowed_tools=["Read"],
        extra_render_ctx=_render_ctx,
    )


def p4_prompt_expansion_node(state, *, router: BackendRouter | None = None):
    slug = state.get("slug")
    if not slug:
        return {"compose": {"expansion": {"skipped": True, "skip_reason": "no slug in state"}}}

    # HOM-265 (Step E partial of HOM-230): gate on STATE-BODY presence, not
    # disk-file presence. The post-D2 source of truth for DESIGN.md is
    # `state.compose.design.design_md` — `p4_materialize_disk_node` writes
    # the file at chain end, but it is NOT on disk while this node runs.
    if not _design_md_body(state):
        return {
            "compose": {
                "expansion": {
                    "skipped": True,
                    "skip_reason": (
                        "no DESIGN.md body in state — upstream p4_design_system "
                        "must run first"
                    ),
                },
            },
        }

    edl = (state.get("edit") or {}).get("edl") or {}
    if edl.get("skipped") or not edl.get("ranges"):
        return {
            "compose": {
                "expansion": {
                    "skipped": True,
                    "skip_reason": "no EDL beats to expand (upstream skip or empty ranges)",
                },
            },
        }

    # HOM-224: no longer mirror `compose.expanded_prompt_path` — identity-only
    # state. Downstream nodes derive via `EpisodePaths(slug).expanded_prompt_path`.
    # HOM-239 (Step D2 of HOM-230): dual-write to `expanded_prompt_path`
    # stripped. The body lives in `compose.expansion.expanded_prompt` and
    # `p4_materialize_disk_node` is the single deterministic writer.
    return _build_node()(state, router=router)
