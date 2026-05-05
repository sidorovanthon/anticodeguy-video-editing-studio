"""edl_failure_interrupt — HITL pause when gate:edl_ok rejects the EDL.

Lives as a separate node from the gate itself because LangGraph's
`interrupt()` raises `GraphInterrupt`; any state delta returned from the
same node before the raise is discarded. Splitting into gate (always
appends `gate_results`) → interrupt-node (suspends) keeps the violation
record observable in Studio.

Resume contract — two outcomes (HOM-130):
  - **Retry** — resume payload is empty (None, "", {}) or any non-abort
    value. The operator's expected gesture: edit ``state.edit.edl`` via
    Studio's update-state, then hit Submit. Routing re-runs ``gate:edl_ok``,
    which either passes (loop exits) or re-suspends here with a fresh
    iteration record.
  - **Abort** — resume payload is one of the abort tokens (``"abort"``,
    ``"stop"``, ``"end"``, ``"give_up"``, ``"no"``, ``"n"`` — case-insensitive)
    or ``{"abort": True}``. Routing escalates to ``halt_llm_boundary`` so its
    notice surfaces in Studio.

The decision is persisted to ``state.edit.edl.failure_resume`` so routing
(a pure function over state) can read it without re-entering the node.
"""

from __future__ import annotations

from datetime import datetime, timezone

from langgraph.types import interrupt

from ..gates._base import latest_gate_result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def edl_failure_interrupt_node(state: dict) -> dict:
    record = latest_gate_result(state, "gate:edl_ok") or {}
    decision = interrupt({
        "gate": "gate:edl_ok",
        "violations": record.get("violations") or [],
        "iteration": record.get("iteration"),
        "hint": (
            "Edit state.edit.edl, then resume.\n"
            "  - To RETRY (re-run gate:edl_ok): hit Submit with an empty resume "
            "box, or pass any non-abort value.\n"
            "  - To ABORT: pass 'abort' / 'stop' / 'give_up' / {'abort': True} "
            "— routes to halt_llm_boundary."
        ),
    })

    edl = dict((state.get("edit") or {}).get("edl") or {})
    edl["failure_resume"] = {
        "action": decision,
        "iteration_at_suspend": record.get("iteration"),
        "resumed_at": _now(),
    }
    return {"edit": {"edl": edl}}
