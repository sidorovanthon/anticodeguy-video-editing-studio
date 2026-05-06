"""p3_edl_select — smart LLM node that produces the canonical EDL.

Implements canon §"Editor sub-agent brief" via a brief that REFERENCES the
canon path rather than embedding it (per
`feedback_graph_decomposition_brief_references_canon`). The dispatched
sub-agent reads canon at call time using the `Read` tool.

Phase 3 orchestrator policy: animations and subtitles live in Phase 4. The
brief mandates `overlays: []`; the schema forbids any `subtitles` field. The
deterministic `gate:edl_ok` validates word-boundary cuts (HR 6), padding (HR
7), and pacing on top of the schema check.
"""

from __future__ import annotations

import json
from pathlib import Path

from langgraph.types import CachePolicy

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from .._caching import make_key, stable_fingerprint, strategy_fingerprint
from ..gates._base import gate_retry_context
from ..schemas.p3_edl_select import EDL
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. Spec §8 review checkpoint.
# v2 (HOM-154): brief gained explicit HR 7 both-sides clarification.
_CACHE_VERSION = 2


def _takes_packed_path(state: dict) -> Path:
    explicit = (state.get("transcripts") or {}).get("takes_packed_path")
    if explicit:
        return Path(explicit)
    return Path(state["episode_dir"]) / "edit" / "takes_packed.md"


def _takes_packed_path_for_key(state: dict) -> str | None:
    explicit = (state.get("transcripts") or {}).get("takes_packed_path")
    if explicit:
        return str(explicit)
    if not state.get("episode_dir"):
        return None
    return str(Path(state["episode_dir"]) / "edit" / "takes_packed.md")


