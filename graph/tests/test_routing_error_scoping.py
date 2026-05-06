"""HOM-158 — routers must distinguish 'predecessor just failed' from
'something failed earlier on this thread'.

Pre-HOM-158 every router started with `if state.get("errors"): return END`.
With LangGraph's `add` (append-only) reducer on `state["errors"]`, that
predicate meant "stop forever once anything has ever failed on this thread"
— and a TURN 2 dispatch on the same thread halted at the very first router
even after the operator addressed the underlying issue. The
`_predecessor_just_failed` helper scopes the check to the immediate
predecessor; LLM nodes raise on terminal failure (per the same ticket) so
their followups don't need any check at all.

The repro from HOM-158:
  TURN 1 errors at p4_design_system → state["errors"] gets one entry.
  TURN 2 starts, runs pickup cleanly. route_after_pickup must NOT END
  on the historical p4_design_system entry.
"""

from __future__ import annotations

from langgraph.graph import END

from edit_episode_graph.nodes._routing import (
    _predecessor_just_failed,
    route_after_assemble_index,
    route_after_pickup,
    route_after_preflight,
    route_after_remap,
    route_after_scaffold,
)


def test_predecessor_just_failed_helper_matches_latest_only():
    state = {
        "errors": [
            {"node": "preflight_canon", "message": "x", "timestamp": "t1"},
            {"node": "p4_design_system", "message": "y", "timestamp": "t2"},
        ]
    }
    # Only the LATEST entry is checked.
    assert _predecessor_just_failed(state, "p4_design_system") is True
    assert _predecessor_just_failed(state, "preflight_canon") is False
    # Multiple candidate predecessors → match if latest is one of them.
    assert _predecessor_just_failed(state, "p4_design_system", "preflight_canon") is True


def test_predecessor_just_failed_handles_empty_state():
    assert _predecessor_just_failed({}, "pickup") is False
    assert _predecessor_just_failed({"errors": []}, "pickup") is False


def test_route_after_pickup_proceeds_with_historical_llm_origin_error(tmp_path):
    """Repro from HOM-158: TURN 1 fails at p4_design_system, TURN 2 starts
    with that historical entry still in state. pickup runs cleanly; routing
    must advance to phase 2 (isolate_audio) instead of halting at END.
    """
    state = {
        "episode_dir": str(tmp_path),
        "pickup": {"resumed": True, "idle": False},
        "errors": [
            {"node": "p4_design_system", "message": "BackendTimeout",
             "timestamp": "turn-1"},
        ],
    }
    # No raw video on disk → pickup wouldn't have succeeded in real life, but
    # `route_after_pickup` is a pure function over state and the tag check is
    # conservative — falls through to isolate_audio when no raw is found.
    assert route_after_pickup(state) == "isolate_audio"


def test_route_after_pickup_still_ends_when_pickup_just_failed(tmp_path):
    """The scoped check must still END when the IMMEDIATE predecessor
    failed (deterministic origin) — i.e. don't break the original intent.
    """
    state = {
        "episode_dir": str(tmp_path),
        "errors": [
            {"node": "p4_design_system", "message": "old", "timestamp": "turn-1"},
            {"node": "pickup", "message": "missing slug", "timestamp": "turn-2"},
        ],
    }
    assert route_after_pickup(state) == END


def test_route_after_preflight_proceeds_with_historical_unrelated_error(tmp_path):
    """An unrelated historical error must not block preflight routing."""
    state = {
        "episode_dir": str(tmp_path),
        "errors": [{"node": "p3_strategy", "message": "old", "timestamp": "turn-1"}],
    }
    # No artifacts → falls through to inventory.
    assert route_after_preflight(state) == "p3_inventory"


def test_route_after_remap_proceeds_with_historical_llm_error(tmp_path):
    """glue_remap_transcript predecessor — historical LLM error doesn't block."""
    state = {
        "episode_dir": str(tmp_path),
        "errors": [{"node": "p3_persist_session", "message": "old", "timestamp": "old"}],
    }
    # No hyperframes/index.html → routes to p4_scaffold.
    assert route_after_remap(state) == "p4_scaffold"


def test_route_after_scaffold_still_ends_when_scaffold_just_failed():
    """Scoped check on the scaffold (deterministic) predecessor — preserves
    the original 'predecessor just failed → END' contract.
    """
    state = {
        "errors": [{"node": "p4_scaffold", "message": "npx fail", "timestamp": "now"}],
    }
    assert route_after_scaffold(state) == END


def test_route_after_assemble_index_proceeds_with_historical_llm_error():
    """A historical LLM-origin error from earlier in Phase 4 must not block
    the gate cluster entry once assemble succeeds.
    """
    state = {
        "errors": [{"node": "p4_beat", "message": "old", "timestamp": "old"}],
        "compose": {"assemble": {"assembled_at": "/tmp/index.html"}},
    }
    assert route_after_assemble_index(state) == "gate_lint"
