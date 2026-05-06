"""halt_llm_boundary copy: distinguishes v1 vs v2 halt so Studio shows
*why* the run stopped and what would unblock it."""

from __future__ import annotations

from edit_episode_graph.nodes.halt_llm_boundary import halt_llm_boundary_node


def test_v1_halt_when_pre_scan_skipped():
    state = {"edit": {"pre_scan": {"skipped": True, "skip_reason": "missing"}}}
    update = halt_llm_boundary_node(state)
    msg = update["notices"][0]
    assert msg.startswith("v1 halt")
    assert "final.mp4" in msg


def test_v1_halt_when_no_pre_scan_state_at_all():
    update = halt_llm_boundary_node({})
    assert update["notices"][0].startswith("v1 halt")


def test_v2_halt_when_pre_scan_ran():
    state = {"edit": {"pre_scan": {"slips": [
        {"quote": "x", "take_index": 1, "reason": "placeholder"},
    ]}}}
    update = halt_llm_boundary_node(state)
    msg = update["notices"][0]
    assert msg.startswith("v2 halt: pre_scan ran")
    assert "1 slip" in msg


def test_v2_halt_with_zero_slips_still_v2():
    """An empty `slips` list still indicates pre_scan executed (no placeholders found)."""
    state = {"edit": {"pre_scan": {"slips": []}}}
    update = halt_llm_boundary_node(state)
    assert update["notices"][0].startswith("v2 halt: pre_scan ran")


def test_v3_halt_when_render_completed():
    state = {
        "edit": {
            "edl": {"ranges": [{}, {}, {}]},
            "render": {
                "final_mp4": "/x/edit/final.mp4",
                "n_segments": 3,
                "delta_ms": 12,
                "cached": False,
            },
        },
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert msg.startswith("v3 halt: final.mp4 rendered")
    assert "3 segment" in msg
    assert "12ms" in msg


def test_v3_halt_marks_cached_render():
    state = {
        "edit": {
            "edl": {"ranges": [{}]},
            "render": {"final_mp4": "/x/edit/final.mp4", "n_segments": 1, "cached": True},
        },
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert "[cached]" in msg


def test_v4_halt_after_plan_gate_pass():
    state = {
        "compose": {"plan": {"beats": [{}, {}, {}]}},
        "gate_results": [
            {"gate": "gate:plan_ok", "passed": True, "iteration": 1,
             "violations": [], "timestamp": "now"},
        ],
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert msg.startswith("v4 halt: gate:plan_ok passed")
    assert "p4_catalog_scan" in msg


def test_v4_halt_after_catalog_scan():
    """Catalog scanned but assembly hasn't run — notice names catalog as latest reachable."""
    state = {
        "compose": {
            "catalog": {"blocks": [{}, {}], "components": [{}], "fetched_at": "now"},
        },
        "gate_results": [
            {"gate": "gate:plan_ok", "passed": True, "iteration": 1,
             "violations": [], "timestamp": "now"},
        ],
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert "catalog scanned" in msg
    assert "2 block" in msg
    assert "1 component" in msg
    # HOM-123: post-catalog the next reachable artifact is p4_captions_layer
    # (captions inserted between catalog scan and the dispatch decision);
    # the message falls back to p4_assemble_index once captions are written.
    assert "p4_captions_layer" in msg


def test_v4_halt_after_assemble_skip():
    state = {
        "compose": {
            "catalog": {"blocks": [{}], "components": [], "fetched_at": "now"},
            "assemble": {"skipped": True, "skip_reason": "no beats in state"},
        },
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert "p4_assemble_index skipped" in msg
    assert "no beats" in msg


def test_v4_halt_after_assemble_success():
    state = {
        "compose": {
            "assemble": {
                "assembled_at": "now",
                "beat_names": ["HOOK", "PAYOFF"],
                "captions_included": True,
            },
        },
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert "scenes assembled" in msg
    assert "2 scene" in msg
    # HOM-125: assemble-success without a static_guard record means
    # studio_launch errored — notice mentions both studio_launch and errors[].
    assert "studio_launch" in msg


def test_v4_halt_after_static_guard_pass():
    state = {
        "compose": {
            "preview_port": 3002,
            "assemble": {"assembled_at": "now", "beat_names": ["A"]},
        },
        "gate_results": [
            {"gate": "gate:static_guard", "passed": True, "violations": [], "iteration": 1},
        ],
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert "studio launched" in msg
    assert "PASSED" in msg
    assert "port 3002" in msg


def test_v4_halt_after_static_guard_fail():
    state = {
        "compose": {"assemble": {"assembled_at": "now", "beat_names": ["A"]}},
        "gate_results": [
            {
                "gate": "gate:static_guard",
                "passed": False,
                "violations": ["StaticGuard: missing data-hf-anchor"],
                "iteration": 1,
            },
        ],
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert "FAILED" in msg
    assert "1 violation" in msg


def test_v4_halt_after_static_guard_canon_artifact():
    state = {
        "compose": {"assemble": {"assembled_at": "now", "beat_names": ["A"]}},
        "gate_results": [
            {
                "gate": "gate:static_guard",
                "passed": True,
                "violations": [],
                "iteration": 1,
                "canon_video_audio_artifact": True,
            },
        ],
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert "PASSED" in msg
    assert "data-has-audio" in msg


def test_halt_notice_on_edl_resume_abort():
    state = {
        "edit": {"edl": {"failure_resume": {"action": "abort"}}},
        "gate_results": [
            {"gate": "gate:edl_ok", "passed": False, "violations": ["v1", "v2"], "iteration": 1}
        ],
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert msg.startswith("v3 halt: gate:edl_ok FAILED")
    assert "2 violation" in msg
    assert "operator aborted" in msg


def test_halt_notice_on_eval_resume_abort():
    state = {
        "edit": {"eval": {"failure_resume": {"action": {"abort": True}}}},
        "gate_results": [
            {"gate": "gate:eval_ok", "passed": False, "violations": ["v"], "iteration": 3}
        ],
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert msg.startswith("v3 halt: gate:eval_ok FAILED")
    assert "iter 3" in msg
    assert "operator aborted" in msg


def test_halt_notice_on_phase3_review_abort():
    """HOM-146: explicit abort at p3_review_interrupt must surface its own
    notice — not the stale 'final.mp4 rendered' one that would otherwise
    fire (final.mp4 always exists by the time we reach this checkpoint)."""
    state = {
        "edit": {
            "review": {"phase3": {"aborted": True}},
            "render": {
                "final_mp4": "/x/edit/final.mp4",
                "n_segments": 3,
                "delta_ms": 12,
                "cached": False,
            },
        },
    }
    msg = halt_llm_boundary_node(state)["notices"][0]
    assert "Phase 3 review aborted" in msg
    assert "re-Submit" in msg
    assert "final.mp4 rendered" not in msg

