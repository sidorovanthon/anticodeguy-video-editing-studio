"""p3_strategy - smart LLM node for Phase 3 cut strategy."""

from __future__ import annotations

import json
from pathlib import Path

from langgraph.types import CachePolicy

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from .._caching import brief_fingerprint, make_llm_key, stable_fingerprint
from .._canon_loader import canon_fingerprint, load_canon_blocks
from .._paths import EpisodePaths
from ..schemas.p3_strategy import Strategy
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. Spec §8 review checkpoint.
# v2 (HOM-160): node body now persists <edit>/strategy.json as a side effect.
# v3 (HOM-223): identity-only state writes — `strategy.source_path` and
# the brief's `episode_dir` extra removed; takes-packed resolved via
# `EpisodePaths(slug)` at use-site.
# v4 (HOM-377): canon sections (video-use SKILL.md §The process Step 4
#   "Propose strategy" + §Cut craft + §Color grade) are pulled VERBATIM from
#   the live skill at render time and inlined via `canon.*`, replacing the
#   "Read those sections" citations. `_cache_key` folds in
#   `canon_fingerprint("p3_strategy")` so an upstream canon edit invalidates.
# v5 (HOM-166): brief.fingerprint folded into cache key (state.brief resolution).
_CACHE_VERSION = 5


def _takes_packed_path(state: dict) -> Path:
    return EpisodePaths(state["slug"]).edit_dir / "takes_packed.md"


def _takes_packed_path_for_key(state: dict) -> str | None:
    """Slug-keyed cache lookup, tolerant of unbound state.

    LangGraph's `compiled.get_graph()` evaluates `key_func` against the
    state-channel default during introspection — `slug` is `""`. The
    production helper raises `KeyError` in that case; for cache keys we want
    a stable "absent" fingerprint, so we emit ``None`` and rely on
    :func:`_caching.file_fingerprint` to map it to ``"absent"``.
    """
    slug = state.get("slug")
    if not slug:
        return None
    return str(EpisodePaths(slug).edit_dir / "takes_packed.md")


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
    # HOM-223: `episode_dir` no longer in extras — was previously included so
    # the "all brief-rendered inputs covered" invariant held when the brief
    # rendered `Episode dir: {{ episode_dir }}` verbatim. The brief now uses
    # `slug` (logical identity); `slug` is already in the cache key. Removing
    # `episode_dir` from extras is what makes the cache key portable across
    # `HOMESTUDIO_PROJECT_ROOT` overrides.
    return make_llm_key(
        node="p3_strategy",
        version=_CACHE_VERSION,
        slug=slug,
        files=[_takes_packed_path_for_key(state)],
        extras=(
            stable_fingerprint(slips),
            stable_fingerprint(revisions),
            # HOM-377: verbatim canon blocks inlined into the brief.
            f"canon:{canon_fingerprint('p3_strategy')}",
            f"brief:{brief_fingerprint(state)}",
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
        # HOM-377: verbatim canon blocks pulled live from the skill by anchor.
        "canon": load_canon_blocks("p3_strategy"),
    }


def _build_node() -> LLMNode:
    return LLMNode(
        name="p3_strategy",
        requirements=NodeRequirements(tier="expensive", needs_tools=False, backends=["claude"]),
        brief_template=_load_brief("p3_strategy"),
        output_schema=Strategy,
        result_namespace="edit",
        result_key="strategy",
        timeout_s=120,
        allowed_tools=[],
        extra_render_ctx=_render_ctx,
    )


def _strategy_json_path(slug: str) -> Path:
    return EpisodePaths(slug).edit_dir / "strategy.json"


def p3_strategy_node(state, *, router: BackendRouter | None = None):
    slug = state.get("slug")
    if not slug:
        return {"edit": {"strategy": {"skipped": True, "skip_reason": "no slug in state"}}}
    takes = _takes_packed_path(state)
    if not takes.exists():
        return {"edit": {"strategy": {"skipped": True, "skip_reason": f"takes_packed.md missing at {takes}"}}}
    node = _build_node()
    update = node(state, router=router)
    strategy = (update.get("edit") or {}).get("strategy") or {}
    if "skipped" not in strategy:
        # HOM-160: persist a machine-readable snapshot so the phase-skip
        # path (route_after_preflight → rehydrate_skip_phase3 when final.mp4
        # exists) can reload strategy on a fresh thread without re-running
        # Phase 3. Strip transient keys the cache fingerprint already
        # excludes so the on-disk artifact equals the in-memory fingerprint
        # round-trip. HOM-223: `source_path` no longer written into state —
        # the brief's traceability comes from the slug + the canonical path.
        out = _strategy_json_path(slug)
        out.parent.mkdir(parents=True, exist_ok=True)
        persisted = {k: v for k, v in strategy.items()
                     if k not in {"skipped", "skip_reason", "approved", "approval_payload"}}
        out.write_text(json.dumps(persisted, ensure_ascii=False, indent=2), encoding="utf-8")
        update.setdefault("edit", {})["strategy"] = strategy
    return update
