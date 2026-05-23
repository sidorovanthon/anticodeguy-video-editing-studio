"""Factory for class-1 deterministic nodes (subprocess wrappers).

Per spec §6.1. Used by `pickup` (v0) and will be reused in v1+ by
`isolate_audio`, `glue_remap_transcript`, `p4_scaffold`, etc.

The factory handles subprocess execution + uniform error reporting:

  - Runs `cmd_factory(state)` via subprocess with optional `cwd`.
  - On non-zero exit: returns a state delta appending one `GraphError` to
    `state["errors"]` (the `add` reducer in `state.py` makes this append-only).
    Both stdout and stderr are folded into the error message — many subprocess
    callers write diagnostics to one or the other inconsistently.
    The graph's conditional edge then routes to END.
  - On success: delegates stdout parsing to the caller-supplied `parser`,
    which returns the full state delta. Parser exceptions are caught and
    converted to the same `GraphError` channel, so a malformed subprocess
    payload cannot crash the graph.

Out of scope: subprocess infrastructure failures (missing executable, OS-level
spawn errors). `subprocess.run` may still raise `FileNotFoundError` /
`OSError`; surfacing those as graph errors is deferred — they indicate an
environment problem the user must fix, not a recoverable pipeline state.

Validation strategy: `parser` may use Pydantic for strict schema enforcement,
or plain `json.loads` while output contracts are still settling. The factory
itself is parser-agnostic — it just propagates whatever dict the parser returns.
"""

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def deterministic_node(
    *,
    name: str,
    cmd_factory: Callable[[dict], list[str]],
    parser: Callable[[str], dict],
    cwd: Path | None = None,
):
    """Wrap a subprocess invocation as a LangGraph node function.

    Args:
        name: node name, used in error records for traceability.
        cmd_factory: builds the argv list from current graph state.
        parser: turns stdout into a state-update dict.
        cwd: working directory for the subprocess (None = inherit).

    Returns:
        A `node(state) -> dict` callable suitable for `StateGraph.add_node`.
    """

    def _error(message: str) -> dict:
        return {"errors": [{"node": name, "message": message, "timestamp": _now()}]}

    def _execute(state) -> dict:
        result = subprocess.run(
            cmd_factory(state),
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        if result.returncode != 0:
            combined = "\n".join(s for s in (result.stderr, result.stdout) if s).strip()
            return _error(combined or f"exit code {result.returncode}, no output")
        try:
            return parser(result.stdout)
        except Exception as exc:
            return _error(f"parser error: {exc!r}\n--- stdout ---\n{result.stdout}")

    def node(state):
        # HOM-334 Phase A.5: step-debug interrupts cover every node in the
        # graph, deterministic factory included. ``wrap_deterministic_node``
        # is a pure pass-through when ``HOMESTUDIO_STEP_DEBUG`` is unset
        # (production default); only the operator's debug session pays the
        # cost of building the context dict and the wrap call. Local import
        # so module import remains cycle-free.
        from .._step_debug import is_enabled as _sd_enabled, wrap_deterministic_node

        if not _sd_enabled():
            return _execute(state)

        # Best-effort cmd preview for the pre-interrupt context. cmd_factory
        # may raise (e.g. missing episode_dir on isolate_audio); in that case
        # the cmd field stays None and _execute() will fail the same way it
        # would in production, surfacing the same RuntimeError. We do NOT
        # try/except _execute() — the step-debug wrapper should expose the
        # raw failure mode just like production.
        cmd_preview: str | None = None
        try:
            cmd_preview = " ".join(cmd_factory(state))
        except Exception:  # pragma: no cover - best effort only
            cmd_preview = None
        return wrap_deterministic_node(
            name,
            state=state,
            context={
                "slug": state.get("slug") if isinstance(state, dict) else None,
                "cmd": cmd_preview,
                "cwd": str(cwd) if cwd is not None else None,
            },
            inner=lambda: _execute(state),
        )

    return node
