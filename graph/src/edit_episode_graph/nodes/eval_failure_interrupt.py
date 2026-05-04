"""eval_failure_interrupt — HITL escalation after 3 failed self-eval passes.

Mirrors `edl_failure_interrupt`: lives as a separate node so the gate's
state-update lands before the suspend, keeping `gate_results` observable
in Studio.

Routing via `route_after_eval_ok` directs here only when the iteration
counter has reached `Gate.max_iterations` (3). Resume contract: an
operator inspects `state["gate_results"]` and `state["edit"]["eval"]`,
decides whether to abort or feed corrected EDL/render, and resumes via
`Command(resume=...)`.
"""

from __future__ import annotations

from langgraph.types import interrupt

from ..gates._base import latest_gate_result


def eval_failure_interrupt_node(state: dict) -> dict:
    record = latest_gate_result(state, "gate:eval_ok") or {}
    eval_report = (state.get("edit") or {}).get("eval") or {}
    interrupt({
        "gate": "gate:eval_ok",
        "violations": record.get("violations") or [],
        "iteration": record.get("iteration"),
        "issues": eval_report.get("issues") or [],
        "hint": "self-eval failed 3x; inspect state.edit.eval + state.edit.render, "
                "then resume with Command(resume=...) once the underlying issue is fixed",
    })
    return {}
