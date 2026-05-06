"""p3_review_interrupt — HITL pause between Phase 3 and Phase 4.

HOM-146: turns the prior Phase-3-terminal halt-to-END into a single linear
flow with a `langgraph.types.interrupt()` checkpoint. The operator has a
chance to review `episodes/<slug>/edit/final.mp4` before Phase 4 spends
LLM tokens; resuming continues into `glue_remap_transcript`.

Resume contract (mirrors `strategy_confirmed_interrupt` to keep the Studio
gesture uniform across HITL checkpoints):

  - **Approve** — empty payload (None / "" / {}), True, an approval token
    ("approved" / "approve" / "yes" / "ok" / "y", case-insensitive), or
    `{"approved": True}`. Marks `state.edit.review.phase3.approved = true`
    and downstream routing advances to `glue_remap_transcript`.
  - **Abort** — explicit abort token ("abort" / "stop" / "end" / "no" / "n")
    or `{"abort": True}`. Routes to `halt_llm_boundary` so the operator sees
    the explicit notice; the run can be re-entered later via Studio.
  - **Revise feedback** is intentionally NOT supported here — Phase 3
    revision happens at `strategy_confirmed_interrupt`/`edl_failure_interrupt`
    upstream. By the time we reach this node `final.mp4` is already rendered;
    revising means re-running Phase 3 deliberately, not a one-line note.

Idempotency: if `state.edit.review.phase3.approved` is already true (e.g.
graph replay after a Phase 4 failure), the node short-circuits without
re-prompting. Phase 4 nodes own their own caches; we don't need to re-pause
on the way back through.

Why this node exists at all (vs a direct edge to `glue_remap_transcript`):
the v6 user_review (HOM-78) gates on the *composed* preview. This node
gates on the *raw cut* — different artifact, different decision. Both stay.
"""

from __future__ import annotations

from langgraph.types import interrupt

# Subset of phase-3 fields surfaced in the Studio prompt. Kept scalar so the
# diff/edit UI stays readable.
SUMMARY_KEYS = ("n_segments", "delta_ms", "cached", "duration_s")

APPROVAL_TOKENS = frozenset({"approved", "approve", "yes", "ok", "y"})
ABORT_TOKENS = frozenset({"abort", "stop", "end", "no", "n", "give_up", "give up"})


def _is_approval(decision: object) -> bool:
    if decision is None or decision is True:
        return True
    if isinstance(decision, str):
        s = decision.strip().lower()
        return s == "" or s in APPROVAL_TOKENS
    if isinstance(decision, dict):
        if not decision:
            return True
        if decision.get("approved") is True and len(decision) == 1:
            return True
    return False


def _is_abort(decision: object) -> bool:
    if isinstance(decision, str):
        return decision.strip().lower() in ABORT_TOKENS
    if isinstance(decision, dict):
        return decision.get("abort") is True
    return False


def p3_review_interrupt_node(state: dict) -> dict:
    edit = state.get("edit") or {}
    phase3 = dict(((edit.get("review") or {}).get("phase3") or {}))

    if phase3.get("approved") or phase3.get("aborted"):
        return {}

    render = edit.get("render") or {}
    summary = {k: render.get(k) for k in SUMMARY_KEYS}

    decision = interrupt({
        "checkpoint": "phase3_review",
        "artifact": "edit/final.mp4",
        "render": summary,
        "hint": (
            "Review the raw cut at episodes/<slug>/edit/final.mp4 before "
            "Phase 4 spends LLM tokens.\n"
            "  - To APPROVE: hit Submit with an empty resume box (or pass "
            "'approved' / 'yes' / 'ok' / {'approved': True}). Continues to "
            "glue_remap_transcript → Phase 4.\n"
            "  - To ABORT: pass 'abort' / 'no' / {'abort': True}. Routes to "
            "halt_llm_boundary; you can re-enter later by re-Submitting on "
            "the same slug."
        ),
    })

    if _is_abort(decision):
        phase3.update({"aborted": True, "decision_payload": decision})
    else:
        # Default to approval: matches strategy_confirmed_interrupt convention
        # (empty Submit = "I'm fine with what I see"). Anything we don't
        # recognize as an explicit abort is treated as approval — wedging the
        # run on a typo would be worse than over-approving.
        phase3.update({"approved": True, "decision_payload": decision})
    # Return only the touched sub-dict so a future `review.phaseN` can't get
    # round-tripped through this node's delta. Mirrors the prior-art shape in
    # strategy_confirmed_interrupt.
    return {"edit": {"review": {"phase3": phase3}}}