def _cache_key(state, *_args, **_kwargs):
    """Cache key for `p3_edl_select`.

    Brief inputs the agent consumes:
    * `takes_packed_path` (Read tool), `transcript_paths_json` (each Read).
      All are file inputs → `files=` content-hashes them.
    * `pre_scan_slips_json` — `state.edit.pre_scan.slips`, in-memory.
    * `strategy_json` — `state.edit.strategy` (modulo skip flags), in-memory.
    * `prior_violations` / `prior_iteration` — retry feedback from
      `gate_retry_context`, in-memory; without it, retry-after-gate-fail
      would cache-hit and short-circuit the retry-with-feedback loop.

    Spec §6 row says `[takes_packed.md, edit.strategy_path]`. There is no
    `strategy_path` on disk — strategy is in-memory state — and the brief
    actually consumes both transcript files plus the pre-scan slips and
    retry feedback. This implementation keeps the spec's intent
    (output-determining content goes in the key) while reflecting the
    actual brief inputs; spec §6 row will be amended with this PR.
    """
    if not isinstance(state, dict):
        raise TypeError(
            f"p3_edl_select cache key requires dict state, got {type(state).__name__}"
        )
    slug = state.get("slug") or "__unbound__"
    pre_scan = (state.get("edit") or {}).get("pre_scan") or {}
    slips = pre_scan.get("slips") or []
    strategy = (state.get("edit") or {}).get("strategy") or {}
    files: list[str | None] = [_takes_packed_path_for_key(state)]
    # `_transcript_paths` falls back to globbing `<episode_dir>/edit/transcripts/`
    # — under introspection (no `episode_dir`), only state-provided paths are
    # safe; suppress the glob path. Using inline lookups keeps the cache key
    # function tolerant of unbound state without forking the production helper.
    inv = (state.get("edit") or {}).get("inventory") or {}
    transcripts = state.get("transcripts") or {}
    if inv.get("transcript_json_paths"):
        files.extend(list(inv["transcript_json_paths"]))
    elif transcripts.get("raw_json_paths"):
        files.extend(list(transcripts["raw_json_paths"]))
    retry = gate_retry_context(state, "gate:edl_ok")
    return make_key(
        node="p3_edl_select",
        version=_CACHE_VERSION,
        slug=slug,
        files=files,
        extras=(
            stable_fingerprint(slips),
            strategy_fingerprint(strategy),
            stable_fingerprint(retry.get("prior_violations") or []),
            int(retry.get("prior_iteration") or 0),
        ),
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


def _transcript_paths(state: dict) -> list[str]:
    inv = (state.get("edit") or {}).get("inventory") or {}
    paths = inv.get("transcript_json_paths")
    if paths:
        return list(paths)
    transcripts = state.get("transcripts") or {}
    if transcripts.get("raw_json_paths"):
        return list(transcripts["raw_json_paths"])
    edit_dir = Path(state["episode_dir"]) / "edit" / "transcripts"
    return sorted(str(p) for p in edit_dir.glob("*.json")) if edit_dir.is_dir() else []


def _pre_scan_slips(state: dict) -> list[dict]:
    pre_scan = (state.get("edit") or {}).get("pre_scan") or {}
    slips = pre_scan.get("slips") or []
    return slips if isinstance(slips, list) else []


def _strategy(state: dict) -> dict:
    strat = (state.get("edit") or {}).get("strategy") or {}
    return {k: v for k, v in strat.items() if k not in {"skipped", "skip_reason", "source_path"}}


def _render_ctx(state: dict) -> dict:
    ctx = {
        "takes_packed_path": str(_takes_packed_path(state)),
        "transcript_paths_json": json.dumps(_transcript_paths(state), ensure_ascii=False),
        "pre_scan_slips_json": json.dumps(_pre_scan_slips(state), ensure_ascii=False),
        "strategy_json": json.dumps(_strategy(state), ensure_ascii=False),
    }
    # HOM-147: render the prior-violations feedback block on retry attempts.
    # Iteration 1 (no prior failure) → macro emits empty string; brief is
    # byte-identical to pre-HOM-147 output.
    ctx.update(gate_retry_context(state, "gate:edl_ok"))
    return ctx


def _build_node() -> LLMNode:
    return LLMNode(
        name="p3_edl_select",
        requirements=NodeRequirements(tier="smart", needs_tools=True, backends=["claude", "codex"]),
        brief_template=_load_brief("p3_edl_select"),
        output_schema=EDL,
        result_namespace="edit",
        result_key="edl",
        timeout_s=180,
        allowed_tools=["Read"],
        extra_render_ctx=_render_ctx,
    )


def p3_edl_select_node(state, *, router: BackendRouter | None = None):
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return {"edit": {"edl": {"skipped": True, "skip_reason": "no episode_dir in state"}}}
    takes = _takes_packed_path(state)
    if not takes.exists():
        return {"edit": {"edl": {"skipped": True, "skip_reason": f"takes_packed.md missing at {takes}"}}}
    node = _build_node()
    update = node(state, router=router)
    edl = (update.get("edit") or {}).get("edl") or {}
    if "skipped" not in edl and "raw_text" not in edl:
        edl["source_path"] = str(takes)
        # Persist EDL to disk so the deterministic render step (canon `render.py`)
        # can consume it. Without this, p3_render_segments fails with
        # "edl.json not found" — the LLM produces an in-state EDL but render.py
        # only reads from a path. Writing it here keeps p3_edl_select the sole
        # owner of EDL persistence (one writer per artifact).
        edl_path = Path(episode_dir) / "edit" / "edl.json"
        edl_path.parent.mkdir(parents=True, exist_ok=True)
        # Strip orchestrator-only fields before serializing — they confuse
        # canon helpers that don't expect them.
        on_disk = {k: v for k, v in edl.items() if k != "source_path"}
        edl_path.write_text(json.dumps(on_disk, indent=2, ensure_ascii=False), encoding="utf-8")
        edl["edl_path"] = str(edl_path)
    update.setdefault("edit", {})["edl"] = edl
    return update
