"""Unit tests for gate:design_ok."""

from __future__ import annotations

import pytest

from edit_episode_graph.gates.design_ok import (
    DESIGN_MD_MIN_BYTES,
    DesignOkGate,
    design_ok_gate_node,
)


_GOOD_DESIGN_MD_BODY = (
    "---\nname: Swiss Pulse\ncolors:\n  primary: '#0a0a0a'\n---\n"
    "## Overview\n\n" + ("body content " * 60) + "\n"
)


def _good_design(design_md_body: str = _GOOD_DESIGN_MD_BODY) -> dict:
    return {
        "style_name": "Swiss Pulse",
        "palette": [
            {"role": "background", "hex": "#0a0a0a"},
            {"role": "foreground", "hex": "#f0f0f0"},
        ],
        "typography": [
            {"role": "headline", "family": "Helvetica Neue", "weight": 700},
        ],
        "refs": [
            {"label": "MB",     "description": "grid"},
            {"label": "Stripe", "description": "editorial"},
        ],
        "alternatives": [{"name": "Folk", "rejected_because": "tone"}],
        "anti_patterns": ["no neon", "no centered", "no gradient text"],
        "beat_visual_mapping": [
            {"beat": "HOOK",    "treatment": "tight"},
            {"beat": "PAYOFF",  "treatment": "wide"},
        ],
        # HOM-270: state-first body. The gate no longer reads from disk;
        # it inspects the body string the producer put in state.
        "design_md": design_md_body,
    }


@pytest.fixture()
def good_design_md_body() -> str:
    """A DESIGN.md body whose size sits comfortably above DESIGN_MD_MIN_BYTES."""
    body = _GOOD_DESIGN_MD_BODY
    assert len(body.encode("utf-8")) > DESIGN_MD_MIN_BYTES
    return body


def _state_with_edl_beats(design: dict, beats: list[str]) -> dict:
    return {
        "compose": {"design": design},
        "edit": {
            "edl": {
                "ranges": [
                    {"source": "raw", "start": 0.0, "end": 1.0,
                     "beat": b, "quote": "x", "reason": "y"} for b in beats
                ],
            },
        },
    }


def test_passes_on_clean_design(good_design_md_body: str):
    state = _state_with_edl_beats(_good_design(good_design_md_body), ["HOOK", "PAYOFF"])
    update = design_ok_gate_node(state)
    record = update["gate_results"][0]
    assert record["passed"], record["violations"]
    assert record["gate"] == "gate:design_ok"


def test_fails_when_design_md_body_absent():
    """HOM-270: body missing in state must violate (producer skipped state write)."""
    design = _good_design()
    design["design_md"] = None
    state = _state_with_edl_beats(design, ["HOOK"])
    update = design_ok_gate_node(state)
    assert not update["gate_results"][0]["passed"]
    assert any(
        "design_md" in v and "absent" in v for v in update["gate_results"][0]["violations"]
    )


def test_fails_when_design_md_body_too_small():
    state = _state_with_edl_beats(_good_design("ok"), ["HOOK"])
    update = design_ok_gate_node(state)
    assert not update["gate_results"][0]["passed"]
    assert any("suspiciously small" in v for v in update["gate_results"][0]["violations"])


def test_fails_at_threshold_minus_one_byte():
    """Boundary: a body exactly one byte below the threshold must fail."""
    body = "a" * (DESIGN_MD_MIN_BYTES - 1)
    assert len(body.encode("utf-8")) == DESIGN_MD_MIN_BYTES - 1
    state = _state_with_edl_beats(_good_design(body), ["HOOK"])
    update = design_ok_gate_node(state)
    assert not update["gate_results"][0]["passed"]
    assert any("suspiciously small" in v for v in update["gate_results"][0]["violations"])


def test_passes_at_threshold():
    """Boundary: a body at exactly the threshold must NOT fire the size check.

    Other gate checks may still fail unrelated to size — we assert the
    specific 'suspiciously small' violation does not appear, not that the
    gate as a whole passes.
    """
    body = "a" * DESIGN_MD_MIN_BYTES
    assert len(body.encode("utf-8")) == DESIGN_MD_MIN_BYTES
    state = _state_with_edl_beats(_good_design(body), ["HOOK"])
    record = design_ok_gate_node(state)["gate_results"][0]
    assert not any("suspiciously small" in v for v in record["violations"])


