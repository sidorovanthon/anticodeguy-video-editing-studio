"""p3_persist_session — cheap LLM node that runs canon §"Memory" persistence.

Appends a Session block to `<edit>/project.md` summarizing this run's
strategy, EDL choices, self-eval result, and any outstanding work. The
sub-agent reads `~/.claude/skills/video-use/SKILL.md` §"Memory — `project.md`"
to source the block format; we never embed the format in the brief.

Idempotency is monotonic-by-N rather than overwrite-skip: re-running adds
a new `## Session N+1 — <date>` block. The agent picks N by reading the
existing file and incrementing past the highest heading it finds.

We skip cleanly when upstream artifacts are missing (no episode_dir, no
EDL, no eval report). The graph wires this node downstream of `gate:eval_ok`
on the pass leg, so in normal flow all three inputs are present.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from langgraph.types import CachePolicy

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from .._caching import make_key, stable_fingerprint, strategy_fingerprint
from ..schemas.p3_persist_session import PersistSessionResult
from ._llm import LLMNode, _load_brief

# Bump on brief / schema / tool-list change. Spec §8 review checkpoint.
_CACHE_VERSION = 1


def _final_mp4_path_for_key(state: dict) -> str | None:
    render = (state.get("edit") or {}).get("render") or {}
    explicit = render.get("final_mp4")
    if explicit:
        return str(explicit)
    if not state.get("episode_dir"):
        return None
    return str(Path(state["episode_dir"]) / "edit" / "final.mp4")


def _edl_path_for_key(state: dict) -> str | None:
    edl = (state.get("edit") or {}).get("edl") or {}
    explicit = edl.get("edl_path")
    if explicit:
        return str(explicit)
    if not state.get("episode_dir"):
        return None
    return str(Path(state["episode_dir"]) / "edit" / "edl.json")


def _cache_key(state, *_args, **_kwargs):
    """Cache key for `p3_persist_session`.

    Brief renders `strategy_json`, `edl_json`, `eval_report_json` (all
    in-memory state — none are written to disk in a form that would let us
    file-fingerprint them; `edl.json` IS on disk but the brief renders the
    in-state dict including transient fields, so we hash it explicitly),
    plus `iteration` and `today`. All in-memory values move to `extras=`.

    `files=` keeps the spec's `[final_mp4_path, edl_path]` for upstream-
    invalidation parity with `p3_self_eval`, and deliberately does NOT
    include `project.md` itself — the node's first run mutates that file
    (appending Session N), so listing it would cause re-runs to always
    cache-miss, defeating idempotency.

    Spec §6 row will be amended in this PR with the in-memory extras and
    the `today` rationale (mirrors the HOM-150 amendment for
    `p4_persist_session`).
    """
    if not isinstance(state, dict):
        raise TypeError(
            f"p3_persist_session cache key requires dict state, got {type(state).__name__}"
        )
    slug = state.get("slug") or "__unbound__"
    edit = state.get("edit") or {}
    strategy = edit.get("strategy") or {}
    edl = edit.get("edl") or {}
    eval_report = edit.get("eval") or {}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return make_key(
        node="p3_persist_session",
        version=_CACHE_VERSION,
        slug=slug,
        files=[_final_mp4_path_for_key(state), _edl_path_for_key(state)],
        extras=(
            strategy_fingerprint(strategy),
            stable_fingerprint({k: v for k, v in edl.items() if k != "source_path"}),
            stable_fingerprint(eval_report),
            today,
        ),
    )


CACHE_POLICY = CachePolicy(key_func=_cache_key)


def _project_md_path(state: dict) -> Path:
    return Path(state["episode_dir"]) / "edit" / "project.md"


def _iteration_count(state: dict) -> int:
    """Count `gate:eval_ok` records — equals the render-eval iteration index."""
    count = 0
    for rec in state.get("gate_results") or []:
        if rec.get("gate") == "gate:eval_ok":
            count += 1
    return max(count, 1)


def _render_ctx(state: dict) -> dict:
    edit = state.get("edit") or {}
    strategy = edit.get("strategy") or {}
    edl = edit.get("edl") or {}
    eval_report = edit.get("eval") or {}
    return {
        "project_md_path": str(_project_md_path(state)),
        "strategy_json": json.dumps(strategy, ensure_ascii=False),
        "edl_json": json.dumps(edl, ensure_ascii=False),
        "eval_report_json": json.dumps(eval_report, ensure_ascii=False),
        "iteration": _iteration_count(state),
        "today": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }


def _build_node() -> LLMNode:
    return LLMNode(
        name="p3_persist_session",
        requirements=NodeRequirements(tier="cheap", needs_tools=True, backends=["claude", "codex"]),
        brief_template=_load_brief("p3_persist_session"),
        output_schema=PersistSessionResult,
        result_namespace="edit",
        result_key="persist",
        timeout_s=120,
        allowed_tools=["Read", "Write"],
        extra_render_ctx=_render_ctx,
    )


def p3_persist_session_node(state, *, router: BackendRouter | None = None):
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return {"edit": {"persist": {"skipped": True, "skip_reason": "no episode_dir in state"}}}
    edit = state.get("edit") or {}
    edl = edit.get("edl") or {}
    if edl.get("skipped") or not edl.get("ranges"):
        return {
            "edit": {
                "persist": {
                    "skipped": True,
                    "skip_reason": "no EDL to persist (upstream skip or empty ranges)",
                },
            },
        }
    eval_report = edit.get("eval") or {}
    if eval_report.get("skipped"):
        return {
            "edit": {
                "persist": {
                    "skipped": True,
                    "skip_reason": f"upstream eval skipped: {eval_report.get('skip_reason') or 'unknown'}",
                },
            },
        }
    # Defense-in-depth: in normal flow `route_after_eval_ok` only routes here
    # when `gate:eval_ok` passed, but direct invocation or a future routing
    # change could land us with a failed eval. Refuse to persist a Session
    # block that would advertise success the run did not earn.
    if eval_report.get("passed") is False:
        return {
            "edit": {
                "persist": {
                    "skipped": True,
                    "skip_reason": "eval did not pass — refusing to persist Session block",
                },
            },
        }

    node = _build_node()
    update = node(state, router=router)
    persist = (update.get("edit") or {}).get("persist") or {}
    if "skipped" not in persist and "raw_text" not in persist:
        persist.setdefault("persisted_at", str(_project_md_path(state)))
    update.setdefault("edit", {})["persist"] = persist
    return update
