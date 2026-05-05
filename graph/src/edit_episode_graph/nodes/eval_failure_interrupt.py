"""eval_failure_interrupt — HITL escalation after 3 failed self-eval passes.

Mirrors `edl_failure_interrupt`: lives as a separate node so the gate's
state-update lands before the suspend, keeping `gate_results` observable
in Studio.

Routing via `route_after_eval_ok` directs here only when the iteration
counter has reached `Gate.max_iterations` (3).

Resume contract — two outcomes (HOM-130):
  - **Retry** — resume payload is empty (None, "", {}) or any non-abort
    value. Routing re-runs ``gate:eval_ok``. Note: the iteration counter
    is already at max by the time we land here, so a still-failing
    eval routes back to this interrupt rather than re-rendering — the
    operator must fix the underlying issue (re-render manually, edit
    ``state.edit.eval``) before resuming, or abort.
  - **Abort** — resume payload is one of the abort tokens (``"abort"``,
    ``"stop"``, ``"end"``, ``"give_up"``, ``"no"``, ``"n"`` — case-insensitive)
    or ``{"abort": True}``. Routing escalates to ``halt_llm_boundary`` so
    its notice surfaces in Studio.

The decision is persisted to ``state.edit.eval.failure_resume`` so routing
(a pure function over state) can read it without re-entering the node.
"""

from __future__ import annotations

from datetime import datetime, timezone

from langgraph.types import interrupt

from ..gates._base import latest_gate_result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def eval_failure_interrupt_node(state: dict) -> dict:
    record = latest_gate_result(state, "gate:eval_ok") or {}
    eval_report = (state.get("edit") or {}).get("eval") or {}
    decision = interrupt({
        "gate": "gate:eval_ok",
        "violations": record.get("violations") or [],
        "iteration": record.get("iteration"),
        "issues": eval_report.get("issues") or [],
        "hint": (
            "Self-eval failed 3x; inspect state.edit.eval + state.edit.render, "
            "fix the underlying issue, then resume.\n"
            "  - To RETRY (re-run gate:eval_ok): hit Submit with an empty resume "
            "box, or pass any non-abort value.\n"
            "  - To ABORT: pass 'abort' / 'stop' / 'give_up' / {'abort': True} "
            "— routes to halt_llm_boundary."
        ),
    })

    new_eval = dict(eval_report)
    new_eval["failure_resume"] = {
        "action": decision,
        "iteration_at_suspend": record.get("iteration"),
        "resumed_at": _now(),
    }
    return {"edit": {"eval": new_eval}}
