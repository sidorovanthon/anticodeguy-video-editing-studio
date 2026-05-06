"""p3_strategy - smart LLM node for Phase 3 cut strategy."""

from __future__ import annotations

import json
from pathlib import Path

from langgraph.types import CachePolicy

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from .._caching import make_key, stable_fingerprint
from ..schemas.p3_strategy import Strategy
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. Spec §8 review checkpoint.
_CACHE_VERSION = 1


def _takes_packed_path(state: dict) -> Path:
    explicit = (state.get("transcripts") or {}).get("takes_packed_path")
    if explicit:
        return Path(explicit)
    return Path(state["episode_dir"]) / "edit" / "takes_packed.md"


def _takes_packed_path_for_key(state: dict) -> str | None:
    """Same resolution as :func:`_takes_packed_path` but tolerant of unbound state.

    LangGraph's `compiled.get_graph()` evaluates `key_func` against the
    state-channel default during introspection — `episode_dir` is `""`. The
    production helper raises `KeyError` in that case; for cache keys we want
    a stable "absent" fingerprint, so we emit ``None`` and rely on
    :func:`_caching.file_fingerprint` to map it to ``"absent"``.
    """
    explicit = (state.get("transcripts") or {}).get("takes_packed_path")
    if explicit:
        return str(explicit)
    if not state.get("episode_dir"):
        return None
    return str(Path(state["episode_dir"]) / "edit" / "takes_packed.md")


def _cache_key(state, *_args, **_kwargs):
    """Cache key for `p3_strategy`.

    Brief inputs the agent consumes:
    * `takes_packed_path` / `takes_packed_text` — file content drives output;
      content-hashed via `files=`.
    * `pre_scan_slips_json` — `state.edit.pre_scan.slips`, in-memory only;
      fingerprinted in `extras`.
    * `strategy_revisions_json` — operator revision feedback list, in-memory;
      fingerprinted in `extras`. The brief renders this verbatim under the
      "Operator revision feedback" block when non-empty.

    Spec §6 lists `[takes_packed_path, edit.pre_scan_path]`, but `pre_scan` is
    an in-memory result of `p3_pre_scan` (no `pre_scan_path` is written to
    disk), so it cannot be file-fingerprinted. Likewise `strategy_revisions`
    is in-memory feedback. Both move to `extras=` per the HOM-150 amendment
    pattern (creative nodes whose briefs render in-memory state verbatim).
    """
    if not isinstance(state, dict):
        raise TypeError(
            f"p3_strategy cache key requires dict state, got {type(state).__name__}"
        )
    slug = state.get("slug") or "__unbound__"
    pre_scan = (state.get("edit") or {}).get("pre_scan") or {}
    slips = pre_scan.get("slips") or []
    revisions = state.get("strategy_revisions") or []
    # `episode_dir` is rendered into the brief verbatim ("Episode dir:
    # `{{ episode_dir }}`"). Slug + takes_packed.md content already
    # namespace per-episode in practice, but include episode_dir in
    # extras for the "all brief-rendered inputs covered" invariant
    # (HOM-132.3 review).
    return make_key(
        node="p3_strategy",
        version=_CACHE_VERSION,
        slug=slug,
        files=[_takes_packed_path_for_key(state)],
        extras=(
            state.get("episode_dir") or "",
            stable_fingerprint(slips),
            stable_fingerprint(revisions),
        ),
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


def _pre_scan_slips(state: dict) -> list[dict]:
    pre_scan = (state.get("edit") or {}).get("pre_scan") or {}
    slips = pre_scan.get("slips") or []
    return slips if isinstance(slips, list) else []


def _render_ctx(state: dict) -> dict:
    takes = _takes_packed_path(state)
    revisions = state.get("strategy_revisions") or []
    return {
        "takes_packed_path": str(takes),
        "takes_packed_text": takes.read_text(encoding="utf-8"),
        "pre_scan_slips_json": json.dumps(_pre_scan_slips(state), ensure_ascii=False),
        "strategy_revisions": revisions,
        "strategy_revisions_json": json.dumps(revisions, ensure_ascii=False),
    }


def _build_node() -> LLMNode:
    return LLMNode(
        name="p3_strategy",
        requirements=NodeRequirements(tier="smart", needs_tools=False, backends=["claude"]),
        brief_template=_load_brief("p3_strategy"),
        output_schema=Strategy,
        result_namespace="edit",
        result_key="strategy",
        timeout_s=120,
        allowed_tools=[],
        extra_render_ctx=_render_ctx,
    )


def p3_strategy_node(state, *, router: BackendRouter | None = None):
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return {"edit": {"strategy": {"skipped": True, "skip_reason": "no episode_dir in state"}}}
    takes = _takes_packed_path(state)
    if not takes.exists():
        return {"edit": {"strategy": {"skipped": True, "skip_reason": f"takes_packed.md missing at {takes}"}}}
    node = _build_node()
    update = node(state, router=router)
    strategy = (update.get("edit") or {}).get("strategy") or {}
    if "skipped" not in strategy:
        strategy["source_path"] = str(takes)
        update.setdefault("edit", {})["strategy"] = strategy
    return update
