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

    def node(state):
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

    return node
