"""strategy_confirmed_interrupt — HITL approval between p3_strategy and p3_edl_select.

Restores canon HR 11 ("Strategy confirmation before execution. Never touch
the cut until the user has approved the plain-English plan.") which the
original v3 spec deferred. In Studio runs the user is in-the-loop by
design, so the natural way to enforce HR 11 is a graph-level interrupt.

Resume contract:
  - Studio shows the strategy summary in the interrupt payload.
  - Operator may edit `state.edit.strategy` via Studio's update-state
    before resuming, or pass an overriding payload via Command(resume=…).
  - Resume value is captured in `state.edit.strategy.approval_payload`
    for traceability; the node sets `approved: true` so re-entry on a
    later turn short-circuits without re-prompting.

Routing:
  - Strategy skipped upstream → bypass approval (nothing to confirm).
  - Strategy already approved → bypass (idempotent re-entry).
  - Otherwise → interrupt(); resumed run sets approved=true and proceeds.
"""

from __future__ import annotations

from langgraph.types import interrupt

# Subset of strategy fields shown in the Studio approval payload. Keeping it
# small and scalar-only so Studio's diff/edit UI stays readable.
SUMMARY_KEYS = ("shape", "takes", "grade", "pacing", "length_estimate_s")


def strategy_confirmed_interrupt_node(state: dict) -> dict:
    edit = state.get("edit") or {}
    strategy = dict(edit.get("strategy") or {})

    if strategy.get("skipped"):
        return {}
    if strategy.get("approved"):
        return {}

    summary = {k: strategy.get(k) for k in SUMMARY_KEYS}
    decision = interrupt({
        "checkpoint": "strategy_confirmed",
        "strategy": summary,
        "hint": (
            "Review the plain-English strategy. To approve, resume with "
            "Command(resume='approved'). To revise, edit state.edit.strategy "
            "via Studio first, then resume."
        ),
    })

    # Preserve every existing strategy field; mark approved.
    strategy.update({"approved": True, "approval_payload": decision})
    return {"edit": {"strategy": strategy}}
