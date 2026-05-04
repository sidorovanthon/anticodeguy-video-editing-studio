"""Unit tests for gate:eval_ok — uses an injected ffprobe stub."""

from __future__ import annotations

from edit_episode_graph.gates.eval_ok import EvalOkGate


def _state(*, passed: bool, issues=None, total: float = 5.0, final: str | None = "/abs/final.mp4") -> dict:
    return {
        "edit": {
            "eval": {"passed": passed, "issues": issues or []},
            "render": {"final_mp4": final},
            "edl": {"total_duration_s": total},
        }
    }


def _fake_probe(value: float | None):
    return lambda path: value


def test_passes_on_clean_eval_and_matching_duration():
    gate = EvalOkGate(probe=_fake_probe(5.05))
    record = gate(_state(passed=True))["gate_results"][0]
    assert record["passed"], record["violations"]
    assert record["gate"] == "gate:eval_ok"
    assert record["iteration"] == 1


def test_fails_when_passed_false():
    gate = EvalOkGate(probe=_fake_probe(5.0))
    record = gate(_state(passed=False))["gate_results"][0]
    assert not record["passed"]
    assert any("passed=false" in v for v in record["violations"])


def test_fails_when_blocker_issue_present():
    gate = EvalOkGate(probe=_fake_probe(5.0))
    issues = [{"kind": "audio_pop", "location": "cut[1]@2.0s", "severity": "blocker", "note": "x"}]
    record = gate(_state(passed=True, issues=issues))["gate_results"][0]
    assert not record["passed"]
    assert any("blocker" in v for v in record["violations"])


def test_passes_with_only_note_severity():
    gate = EvalOkGate(probe=_fake_probe(5.0))
    issues = [{"kind": "grade_drift", "location": "1.0s", "severity": "note", "note": "x"}]
    record = gate(_state(passed=True, issues=issues))["gate_results"][0]
    assert record["passed"], record["violations"]


def test_fails_on_duration_drift_beyond_tolerance():
    gate = EvalOkGate(probe=_fake_probe(5.5))  # 500ms vs 5.0 expected
    record = gate(_state(passed=True, total=5.0))["gate_results"][0]
    assert not record["passed"]
    assert any("deviates from EDL" in v for v in record["violations"])


def test_passes_on_duration_within_tolerance():
    gate = EvalOkGate(probe=_fake_probe(5.099))  # 99ms < 100ms cap
    record = gate(_state(passed=True, total=5.0))["gate_results"][0]
    assert record["passed"], record["violations"]


def test_fails_when_ffprobe_returns_none():
    gate = EvalOkGate(probe=_fake_probe(None))
    record = gate(_state(passed=True))["gate_results"][0]
    assert not record["passed"]
    assert any("ffprobe failed" in v for v in record["violations"])


def test_fails_when_final_mp4_missing():
    gate = EvalOkGate(probe=_fake_probe(5.0))
    record = gate(_state(passed=True, final=None))["gate_results"][0]
    assert not record["passed"]
    assert any("final_mp4 missing" in v for v in record["violations"])


def test_skipped_eval_emits_violation():
    gate = EvalOkGate(probe=_fake_probe(5.0))
    state = {"edit": {"eval": {"skipped": True, "skip_reason": "render missing"}}}
    record = gate(state)["gate_results"][0]
    assert not record["passed"]
    assert "skipped upstream" in record["violations"][0]


def test_iteration_increments_across_invocations():
    gate = EvalOkGate(probe=_fake_probe(5.0))
    state = _state(passed=False)
    first = gate(state)
    state["gate_results"] = first["gate_results"]
    second = gate(state)
    assert second["gate_results"][0]["iteration"] == 2