def test_skeleton_design_md_with_all_headers_fails():
    """Regression check: a YAML-frontmatter + 7 empty-section skeleton must
    be rejected. This is the exact failure mode the threshold raise targets —
    on the original 200B threshold, a body like this slipped past."""
    body = (
        "---\nname: x\ncolors:\n  a: b\ntypography:\n  a: b\n"
        "rounded:\n  a: b\nspacing:\n  a: b\nmotion:\n  a: b\n---\n"
        "## Overview\n\n## Colors\n\n## Typography\n\n## Layout\n\n"
        "## Elevation\n\n## Components\n\n## Do's and Don'ts\n"
    )
    assert len(body.encode("utf-8")) < DESIGN_MD_MIN_BYTES, (
        f"skeleton size {len(body.encode('utf-8'))}B should be below {DESIGN_MD_MIN_BYTES}B "
        "or the regression check tests nothing"
    )
    state = _state_with_edl_beats(_good_design(body), ["HOOK"])
    record = design_ok_gate_node(state)["gate_results"][0]
    assert not record["passed"]
    assert any("suspiciously small" in v for v in record["violations"])


def test_fails_on_substance_underflow(good_design_md_body: str):
    design = _good_design(good_design_md_body)
    design["refs"] = design["refs"][:1]
    design["alternatives"] = []
    design["anti_patterns"] = ["just two", "items"]
    state = _state_with_edl_beats(design, ["HOOK"])
    record = design_ok_gate_node(state)["gate_results"][0]
    assert not record["passed"]
    msg = " ".join(record["violations"])
    assert "refs" in msg and "alternatives" in msg and "anti_patterns" in msg


def test_fails_when_beat_unmapped(good_design_md_body: str):
    design = _good_design(good_design_md_body)
    state = _state_with_edl_beats(design, ["HOOK", "PAYOFF", "ORPHAN"])
    record = design_ok_gate_node(state)["gate_results"][0]
    assert not record["passed"]
    assert any("ORPHAN" in v for v in record["violations"])


def test_fails_when_named_preset_diverges(good_design_md_body: str):
    design = _good_design(good_design_md_body)
    design["style_name"] = "Folk Frequency"
    state = _state_with_edl_beats(design, ["HOOK", "PAYOFF"])
    state["edit"]["strategy"] = {
        "shape": "user requested Swiss Pulse aesthetic",
        "pacing": "tight",
    }
    record = design_ok_gate_node(state)["gate_results"][0]
    assert not record["passed"]
    assert any("Swiss Pulse" in v for v in record["violations"])


def test_passes_when_no_named_preset(good_design_md_body: str):
    """When the operator did not name a preset, custom style_name is fine."""
    design = _good_design(good_design_md_body)
    design["style_name"] = "Anticodeguy Custom"
    state = _state_with_edl_beats(design, ["HOOK", "PAYOFF"])
    record = design_ok_gate_node(state)["gate_results"][0]
    assert record["passed"], record["violations"]


def test_skipped_design_emits_violation():
    state = {"compose": {"design": {"skipped": True, "skip_reason": "no edl"}}}
    update = design_ok_gate_node(state)
    assert not update["gate_results"][0]["passed"]
    assert "skipped upstream" in update["gate_results"][0]["violations"][0]


def test_unparseable_design_emits_violation():
    state = {"compose": {"design": {"raw_text": "the model returned prose, not JSON"}}}
    update = design_ok_gate_node(state)
    assert not update["gate_results"][0]["passed"]
    assert "unparseable" in update["gate_results"][0]["violations"][0]


def test_iteration_increments_across_invocations(good_design_md_body: str):
    state = _state_with_edl_beats(_good_design(good_design_md_body), ["HOOK"])
    first = design_ok_gate_node(state)
    state["gate_results"] = first["gate_results"]
    second = design_ok_gate_node(state)
    assert second["gate_results"][0]["iteration"] == 2


def test_gate_class_identity():
    g = DesignOkGate()
    assert g.name == "gate:design_ok"
