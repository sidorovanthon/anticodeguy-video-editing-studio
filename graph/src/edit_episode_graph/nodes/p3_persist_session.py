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

from ..backends._router import BackendRouter
from ..backends._types import NodeRequirements
from ..schemas.p3_persist_session import PersistSessionResult
from ._llm import LLMNode, _load_brief


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
        allowed_tools=["Read", "Edit", "Write"],
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

    node = _build_node()
    update = node(state, router=router)
    persist = (update.get("edit") or {}).get("persist") or {}
    if "skipped" not in persist and "raw_text" not in persist:
        persist.setdefault("persisted_at", str(_project_md_path(state)))
    update.setdefault("edit", {})["persist"] = persist
    return update
