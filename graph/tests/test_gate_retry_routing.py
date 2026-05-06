"""Unit tests for `route_after_gate_with_retry` (HOM-147).

The helper generalizes the iter<N retry pattern from `route_after_eval_ok`
across the whole gate family. These tests exercise the three branch
outcomes — pass, retry, exhausted-fail — plus the missing-record
defensive branch, all on a synthetic gate name so we don't depend on
any specific gate's domain logic.
"""

from __future__ import annotations

from edit_episode_graph.gates._base import gate_retry_context
from edit_episode_graph.nodes._routing import route_after_gate_with_retry


router = route_after_gate_with_retry(
    gate_name="gate:test",
    on_pass="next_node",
    retry_node="producer_node",
    fail_route="interrupt_node",
    max_iterations=3,
)


def _state(*, passed: bool, iteration: int, violations: list[str] | None = None) -> dict:
    return {
        "gate_results": [
            {
                "gate": "gate:test",
                "passed": passed,
                "iteration": iteration,
                "violations": violations or [],
                "timestamp": "now",
            }
        ]
    }


def test_pass_routes_to_on_pass():
    assert router(_state(passed=True, iteration=1)) == "next_node"


def test_first_fail_routes_to_retry_node():
    assert router(_state(passed=False, iteration=1)) == "producer_node"


def test_second_fail_still_retries():
    assert router(_state(passed=False, iteration=2)) == "producer_node"


def test_exhausted_fail_falls_through_to_fail_route():
    """At iteration == max_iterations the retry budget is spent — operator
    must take over via the interrupt rather than the helper looping."""
    assert router(_state(passed=False, iteration=3)) == "interrupt_node"


def test_missing_record_treated_as_fail_no_retry():
    """No record means the gate never ran; we don't burn a retry on phantom
    state — fall through to the fail route so the operator sees real state."""
    assert router({}) == "interrupt_node"


def test_max_iterations_is_configurable():
    custom = route_after_gate_with_retry(
        gate_name="gate:test",
        on_pass="ok",
        retry_node="retry",
        fail_route="halt",
        max_iterations=1,
    )
    assert custom(_state(passed=False, iteration=1)) == "halt"


def test_helper_only_inspects_named_gate():
    """Multiple gates in gate_results must not cross-contaminate — only the
    latest record matching `gate_name` should drive the decision."""
    state = {
        "gate_results": [
            {"gate": "gate:other", "passed": False, "iteration": 5,
             "violations": ["unrelated"], "timestamp": "x"},
            {"gate": "gate:test", "passed": True, "iteration": 1,
             "violations": [], "timestamp": "y"},
        ]
    }
    assert router(state) == "next_node"


# ---------- gate_retry_context (the producer-side render helper) ----------


def test_retry_context_empty_when_no_record():
    ctx = gate_retry_context({}, "gate:test")
    assert ctx == {"prior_violations": [], "prior_iteration": 0}


def test_retry_context_empty_on_pass():
    state = _state(passed=True, iteration=1, violations=[])
    ctx = gate_retry_context(state, "gate:test")
    assert ctx == {"prior_violations": [], "prior_iteration": 0}


def test_retry_context_carries_violations_on_fail():
    state = _state(passed=False, iteration=2, violations=["v1", "v2"])
    ctx = gate_retry_context(state, "gate:test")
    assert ctx == {"prior_violations": ["v1", "v2"], "prior_iteration": 2}


def test_retry_context_uses_latest_record_for_gate():
    """When a gate has multiple records, only the most recent drives the
    feedback block — older violations would mislead the producer."""
    state = {
        "gate_results": [
            {"gate": "gate:test", "passed": False, "iteration": 1,
             "violations": ["old"], "timestamp": "t1"},
            {"gate": "gate:test", "passed": False, "iteration": 2,
             "violations": ["fresh"], "timestamp": "t2"},
        ]
    }
    ctx = gate_retry_context(state, "gate:test")
    assert ctx["prior_violations"] == ["fresh"]
    assert ctx["prior_iteration"] == 2


# ---------- Brief macro renders the violations block ----------


def test_brief_renders_violations_block_on_retry():
    """End-to-end: producer brief + macro + retry context → rendered text
    contains the prior violations and an "address them" instruction."""
    from edit_episode_graph.nodes._llm import _BRIEF_ENV, _load_brief

    state = _state(passed=False, iteration=2,
                   violations=["range[0].start cuts inside word",
                               "overlays must be empty"])
    ctx = {
        "slug": "x", "episode_dir": "/tmp/x",
        "takes_packed_path": "/x", "transcript_paths_json": "[]",
        "pre_scan_slips_json": "[]", "strategy_json": "{}",
    }
    ctx.update(gate_retry_context(state, "gate:test"))
    # The macro is keyed by `gate:edl_ok` in the actual brief, but our
    # test state uses `gate:test`. Reproduce the keying via gate_retry_context
    # output above; the macro reads the splatted vars, not the gate name.
    rendered = _BRIEF_ENV.from_string(_load_brief("p3_edl_select")).render(**ctx)
    assert "Previous attempt (iteration 2) failed these checks" in rendered
    assert "range[0].start cuts inside word" in rendered
    assert "overlays must be empty" in rendered


def test_brief_omits_violations_block_on_first_attempt():
    """No prior failure → macro emits empty string → brief is byte-equivalent
    to the pre-HOM-147 form (modulo the macro import line)."""
    from edit_episode_graph.nodes._llm import _BRIEF_ENV, _load_brief

    ctx = {
        "slug": "x", "episode_dir": "/tmp/x",
        "takes_packed_path": "/x", "transcript_paths_json": "[]",
        "pre_scan_slips_json": "[]", "strategy_json": "{}",
        "prior_violations": [],
        "prior_iteration": 0,
    }
    rendered = _BRIEF_ENV.from_string(_load_brief("p3_edl_select")).render(**ctx)
    assert "Previous attempt" not in rendered
    assert "failed these checks" not in rendered
