"""p4_persist_session — cheap LLM node that runs canon §"Memory" persistence
for the Phase 4 (HF composition) leg of the pipeline.

Mirrors `p3_persist_session` (HOM-105) shape: dispatched sub-agent reads
the video-use §"Memory — `project.md`" canon, scans existing Session
headings, and appends a new `## Session N — <date>` block dated today.
Numbering is monotonic across the whole file — Phase 3 + Phase 4 share
the same N space.

Idempotency is monotonic-by-N (re-runs add a new block, not overwrite),
matching p3. The compose.session_persisted flag is set on success so
downstream callers can observe completion without reading the file.

Skip cleanly when upstream artifacts are missing:
  - no episode_dir,
  - no assembled index (compose.assemble.skipped or missing assembled_at).
The graph wires this node downstream of `p4_assemble_index` on the
success leg, so in normal flow these inputs are always present.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from langgraph.types import CachePolicy

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from .._caching import make_llm_key, stable_fingerprint
from .._paths import EpisodePaths
from ..schemas.p4_persist_session import PersistSessionOutput
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. See HOM-132 spec §8.
# v2 (HOM-224): identity-only state — `compose.persist.persisted_at` no
# longer holds a path; runtime overwrites with ISO 8601 timestamp (mirrors
# the p3 shape post-HOM-223). Brief asks for ISO timestamp; schema/field
# semantics shift from "where" → "when". `compose.index_html_path` cache
# input replaced with slug-derived `EpisodePaths(slug).index_html_path`
# (input file fingerprint stays semantically identical — same physical file).
# v3 (HOM-229): `today` is no longer a fingerprint extra — it derives from
# `assembled_at[:10]` (already in extras) inside `_render_ctx`. Cache key
# is now a pure function of upstream content; same-content re-runs cache-hit
# regardless of which calendar day they happen on. Session block reflects
# the day the composition was assembled, not the day persist ran.
# v4 (HOM-237): state-first artifacts (Step B6 of HOM-230 epic). Brief no
# longer instructs the sub-agent to compose+Write the merged file; the new
# Session block body now comes back in the structured
# `PersistSessionOutput.session_block` field and the orchestrator appends
# it (preceded by a blank line) to `<edit>/project.md` so today's
# downstream readers keep working. `Write` dropped from `allowed_tools`.
# Output schema and brief both changed → cache invalidation.
# v5 (HOM-239 / Step D2 of HOM-230): dual-write append to
# `<edit>/project.md` stripped. The session-block body lives in
# `compose.persist.session_block`; `p4_materialize_disk_node` is the
# single deterministic writer (substring-skip idempotent append). Node
# output contract changed → cache invalidation.
# v6 (HOM-265 / Step E partial of HOM-230): brief migrated from
# "Read project.md" to embedded body — the prior file content (when
# present from a previous materialization) is inlined directly in the
# brief context so the sub-agent no longer calls `Read` on it. On a
# fresh run the body is empty (no prior project.md). Cache-key inputs
# (`files=[index_html_path]`) unchanged in this PR — full Step E
# refactor deferred.
# v7 (HOM-240 / Step E of HOM-230): cache-key migration —
# `index_html_path` dropped from `files=` (file no longer on disk
# pre-materialize); replaced with `stable_fingerprint` of the in-state
# `compose.index_html` body. `files=` is now empty for this node.
# v8 (HOM-282): `_render_ctx.project_md_body` now reads from
# `state.session.project_md` instead of the disk file. The cache key
# extras do NOT change shape (the same body content was already
# implicit in `index_html` fingerprint via assembled-at timestamp) —
# bump because the brief input set changed semantics: a recording made
# against the old disk-read path may carry an out-of-band body the
# state channel does not reproduce on replay. Bump invalidates so the
# next replay re-asserts under the state-fed shape.
_CACHE_VERSION = 8


def _cache_key(state, *_args, **_kwargs):
    if not isinstance(state, dict):
        raise TypeError(
            f"p4_persist_session cache key requires dict state, got {type(state).__name__}"
        )
    # See p4_design_system._cache_key for the empty-slug rationale.
    slug = state.get("slug") or "__unbound__"
    compose = state.get("compose") or {}
    assemble = compose.get("assemble") or {}
    # HOM-240: index_html body fingerprint replaces index_html_path file
    # fingerprint. The assembled root composition body lives in
    # `compose.index_html` (HOM-236); the materializer writes the file at
    # chain end, NOT while this node runs. `assembled_at` ISO timestamp
    # stays in extras as a redundant upstream signal (any body change
    # implies a different timestamp, but keeping both is cheap and makes
    # the fingerprint robust to a body-identical re-assembly).
    assembled_at = assemble.get("assembled_at") or ""
    index_html_body = compose.get("index_html") or ""
    return make_llm_key(
        node="p4_persist_session",
        version=_CACHE_VERSION,
        slug=slug,
        files=[],
        extras=(
            assembled_at,
            stable_fingerprint(index_html_body),
        ),
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)

# Phase 4 gates whose records belong in the persisted Session block. Filtering
# narrows the brief input to relevant context (design / plan / static_guard,
# plus the future cluster from HOM-127); Phase 3 gates (edl_ok, eval_ok)
# already belong to that phase's own Session block.
_PHASE4_GATES = {
    "gate:design_ok",
    "gate:plan_ok",
    "gate:lint",
    "gate:validate",
    "gate:inspect",
    "gate:design_adherence",
    "gate:animation_map",
    "gate:snapshot",
    "gate:captions_track",
    "gate:static_guard",
}


def _project_md_path(state: dict) -> Path:
    """HOM-224: derive via slug; legacy fallback for synthetic-state tests."""
    slug = state.get("slug")
    if slug:
        return EpisodePaths(slug).edit_dir / "project.md"
    episode_dir = state.get("episode_dir")
    if episode_dir:
        return Path(episode_dir) / "edit" / "project.md"
    raise RuntimeError("p4_persist_session: slug missing from state")


def _phase4_gate_records(state: dict) -> list[dict]:
    return [
        rec for rec in (state.get("gate_results") or [])
        if rec.get("gate") in _PHASE4_GATES
    ]


def _beats_summary(compose: dict) -> list[dict]:
    """Compact one-entry-per-beat list for the brief.

    The full BeatState shape carries scene-fragment HTML and per-beat tool
    traces; the persist sub-agent only needs identifying metadata to write
    a meaningful Session block. We keep this narrow on purpose — the brief
    is task input, not a state dump.
    """
    plan = compose.get("plan") or {}
    plan_beats = plan.get("beats") or []
    out: list[dict] = []
    state_beats = compose.get("beats") or []
    by_id = {b.get("beat_id"): b for b in state_beats if isinstance(b, dict)}
    for pb in plan_beats:
        beat_id = pb.get("id") or pb.get("beat_id")
        sb = by_id.get(beat_id) or {}
        out.append({
            "beat_id": beat_id,
            "title": pb.get("title") or pb.get("name"),
            "duration_s": pb.get("duration_s"),
            "scene_path": sb.get("scene_path"),
            "status": sb.get("status") or ("planned" if not sb else "unknown"),
        })
    return out


def _render_ctx(state: dict) -> dict:
    compose = state.get("compose") or {}
    plan = compose.get("plan") or {}
    captions = compose.get("captions") or {}
    assemble = compose.get("assemble") or {}
    # HOM-224: derive paths via slug; legacy compose echoes dropped.
    slug = state.get("slug")
    if slug:
        ep = EpisodePaths(slug)
        design_md_path = str(ep.design_md_path)
        expanded_prompt_path = str(ep.expanded_prompt_path)
        index_html_path = str(ep.index_html_path)
        # Captions are optional; surface the deterministic path only when the
        # file is actually on disk. The brief otherwise gets the `""` it
        # already handled pre-HOM-224.
        # HOM-282: presence check reads from state (`compose.captions.html`,
        # HOM-235 channel) rather than `cap_path.is_file()`. The captions
        # block lives in state pre-materialize; the file lands on disk
        # downstream when `p4_materialize_disk_node` runs. Surface the
        # deterministic on-disk path only when the body was authored.
        captions_authored = bool((compose.get("captions") or {}).get("html"))
        captions_block_path = str(ep.captions_block_path) if captions_authored else ""
    else:
        design = compose.get("design") or {}
        expansion = compose.get("expansion") or {}
        design_md_path = design.get("design_md_path") or ""
        expanded_prompt_path = expansion.get("expanded_prompt_path") or ""
        index_html_path = assemble.get("index_html_path") or ""
        captions_block_path = (
            compose.get("captions_block_path")
            or captions.get("captions_block_path")
            or ""
        )
    # HOM-282: inline the prior project.md body from state, not disk.
    # `state.session.project_md` is populated by `p4_materialize_disk_node`
    # after its substring-skip append completes (the materializer is the
    # single writer; this producer reads its own prior output via state).
    # On a fresh thread with no prior materialize the channel is absent
    # — the sub-agent then knows N = 1. Pre-HOM-282 behaviour read the
    # file from disk; that path is gone now, completing the HOM-282
    # cutover from "producer reads own disk output" to "state is the
    # single channel".
    project_md_path = _project_md_path(state)
    project_md_body = (state.get("session") or {}).get("project_md") or ""
    return {
        "project_md_path": str(project_md_path),
        "project_md_body": project_md_body,
        "design_md_path": design_md_path,
        "expanded_prompt_path": expanded_prompt_path,
        "plan_json": json.dumps(plan, ensure_ascii=False),
        "beats_json": json.dumps(_beats_summary(compose), ensure_ascii=False),
        "captions_block_path": captions_block_path,
        "index_html_path": index_html_path,
        "gate_results_json": json.dumps(_phase4_gate_records(state), ensure_ascii=False),
        # HOM-229: derive `today` from `assembled_at` so the Session block
        # date is a function of upstream content, not wall-clock at persist
        # time. The fallback to `datetime.now()` only fires for legacy
        # synthetic-state tests where `assembled_at` is empty; the
        # production path always sets it (p4_persist_session_node skips
        # otherwise).
        "today": (
            (assemble.get("assembled_at") or "")[:10]
            or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        ),
    }


def _build_node() -> LLMNode:
    return LLMNode(
        name="p4_persist_session",
        requirements=NodeRequirements(tier="cheap", needs_tools=True, backends=["claude", "codex"]),
        brief_template=_load_brief("p4_persist_session"),
        output_schema=PersistSessionOutput,
        result_namespace="compose",
        result_key="persist",
        timeout_s=120,
        allowed_tools=["Read"],
        extra_render_ctx=_render_ctx,
    )


def p4_persist_session_node(state, *, router: BackendRouter | None = None):
    slug = state.get("slug")
    if not slug:
        return {"compose": {"persist": {"skipped": True, "skip_reason": "no slug in state"}}}
    compose = state.get("compose") or {}
    assemble = compose.get("assemble") or {}
    if assemble.get("skipped"):
        return {
            "compose": {
                "persist": {
                    "skipped": True,
                    "skip_reason": (
                        f"upstream assemble skipped: "
                        f"{assemble.get('skip_reason') or 'unknown'}"
                    ),
                },
            },
        }
    # HOM-224: `assemble.index_html_path` write removed; `assembled_at`
    # ISO timestamp is the sole success signal.
    if not assemble.get("assembled_at"):
        return {
            "compose": {
                "persist": {
                    "skipped": True,
                    "skip_reason": "no assembled index.html — nothing to persist",
                },
            },
        }

    node = _build_node()
    update = node(state, router=router)
    persist = (update.get("compose") or {}).get("persist") or {}
    update_compose = update.setdefault("compose", {})
    if "skipped" not in persist and "raw_text" not in persist:
        # HOM-239 (Step D2 of HOM-230 state-first artifacts): dual-write
        # append to `<edit>/project.md` stripped. The new Session block
        # body lives in `compose.persist.session_block`;
        # `p4_materialize_disk_node` performs the substring-skip
        # idempotent append downstream.

        # HOM-224: `persisted_at` was previously stringified absolute path
        # to project.md, abusing the `str | None` slot. Identity-only state:
        # store an ISO timestamp instead — same `str | None` shape, but
        # observation (when, not where), per the field's literal name. The
        # canonical path lives at `EpisodePaths(slug).edit_dir / "project.md"`.
        # OVERWRITES whatever the brief returned (the brief still echoes a
        # value per the schema; the node body re-shapes it).
        persist["persisted_at"] = datetime.now(timezone.utc).isoformat()
        update_compose["session_persisted"] = True
    update_compose["persist"] = persist
    return update
