"""HOM-162: RetryPolicy predicate matches AllBackendsExhausted on all-timeout.

Three layers of coverage, mirroring the ticket's DoD:

1. Pure unit on the predicate — synthesize `AllBackendsExhausted` with
   all-timeout attempts → predicate returns True.
2. Pure unit on the predicate — mixed timeout + auth attempts → predicate
   returns False (and a few other negative cases for robustness).
3. Integration smoke — compile a minimal `StateGraph` with a single node
   that raises `AllBackendsExhausted` once (all-timeout) then succeeds, wire
   the same `RetryPolicy` configured in `graph.py`, and assert pregel
   actually retried via call-count + final state. This is the cheap
   stand-in for "inject one transient timeout into Phase 3" — all the
   relevant mechanics (predicate signature, exception-matching, retry
   semantics) are exercised without spending real Anthropic credits.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from edit_episode_graph.backends._types import AllBackendsExhausted
from edit_episode_graph.graph import (
    _LLM_RETRY_POLICY,
    _retry_on_all_timeout_exhaustion,
)


def _attempt(reason: str, backend: str = "claude") -> dict:
    """Build a minimal attempt dict matching the router's telemetry shape."""
    return {
        "backend": backend,
        "success": False,
        "reason": reason,
        "wall_time_s": 0.5,
        "message": f"synthetic {reason}",
        "exc_type": "BackendTimeout" if reason == "timeout" else "BackendError",
        "ts": "2026-05-08T00:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# DoD 1 — all-timeout exhaustion → predicate returns True (retry).
# ---------------------------------------------------------------------------


def test_predicate_matches_all_timeout_exhaustion():
    exc = AllBackendsExhausted(
        attempts=[_attempt("timeout", "claude"), _attempt("timeout", "codex")]
    )
    assert _retry_on_all_timeout_exhaustion(exc) is True


def test_predicate_matches_single_timeout_exhaustion():
    exc = AllBackendsExhausted(attempts=[_attempt("timeout", "claude")])
    assert _retry_on_all_timeout_exhaustion(exc) is True


# ---------------------------------------------------------------------------
# DoD 2 — mixed reasons → predicate returns False (no retry).
# ---------------------------------------------------------------------------


def test_predicate_rejects_mixed_timeout_and_auth():
    exc = AllBackendsExhausted(
        attempts=[_attempt("timeout", "claude"), _attempt("auth", "codex")]
    )
    assert _retry_on_all_timeout_exhaustion(exc) is False


def test_predicate_rejects_all_auth():
    exc = AllBackendsExhausted(attempts=[_attempt("auth", "claude")])
    assert _retry_on_all_timeout_exhaustion(exc) is False


def test_predicate_rejects_schema_then_timeout():
    exc = AllBackendsExhausted(
        attempts=[_attempt("schema", "claude"), _attempt("timeout", "codex")]
    )
    assert _retry_on_all_timeout_exhaustion(exc) is False


def test_predicate_rejects_empty_attempts_list():
    # Defensive: no attempts recorded should not be treated as "all timeouts".
    exc = AllBackendsExhausted(attempts=[])
    assert _retry_on_all_timeout_exhaustion(exc) is False


def test_predicate_rejects_unrelated_exception_type():
    # Sibling BackendTimeout (or any non-wrapper) must not match — the whole
    # point of HOM-162 is that the wrapper is the only thing _llm.py raises.
    assert _retry_on_all_timeout_exhaustion(RuntimeError("boom")) is False
    assert _retry_on_all_timeout_exhaustion(ValueError("boom")) is False


# ---------------------------------------------------------------------------
# DoD 3 — pregel actually retries when the predicate matches.
# Build a minimal one-node graph using the SAME _LLM_RETRY_POLICY exported
# from graph.py, raise AllBackendsExhausted (all-timeout) on first invocation,
# return success on the second — assert pregel called the node twice and the
# graph finished cleanly.
# ---------------------------------------------------------------------------


class _MiniState(TypedDict, total=False):
    counter: int
    done: bool


def test_pregel_retries_node_on_all_timeout_exhaustion():
    calls: list[int] = []

    def flaky_node(state: _MiniState) -> dict:
        calls.append(1)
        if len(calls) == 1:
            raise AllBackendsExhausted(
                attempts=[
                    _attempt("timeout", "claude"),
                    _attempt("timeout", "codex"),
                ]
            )
        return {"done": True}

    g = StateGraph(_MiniState)
    g.add_node("flaky", flaky_node, retry_policy=_LLM_RETRY_POLICY)
    g.set_entry_point("flaky")
    g.add_edge("flaky", END)
    compiled = g.compile(checkpointer=InMemorySaver())

    final = compiled.invoke(
        {"counter": 0},
        config={"configurable": {"thread_id": "hom162-retry-test"}},
    )

    assert len(calls) == 2, (
        "predicate matched all-timeout exhaustion; pregel should have "
        f"retried the node exactly once (got {len(calls)} call(s))"
    )
    assert final.get("done") is True


def test_pregel_does_not_retry_on_mixed_reasons():
    # Mirror image of the test above: a mixed-reason exhaustion must NOT
    # trigger a retry — pregel should fail the run after a single call.
    calls: list[int] = []

    def flaky_node(state: _MiniState) -> dict:
        calls.append(1)
        raise AllBackendsExhausted(
            attempts=[
                _attempt("timeout", "claude"),
                _attempt("auth", "codex"),
            ]
        )

    g = StateGraph(_MiniState)
    g.add_node("flaky", flaky_node, retry_policy=_LLM_RETRY_POLICY)
    g.set_entry_point("flaky")
    g.add_edge("flaky", END)
    compiled = g.compile(checkpointer=InMemorySaver())

    raised: AllBackendsExhausted | None = None
    try:
        compiled.invoke(
            {"counter": 0},
            config={"configurable": {"thread_id": "hom162-no-retry-test"}},
        )
    except AllBackendsExhausted as e:
        raised = e

    assert raised is not None, "expected AllBackendsExhausted to propagate"
    assert len(calls) == 1, (
        "mixed-reason exhaustion must not retry; expected 1 call, "
        f"got {len(calls)}"
    )
