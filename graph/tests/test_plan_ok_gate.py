"""Unit tests for gate:plan_ok."""

from __future__ import annotations

from edit_episode_graph.gates.plan_ok import PlanOkGate, plan_ok_gate_node


def _good_plan() -> dict:
    return {
        "narrative_arc": "Hook → tension → payoff.",
        "rhythm": "fast-SLOW-fast",
        "beats": [
            {
                "beat": "HOOK", "concept": "c", "mood": "m",
                "energy": "medium", "duration_s": 6.9,
                "catalog_or_custom": "custom", "justification": "off-axis layout",
            },
            {
                "beat": "PROBLEM", "concept": "c", "mood": "m",
                "energy": "calm", "duration_s": 10.5,
                "catalog_or_custom": "catalog", "justification": "stat-hold",
            },
            {
                "beat": "PAYOFF", "concept": "c", "mood": "m",
                "energy": "high", "duration_s": 8.4,
                "catalog_or_custom": "custom", "justification": "hairline rules",
            },
        ],
        "transitions": [
            {"from_beat": "HOOK", "to_beat": "PROBLEM",
             "mechanism": "css", "name": "blur crossfade",
             "duration_s": 0.6, "easing": "sine.inOut", "why": "."},
            {"from_beat": "PROBLEM", "to_beat": "PAYOFF",
             "mechanism": "shader", "name": "cinematic zoom",
             "duration_s": 0.4, "easing": "power3.out", "why": "."},
            {"from_beat": "PAYOFF", "to_beat": "END",
             "mechanism": "final-fade", "name": "fade-to-black",
             "duration_s": 0.5, "easing": "power2.in", "why": "."},
        ],
    }


def _state_with_edl(plan: dict, beats: list[str]) -> dict:
    return {
        "compose": {"plan": plan},
        "edit": {"edl": {"ranges": [
            {"source": "raw", "start": 0.0, "end": 1.0,
             "beat": b, "quote": "x", "reason": "y"} for b in beats
        ]}},
    }


def test_passes_on_clean_plan():
    state = _state_with_edl(_good_plan(), ["HOOK", "PROBLEM", "PAYOFF"])
    record = plan_ok_gate_node(state)["gate_results"][0]
    assert record["passed"], record["violations"]
    assert record["gate"] == "gate:plan_ok"


def test_fails_under_three_beats():
    plan = _good_plan()
    plan["beats"] = plan["beats"][:2]
    plan["transitions"] = plan["transitions"][:1]
    state = _state_with_edl(plan, ["HOOK", "PROBLEM"])
    record = plan_ok_gate_node(state)["gate_results"][0]
    assert not record["passed"]
    assert any("≥ 3" in v or ">= 3" in v or "need ≥" in v for v in record["violations"])


def test_fails_when_interior_boundary_missing():
    plan = _good_plan()
    plan["transitions"] = [t for t in plan["transitions"]
                           if (t["from_beat"], t["to_beat"]) != ("HOOK", "PROBLEM")]
    state = _state_with_edl(plan, ["HOOK", "PROBLEM", "PAYOFF"])
    record = plan_ok_gate_node(state)["gate_results"][0]
    assert not record["passed"]
    assert any("HOOK" in v and "PROBLEM" in v for v in record["violations"])


def test_fails_when_mechanism_invalid():
    plan = _good_plan()
    plan["transitions"][0]["mechanism"] = "magic-wipe"
    state = _state_with_edl(plan, ["HOOK", "PROBLEM", "PAYOFF"])
    record = plan_ok_gate_node(state)["gate_results"][0]
    assert not record["passed"]
    assert any("mechanism" in v for v in record["violations"])


def test_fails_when_final_fade_not_on_last_beat():
    plan = _good_plan()
    # Move final-fade so it claims to fire on a non-last beat.
    plan["transitions"][0] = {
        "from_beat": "HOOK", "to_beat": "PROBLEM",
        "mechanism": "final-fade", "name": "fade",
        "duration_s": 0.5, "easing": "power2.in", "why": ".",
    }
    state = _state_with_edl(plan, ["HOOK", "PROBLEM", "PAYOFF"])
    record = plan_ok_gate_node(state)["gate_results"][0]
    assert not record["passed"]
    assert any("final-fade" in v and "last beat" in v for v in record["violations"])


def test_fails_when_catalog_or_custom_missing():
    plan = _good_plan()
    plan["beats"][0]["catalog_or_custom"] = None
    state = _state_with_edl(plan, ["HOOK", "PROBLEM", "PAYOFF"])
    record = plan_ok_gate_node(state)["gate_results"][0]
    assert not record["passed"]
    assert any("catalog_or_custom" in v for v in record["violations"])


def test_fails_when_justification_empty():
    plan = _good_plan()
    plan["beats"][1]["justification"] = "   "
    state = _state_with_edl(plan, ["HOOK", "PROBLEM", "PAYOFF"])
    record = plan_ok_gate_node(state)["gate_results"][0]
    assert not record["passed"]
    assert any("justification" in v for v in record["violations"])


def test_fails_when_edl_beat_unmapped():
    plan = _good_plan()
    state = _state_with_edl(plan, ["HOOK", "PROBLEM", "PAYOFF", "ORPHAN"])
    record = plan_ok_gate_node(state)["gate_results"][0]
    assert not record["passed"]
    assert any("ORPHAN" in v for v in record["violations"])


def test_fails_when_beats_out_of_edl_order():
    plan = _good_plan()
    plan["beats"].reverse()
    plan["transitions"] = [
        {"from_beat": "PAYOFF", "to_beat": "PROBLEM",
         "mechanism": "css", "name": "blur crossfade",
         "duration_s": 0.6, "easing": "sine.inOut", "why": "."},
        {"from_beat": "PROBLEM", "to_beat": "HOOK",
         "mechanism": "shader", "name": "cinematic zoom",
         "duration_s": 0.4, "easing": "power3.out", "why": "."},
    ]
    state = _state_with_edl(plan, ["HOOK", "PROBLEM", "PAYOFF"])
    record = plan_ok_gate_node(state)["gate_results"][0]
    assert not record["passed"]
    assert any("out of EDL order" in v for v in record["violations"])


def test_skipped_plan_emits_violation():
    state = {"compose": {"plan": {"skipped": True, "skip_reason": "no edl"}}}
    record = plan_ok_gate_node(state)["gate_results"][0]
    assert not record["passed"]
    assert "skipped upstream" in record["violations"][0]


def test_unparseable_plan_emits_violation():
    state = {"compose": {"plan": {"raw_text": "the model returned prose"}}}
    record = plan_ok_gate_node(state)["gate_results"][0]
    assert not record["passed"]
    assert "unparseable" in record["violations"][0]


def test_iteration_increments_across_invocations():
    state = _state_with_edl(_good_plan(), ["HOOK", "PROBLEM", "PAYOFF"])
    first = plan_ok_gate_node(state)
    state["gate_results"] = first["gate_results"]
    second = plan_ok_gate_node(state)
    assert second["gate_results"][0]["iteration"] == 2


def test_gate_class_identity():
    g = PlanOkGate()
    assert g.name == "gate:plan_ok"
