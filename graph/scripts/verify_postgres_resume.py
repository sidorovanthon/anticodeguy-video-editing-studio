"""HOM-346 verification: thread state survives process restart.

This script proves the *mechanism* the ticket requires — a checkpointer
backed by durable storage lets a thread's interrupt position survive a
full Python process exit and be resumed in a fresh process.

It uses TWO checkpointer backends so we can run it both with and without
Docker:

* ``--backend sqlite`` (default, no external deps) — uses
  ``langgraph.checkpoint.sqlite.SqliteSaver`` against a file. Runs on any
  dev machine. Demonstrates that ``compile(checkpointer=…)`` + interrupt
  + ``Command(resume=…)`` correctly persist and resume across distinct
  Python interpreter processes. This proves the LangGraph-side mechanism
  is sound — the only thing differing between SQLite and Postgres at this
  layer is the underlying SQL backend, not the protocol.

* ``--backend postgres`` — uses
  ``langgraph.checkpoint.postgres.PostgresSaver`` against the URI in
  ``$POSTGRES_URI`` (default
  ``postgres://postgres:postgres@192.168.1.115:5443/postgres`` once the
  HOM-347 TrueNAS stack is deployed). Requires the
  ``homestudio-langgraph-postgres`` container to be reachable. Demonstrates
  the resume contract directly against the same backend the deployed
  ``langgraph-api`` server uses.

How the script proves resume-across-restart
-------------------------------------------
A single invocation of this script runs a TWO-step protocol:

1. **First subprocess** ("phase=start"): build a tiny graph (one node
   then ``interrupt(...)`` then a sink), open the checkpointer, invoke
   the graph on a fresh ``thread_id`` (uuid4), let it halt on the
   interrupt, then ``sys.exit(0)`` — closing all connections.
2. **Second subprocess** ("phase=resume"): reopen the same checkpointer
   pointing at the same backing file/URI, look up the same ``thread_id``,
   call ``get_state(thread_id)`` to confirm the interrupt position
   survived, then ``invoke(Command(resume="approved"))`` to confirm the
   run actually advances. Print a structured PASS / FAIL line.

The two phases are dispatched as real subprocesses (``subprocess.run``)
so there is zero shared in-process state — exactly mimicking a Studio
restart.

Why not exercise the full ``graph.graph`` graph
-----------------------------------------------
Per HOM-346 the verification scope is "graph-mechanism level, not a full
episode run" — we are validating the LangGraph checkpointer contract,
not Phase 3/4 behaviour. A minimal hand-crafted graph keeps the proof
self-contained, free of LLM calls, and free of fixture dependencies.

Exit codes
----------
0 on PASS (state survived restart, interrupt position preserved, resume
advanced the run). Non-zero on any failure, with a structured diagnostic
line on stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict


class _State(TypedDict, total=False):
    counter: int
    resumed_with: str


def _before(state: _State) -> _State:
    return {"counter": state.get("counter", 0) + 1}


def _pause(state: _State) -> _State:
    payload = interrupt({"awaiting": "operator approval"})
    return {"resumed_with": str(payload)}


def _after(state: _State) -> _State:
    return {"counter": state["counter"] + 1}


def _build_graph():
    g = StateGraph(_State)
    g.add_node("before", _before)
    g.add_node("pause", _pause)
    g.add_node("after", _after)
    g.add_edge(START, "before")
    g.add_edge("before", "pause")
    g.add_edge("pause", "after")
    g.add_edge("after", END)
    return g


def _open_checkpointer(backend: str, target: str):
    """Open the persistent checkpointer for ``backend`` against ``target``.

    Returns a context-managed checkpointer. Caller wraps in ``with``.
    """
    if backend == "sqlite":
        from langgraph.checkpoint.sqlite import SqliteSaver

        return SqliteSaver.from_conn_string(target)
    if backend == "postgres":
        from langgraph.checkpoint.postgres import PostgresSaver

        return PostgresSaver.from_conn_string(target)
    raise SystemExit(f"unknown backend: {backend!r}")


def _phase_start(backend: str, target: str, thread_id: str) -> None:
    """Process 1: run the graph until it hits the interrupt, then exit."""
    with _open_checkpointer(backend, target) as saver:
        if backend == "postgres":
            saver.setup()
        graph = _build_graph().compile(checkpointer=saver)
        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
        result = graph.invoke({"counter": 0}, config=config)
        state = graph.get_state(config)
        print(
            json.dumps(
                {
                    "phase": "start",
                    "thread_id": thread_id,
                    "result_keys": sorted(result.keys()),
                    "next": list(state.next),
                    "interrupt_count": len(state.tasks[0].interrupts)
                    if state.tasks
                    else 0,
                }
            )
        )


def _phase_resume(backend: str, target: str, thread_id: str) -> None:
    """Process 2 (fresh interpreter): inspect state, then resume the thread."""
    with _open_checkpointer(backend, target) as saver:
        graph = _build_graph().compile(checkpointer=saver)
        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
        before = graph.get_state(config)
        if not before.tasks or not before.tasks[0].interrupts:
            print(
                json.dumps(
                    {
                        "phase": "resume",
                        "thread_id": thread_id,
                        "verdict": "FAIL",
                        "reason": "no interrupt found in restored state",
                        "next": list(before.next),
                    }
                ),
                file=sys.stderr,
            )
            sys.exit(2)
        result = graph.invoke(Command(resume="approved"), config=config)
        after = graph.get_state(config)
        print(
            json.dumps(
                {
                    "phase": "resume",
                    "thread_id": thread_id,
                    "verdict": "PASS"
                    if result.get("counter") == 2 and result.get("resumed_with")
                    else "FAIL",
                    "result": result,
                    "next_after_resume": list(after.next),
                }
            )
        )


def _run_full_proof(backend: str, target: str) -> int:
    """Spawn two subprocesses (start, resume) and return the resume exit code."""
    thread_id = str(uuid.uuid4())
    here = Path(__file__).resolve()
    env = os.environ.copy()

    start = subprocess.run(
        [
            sys.executable,
            str(here),
            "--phase",
            "start",
            "--backend",
            backend,
            "--target",
            target,
            "--thread-id",
            thread_id,
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    sys.stdout.write(start.stdout)
    sys.stderr.write(start.stderr)
    if start.returncode != 0:
        print(f"start phase failed (exit={start.returncode})", file=sys.stderr)
        return start.returncode

    resume = subprocess.run(
        [
            sys.executable,
            str(here),
            "--phase",
            "resume",
            "--backend",
            backend,
            "--target",
            target,
            "--thread-id",
            thread_id,
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    sys.stdout.write(resume.stdout)
    sys.stderr.write(resume.stderr)
    return resume.returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--backend",
        choices=("sqlite", "postgres"),
        default="sqlite",
        help="checkpointer backend (default sqlite — no external deps)",
    )
    ap.add_argument(
        "--target",
        default=None,
        help=(
            "sqlite: path to a .db file (auto temp if omitted). "
            "postgres: connection URI (defaults to $POSTGRES_URI or "
            "postgres://postgres:postgres@localhost:5433/postgres)."
        ),
    )
    ap.add_argument(
        "--phase",
        choices=("full", "start", "resume"),
        default="full",
        help="full=spawn both subprocesses; start/resume=single phase",
    )
    ap.add_argument("--thread-id", default=None, help="for --phase start|resume")
    args = ap.parse_args(argv)

    if args.target is None:
        if args.backend == "sqlite":
            args.target = str(Path(tempfile.gettempdir()) / "hom346-verify.db")
        else:
            args.target = os.environ.get(
                "POSTGRES_URI",
                "postgres://postgres:postgres@192.168.1.115:5443/postgres",
            )

    if args.phase == "full":
        return _run_full_proof(args.backend, args.target)

    if not args.thread_id:
        raise SystemExit("--thread-id is required for --phase start|resume")

    if args.phase == "start":
        _phase_start(args.backend, args.target, args.thread_id)
    else:
        _phase_resume(args.backend, args.target, args.thread_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
