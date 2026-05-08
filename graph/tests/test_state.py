"""Unit tests for state-schema reducers (HOM-163).

Covers `gate_results_reducer` clear-on-replay semantics:
  * default additive-append behavior preserved (back-compat)
  * `_replace` sentinel — full replace
  * `_clear_gate` sentinel — selective filter by gate name
  * `_clear_gate` no-op when nothing matches
  * empty-left edge cases
  * single-dict right operand (legacy / defensive shape)
"""

from edit_episode_graph.state import gate_results_reducer


def _rec(gate: str, *, passed: bool = False, iteration: int = 1) -> dict:
    return {"gate": gate, "passed": passed, "iteration": iteration}


def test_default_append_list_of_records():
    left = [_rec("gate:lint")]
    right = [_rec("gate:eval_ok"), _rec("gate:lint", iteration=2)]
    out = gate_results_reducer(left, right)
    assert [r["gate"] for r in out] == ["gate:lint", "gate:eval_ok", "gate:lint"]
    # Original list not mutated.
    assert len(left) == 1


def test_append_into_empty_left():
    out = gate_results_reducer(None, [_rec("gate:lint")])
    assert out == [_rec("gate:lint")]
    out2 = gate_results_reducer([], [_rec("gate:lint")])
    assert out2 == [_rec("gate:lint")]


def test_append_none_right_is_noop():
    left = [_rec("gate:lint")]
    out = gate_results_reducer(left, None)
    assert out == left
    # New list, not aliased.
    assert out is not left


def test_replace_sentinel_full():
    left = [_rec("gate:lint"), _rec("gate:eval_ok")]
    out = gate_results_reducer(left, {"_replace": True, "items": [_rec("gate:plan_ok")]})
    assert out == [_rec("gate:plan_ok")]


def test_replace_sentinel_empty_clears_all():
    left = [_rec("gate:lint")]
    out = gate_results_reducer(left, {"_replace": True})
    assert out == []
    out2 = gate_results_reducer(left, {"_replace": True, "items": []})
    assert out2 == []


def test_clear_gate_sentinel_drops_matching():
    left = [
        _rec("gate:lint", iteration=1),
        _rec("gate:eval_ok"),
        _rec("gate:lint", iteration=2),
        _rec("gate:plan_ok"),
    ]
    out = gate_results_reducer(left, {"_clear_gate": "gate:lint"})
    assert [r["gate"] for r in out] == ["gate:eval_ok", "gate:plan_ok"]


def test_clear_gate_sentinel_no_match_is_noop():
    left = [_rec("gate:eval_ok"), _rec("gate:plan_ok")]
    out = gate_results_reducer(left, {"_clear_gate": "gate:nonexistent"})
    assert out == left
    assert out is not left  # fresh copy


def test_clear_gate_sentinel_on_empty_left():
    out = gate_results_reducer(None, {"_clear_gate": "gate:lint"})
    assert out == []
    out2 = gate_results_reducer([], {"_clear_gate": "gate:lint"})
    assert out2 == []


def test_single_dict_record_appended_as_legacy_shape():
    """A bare-dict record (no sentinel keys) appends defensively.

    None of the canonical writers emit this shape — they all wrap in `[record]`
    — but we tolerate it because historically `Annotated[list, add]` would
    have raised on a dict (`list + dict`), masking the bug. Now it's clearly
    appended.
    """
    left = [_rec("gate:lint")]
    rec = _rec("gate:eval_ok")
    out = gate_results_reducer(left, rec)
    assert out == [_rec("gate:lint"), _rec("gate:eval_ok")]


def test_sentinel_keys_take_precedence_over_record_shape():
    """Defense-in-depth: a dict that looks like a record but ALSO contains
    `_clear_gate` is treated as a sentinel. This shouldn't happen in
    practice (gate writers never emit `_clear_gate`), but if a future writer
    accidentally collides we'd rather it surface as a clear, not silently
    appended garbage."""
    left = [_rec("gate:lint")]
    out = gate_results_reducer(left, {"gate": "x", "_clear_gate": "gate:lint"})
    assert out == []


def test_replace_then_clear_chain_via_repeated_application():
    """Reducer is binary; chained applications produce expected sequence."""
    s = []
    s = gate_results_reducer(s, [_rec("gate:lint")])
    s = gate_results_reducer(s, [_rec("gate:eval_ok")])
    s = gate_results_reducer(s, {"_clear_gate": "gate:lint"})
    assert [r["gate"] for r in s] == ["gate:eval_ok"]
    s = gate_results_reducer(s, {"_replace": True, "items": []})
    assert s == []
