# graph/src/edit_episode_graph/nodes/_llm.py
"""LLMNode — minimal base for nodes that dispatch through BackendRouter.

Subclass or instantiate to build a callable that LangGraph treats as a node.
The base handles: brief rendering (Jinja2 string), router invocation,
telemetry append to `state["llm_runs"]`, error → `state["errors"]` + notice
on terminal failure (AllBackendsExhausted).

Tool-call observability: if a `dispatch_custom_event` is available
(LangGraph runtime), each `ToolCall` from the InvokeResult is re-emitted as
a `tool_call` custom event so Studio renders nested steps. Outside the
runtime (unit tests), the dispatch is a no-op.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from jinja2 import Template
from pydantic import BaseModel


_BRIEFS_DIR = Path(__file__).resolve().parent.parent / "briefs"


@lru_cache(maxsize=None)
def _load_brief(name: str) -> str:
    """Load `briefs/<name>.j2` once per process. `langgraph dev` reload re-imports
    the module, resetting the cache; tests mutating brief files should call
    `_load_brief.cache_clear()`.
    """
    return (_BRIEFS_DIR / f"{name}.j2").read_text(encoding="utf-8")

from ..backends._router import BackendRouter
from ..backends._types import (
    AllBackendsExhausted,
    InvokeResult,
    NodeRequirements,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dispatch_event(name: str, payload: dict) -> None:
    try:
        from langgraph.config import get_stream_writer  # type: ignore
        writer = get_stream_writer()
        writer({"event": name, "payload": payload})
    except Exception:
        return


@dataclass
class LLMNode:
    name: str
    requirements: NodeRequirements
    brief_template: str
    output_schema: type[BaseModel] | None
    result_namespace: str
    result_key: str
    timeout_s: int = 120
    allowed_tools: list[str] | None = None
    extra_render_ctx: Callable[[dict], dict] = field(default=lambda s: {})

    def __call__(self, state: dict, *, router: BackendRouter | None = None) -> dict:
        # In production, the router is bound in graph.py at compile time via
        # functools.partial; tests pass it explicitly.
        from ..config import load_default_config
        if router is None:
            from .._runtime import get_router   # late import; defined in next task
            router = get_router()
        ctx = {"slug": state.get("slug"), "episode_dir": state.get("episode_dir")}
        ctx.update(self.extra_render_ctx(state))
        node_cfg = load_default_config().resolve_node(self.name)
        # Per-node config overrides defaults baked into the LLMNode dataclass.
        effective_req = NodeRequirements(
            tier=node_cfg.tier or self.requirements.tier,
            needs_tools=self.requirements.needs_tools,
            backends=node_cfg.backend_preference or self.requirements.backends,
        )
        return self._invoke_with(
            router, state, render_ctx=ctx,
            requirements=effective_req,
            timeout_s=node_cfg.timeout_s or self.timeout_s,
            model_override=node_cfg.model,
        )

    def _invoke_with(
        self, router: BackendRouter, state: dict, render_ctx: dict,
        *, requirements: NodeRequirements | None = None,
        timeout_s: int | None = None,
        model_override: str | None = None,
    ) -> dict:
        req = requirements or self.requirements
        timeout_s = timeout_s or self.timeout_s
        task = Template(self.brief_template).render(**render_ctx)
        cwd = Path(state.get("episode_dir") or ".")
        try:
            result, attempts = router.invoke(
                req,
                task,
                cwd=cwd,
                timeout_s=timeout_s,
                output_schema=self.output_schema,
                allowed_tools=self.allowed_tools,
                model_override=model_override,
            )
        except AllBackendsExhausted as e:
            runs = [self._record(at) for at in e.attempts]
            return {
                "errors": [{"node": self.name, "message": str(e), "timestamp": _now()}],
                "llm_runs": runs,
                "notices": [f"{self.name}: all backends exhausted; see llm_runs"],
            }

        for tc in result.tool_calls:
            _safe_dispatch_event("tool_call", {
                "node": self.name, "tool": tc.name,
                "input": tc.input, "output_preview": tc.output_preview,
            })

        runs = [self._record(at) for at in attempts]
        update: dict[str, Any] = {"llm_runs": runs}
        if self.output_schema is not None and isinstance(result.structured, BaseModel):
            update[self.result_namespace] = {self.result_key: result.structured.model_dump()}
        else:
            update[self.result_namespace] = {self.result_key: {"raw_text": result.raw_text}}
        return update

    def _record(self, attempt: dict) -> dict:
        record = {
            "node": self.name,
            "backend": attempt.get("backend"),
            "model": attempt.get("model"),
            "tier": self.requirements.tier,
            "success": attempt.get("success", False),
            "reason": attempt.get("reason"),
            "wall_time_s": attempt.get("wall_time_s"),
            "tokens_in": attempt.get("tokens_in"),
            "tokens_out": attempt.get("tokens_out"),
            "timestamp": attempt.get("ts", _now()),
        }
        for k in ("exc_type", "returncode", "stderr_preview"):
            if k in attempt:
                record[k] = attempt[k]
        return record
