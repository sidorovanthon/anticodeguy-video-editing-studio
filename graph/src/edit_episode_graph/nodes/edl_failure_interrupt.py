"""edl_failure_interrupt — HITL pause when gate:edl_ok rejects the EDL.

Lives as a separate node from the gate itself because LangGraph's
`interrupt()` raises `GraphInterrupt`; any state delta returned from the
same node before the raise is discarded. Splitting into gate (always
appends `gate_results`) → interrupt-node (suspends) keeps the violation
record observable in Studio.

Resume contract: an operator inspects `state["gate_results"]`, edits
`state["edit"]["edl"]` via Studio's update-state, then resumes via
`Command(resume=...)`. The resumed run re-enters this node; if the gate
has been re-run and now passes, routing skips this node entirely.
"""

from __future__ import annotations

from langgraph.types import interrupt

from ..gates._base import latest_gate_result


def edl_failure_interrupt_node(state: dict) -> dict:
    record = latest_gate_result(state, "gate:edl_ok") or {}
    interrupt({
        "gate": "gate:edl_ok",
        "violations": record.get("violations") or [],
        "iteration": record.get("iteration"),
        "hint": "edit state.edit.edl, then resume with Command(resume=...)",
    })
    return {}
