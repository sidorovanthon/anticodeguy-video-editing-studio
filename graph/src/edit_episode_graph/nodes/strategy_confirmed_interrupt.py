"""strategy_confirmed_interrupt — HITL approval between p3_strategy and p3_edl_select.

Restores canon HR 11 ("Strategy confirmation before execution. Never touch
the cut until the user has approved the plain-English plan.") which the
original v3 spec deferred. In Studio runs the user is in-the-loop by
design, so the natural way to enforce HR 11 is a graph-level interrupt.

Resume contract — two outcomes:
  - **Approve** — resume payload is True, "approved" / "approve" / "yes" /
    "ok" (case-insensitive), or a dict with `{"approved": True}`. The node
    sets `state.edit.strategy.approved = true` and downstream routing
    proceeds to `p3_edl_select`.
  - **Revise** — any other non-empty payload (a string with the requested
    correction, or a dict). The payload is appended to top-level
    `state.strategy_revisions`; the strategy is NOT marked approved. The
    routing sends control back to `p3_strategy`, which reads the revisions
    list via render_ctx and emits a refined strategy that re-enters this
    node for re-approval.

Cap: after 3 revisions on the same strategy chain the routing escalates
to `halt_llm_boundary` rather than looping forever. Operator can re-enter
with a fresh strategy via Studio update-state if they need a hard reset.

Idempotency: if the strategy is already approved (e.g. graph replay) the
node short-circuits without prompting again.
"""

from __future__ import annotations

from langgraph.types import interrupt

# Subset of strategy fields shown in the Studio approval payload. Keeping it
# small and scalar-only so Studio's diff/edit UI stays readable.
SUMMARY_KEYS = ("shape", "takes", "grade", "pacing", "length_estimate_s")

# Resume strings that count as approval. Case-insensitive. Anything else is
# treated as revision feedback.
APPROVAL_TOKENS = frozenset({"approved", "approve", "yes", "ok", "y"})


def _is_approval(decision: object) -> bool:
    if decision is True:
        return True
    if isinstance(decision, str):
        return decision.strip().lower() in APPROVAL_TOKENS
    if isinstance(decision, dict):
        # Allow {"approved": True} as the structured form; reject if the dict
        # looks like a revision (any non-trivial key set) so the loop runs.
        if decision.get("approved") is True and len(decision) == 1:
            return True
    return False


def _stringify_revision(decision: object) -> str:
    if isinstance(decision, str):
        return decision
    if decision is None:
        return ""
    return repr(decision)


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
            "Review the plain-English strategy.\n"
            "  - To APPROVE: resume with Command(resume='approved') "
            "(also accepts 'yes', 'ok', or {'approved': True}).\n"
            "  - To REVISE: resume with a string describing the correction "
            "(e.g. 'Target loudness = -14 LUFS'). The graph routes back to "
            "p3_strategy, which incorporates the feedback and re-prompts."
        ),
    })

    if _is_approval(decision):
        strategy.update({"approved": True, "approval_payload": decision})
        return {"edit": {"strategy": strategy}}

    # Revision intent — append to top-level append-only list and DO NOT mark
    # approved. Routing will send control back to p3_strategy which reads
    # strategy_revisions and emits a refined strategy for re-approval.
    revision = _stringify_revision(decision)
    return {
        "strategy_revisions": [revision] if revision else [],
        "notices": [
            f"strategy_confirmed_interrupt: revision queued — looping back to p3_strategy"
        ],
    }
