"""Unit tests for p4_transitions node (HOM-137).

Deterministic node — no LLM dispatch. Replaces the v4 visibility shim
written by p4_assemble_index with a canonical root-timeline transitions
block per `~/.agents/skills/hyperframes/references/transitions/catalog.md`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from edit_episode_graph.nodes.p4_transitions import (
    _BEGIN_MARKER,
    _END_MARKER,
    _SHIM_BEGIN_MARKER,
    _SHIM_END_MARKER,
    _cache_key,
    assemble_html,
    build_transitions_block,
    p4_transitions_node,
)


# Index.html shape that includes the v4 visibility shim p4_assemble_index
# would have written. p4_transitions must STRIP this and replace it.
def _scaffolded_index_with_shim() -> str:
    return f"""\
<!doctype html>
<html>
  <head></head>
  <body>
    <div data-composition-id="root" data-width="1920" data-height="1080" data-duration="20">
      <div id="scene-hook" class="scene clip" data-start="0" data-duration="3">H</div>
      <div id="scene-build" class="scene clip" data-start="3" data-duration="4">B</div>
      <div id="scene-payoff" class="scene clip" data-start="7" data-duration="5">P</div>
    </div>
    {_SHIM_BEGIN_MARKER}
    <script>/* legacy v4 shim */</script>
    {_SHIM_END_MARKER}
  </body>
</html>
"""


def _plan_state(tmp_path: Path, transitions: list[dict], beats=None) -> dict:
    """Build minimal state with index.html body in state + plan transitions.

    HOM-239 (Step D2 of HOM-230 state-first artifacts): the disk-read
    fallback in `_load_root_html` is gone. State must carry the
    assembled body via `compose.index_html`. `tmp_path` is retained for
    test-isolation parity with other p4_* unit tests but no longer
    seeds disk.
    """
    if beats is None:
        beats = [
            {"beat": "HOOK", "duration_s": 3.0},
            {"beat": "BUILD", "duration_s": 4.0},
            {"beat": "PAYOFF", "duration_s": 5.0},
        ]
    return {
        "compose": {
            "index_html": _scaffolded_index_with_shim(),
            "plan": {"beats": beats, "transitions": transitions},
        },
    }


# ---- pure builders / assemble_html ----


def test_build_transitions_block_returns_none_for_empty_list():
    assert build_transitions_block(transitions=[], beats=[]) is None


def test_build_transitions_block_emits_css_crossfade_with_root_timeline():
    """CSS mechanism → tl.to + tl.fromTo with chosen duration/easing on root."""
    transitions = [
        {
            "from_beat": "HOOK", "to_beat": "BUILD",
            "mechanism": "css", "name": "crossfade",
            "duration_s": 0.5, "easing": "power2.inOut", "why": "soft handoff",
        },
    ]
    beats = [
        {"beat": "HOOK", "duration_s": 3.0},
        {"beat": "BUILD", "duration_s": 4.0},
    ]
    block = build_transitions_block(transitions=transitions, beats=beats)
    assert block is not None
    assert _BEGIN_MARKER in block
    assert _END_MARKER in block
    # Canonical baseline: outgoing opacity → 0 + incoming fromTo 0 → 1.
    assert "root.to('#scene-hook'" in block
    assert "opacity: 0" in block
    assert "root.fromTo('#scene-build'" in block
    assert '"power2.inOut"' in block
    # Position = cumulative start of `to_beat` (BUILD starts at 3.0).
    assert ", 3);" in block or ", 3.0);" in block
    # Plan-chosen `name` recorded as comment for reviewer traceability.
    assert "crossfade" in block
    # Registers on window.__timelines["root"] — root timeline access.
    assert '__timelines["root"]' in block


def test_build_transitions_block_shader_uses_hf_shader_transitions_runtime():
    """Shader mechanism → @hyperframes/shader-transitions runtime call."""
    transitions = [
        {
            "from_beat": "HOOK", "to_beat": "BUILD",
            "mechanism": "shader", "name": "ripple",
            "duration_s": 0.4, "easing": "power2.out", "why": "energetic cut",
        },
    ]
    beats = [
        {"beat": "HOOK", "duration_s": 3.0},
        {"beat": "BUILD", "duration_s": 4.0},
    ]
    block = build_transitions_block(transitions=transitions, beats=beats)
    assert block is not None
    # The package's runtime entry point is referenced — no raw GLSL.
    assert "HFShaderTransitions" in block
    assert "ripple" in block
    # Defensive fallback to crossfade if package unloaded.
    assert "Fallback" in block
    assert "root.to('#scene-hook'" in block  # fallback path uses same selector
    # Anchors on root timeline.
    assert '__timelines["root"]' in block


def test_build_transitions_block_final_fade_anchors_at_end_minus_duration():
    """final-fade → tl.to('#scene-<last>', opacity: 0) at end - duration."""
    transitions = [
        {
            "from_beat": "PAYOFF", "to_beat": "END",
            "mechanism": "final-fade", "name": "fade-to-black",
            "duration_s": 0.8, "easing": "power1.in", "why": "cinematic close",
        },
    ]
    beats = [
        {"beat": "HOOK", "duration_s": 3.0},
        {"beat": "BUILD", "duration_s": 4.0},
        {"beat": "PAYOFF", "duration_s": 5.0},
    ]
    block = build_transitions_block(transitions=transitions, beats=beats)
    assert block is not None
    # Total = 12, position = 12 - 0.8 = 11.2.
    assert "11.2" in block
    assert "root.to('#scene-payoff'" in block
    assert "opacity: 0" in block
    # final-fade comment surfaces the catalog `name`.
    assert "fade-to-black" in block


def test_build_transitions_block_combines_all_three_mechanisms():
    transitions = [
        {"from_beat": "HOOK", "to_beat": "BUILD", "mechanism": "css",
         "name": "blur crossfade", "duration_s": 0.5, "easing": "power2.inOut",
         "why": "x"},
        {"from_beat": "BUILD", "to_beat": "PAYOFF", "mechanism": "shader",
         "name": "page burn", "duration_s": 0.4, "easing": "power1.out",
         "why": "y"},
        {"from_beat": "PAYOFF", "to_beat": "END", "mechanism": "final-fade",
         "name": "fade-to-black", "duration_s": 0.8, "easing": "power1.in",
         "why": "z"},
    ]
    beats = [
        {"beat": "HOOK", "duration_s": 3.0},
        {"beat": "BUILD", "duration_s": 4.0},
        {"beat": "PAYOFF", "duration_s": 5.0},
    ]
    block = build_transitions_block(transitions=transitions, beats=beats)
    assert "root.to('#scene-hook'" in block
    assert "HFShaderTransitions" in block
    assert "11.2" in block  # final-fade at end - 0.8


def test_assemble_html_strips_v4_shim_and_injects_transitions_block():
    block = build_transitions_block(
        transitions=[{
            "from_beat": "HOOK", "to_beat": "BUILD", "mechanism": "css",
            "name": "crossfade", "duration_s": 0.5, "easing": "power2.inOut",
            "why": "x",
        }],
        beats=[
            {"beat": "HOOK", "duration_s": 3.0},
            {"beat": "BUILD", "duration_s": 4.0},
        ],
    )
    out = assemble_html(root_html=_scaffolded_index_with_shim(), transitions_block=block)
    # v4 shim block is gone.
    assert _SHIM_BEGIN_MARKER not in out
    assert _SHIM_END_MARKER not in out
    assert "legacy v4 shim" not in out
    # New transitions block is in.
    assert _BEGIN_MARKER in out
    assert _END_MARKER in out
    assert out.index(_BEGIN_MARKER) < out.index("</body>")


def test_assemble_html_is_idempotent_on_rerun():
    block = build_transitions_block(
        transitions=[{
            "from_beat": "HOOK", "to_beat": "BUILD", "mechanism": "css",
            "name": "crossfade", "duration_s": 0.5, "easing": "power2.inOut",
            "why": "x",
        }],
        beats=[
            {"beat": "HOOK", "duration_s": 3.0},
            {"beat": "BUILD", "duration_s": 4.0},
        ],
    )
    once = assemble_html(root_html=_scaffolded_index_with_shim(), transitions_block=block)
    twice = assemble_html(root_html=once, transitions_block=block)
    assert twice.count(_BEGIN_MARKER) == 1
    assert twice.count(_END_MARKER) == 1


def test_assemble_html_with_no_block_strips_shim_and_writes_nothing_back():
    out = assemble_html(root_html=_scaffolded_index_with_shim(), transitions_block=None)
    assert _SHIM_BEGIN_MARKER not in out
    assert _BEGIN_MARKER not in out


# ---- node body ----


def test_node_skips_when_no_transitions(tmp_path):
    state = _plan_state(tmp_path, transitions=[])
    update = p4_transitions_node(state)
    assert update["compose"]["transitions"]["skipped"] is True
    reason = update["compose"]["transitions"]["skip_reason"].lower()
    assert "transitions" in reason or "plan" in reason
    # And the v4 shim was stripped from the body returned in state, even on skip.
    patched = update["compose"]["index_html"]
    assert _SHIM_BEGIN_MARKER not in patched


def test_node_authors_css_block_into_index_html(tmp_path):
    transitions = [{
        "from_beat": "HOOK", "to_beat": "BUILD", "mechanism": "css",
        "name": "crossfade", "duration_s": 0.5, "easing": "power2.inOut",
        "why": "soft",
    }]
    state = _plan_state(tmp_path, transitions=transitions)
    update = p4_transitions_node(state)
    assert "errors" not in update
    assert update["compose"]["transitions"]["n_transitions"] == 1
    assert update["compose"]["transitions"]["mechanisms"] == ["css"]
    patched = update["compose"]["index_html"]
    assert _BEGIN_MARKER in patched
    assert _SHIM_BEGIN_MARKER not in patched
    assert "root.fromTo('#scene-build'" in patched


def test_node_errors_when_from_beat_dangles(tmp_path):
    transitions = [{
        "from_beat": "GHOST", "to_beat": "BUILD", "mechanism": "css",
        "name": "crossfade", "duration_s": 0.5, "easing": "power2.inOut",
        "why": "x",
    }]
    state = _plan_state(tmp_path, transitions=transitions)
    update = p4_transitions_node(state)
    assert update["errors"][0]["node"] == "p4_transitions"
    assert "GHOST" in update["errors"][0]["message"]


def test_node_errors_when_to_beat_dangles(tmp_path):
    transitions = [{
        "from_beat": "HOOK", "to_beat": "PHANTOM", "mechanism": "css",
        "name": "crossfade", "duration_s": 0.5, "easing": "power2.inOut",
        "why": "x",
    }]
    state = _plan_state(tmp_path, transitions=transitions)
    update = p4_transitions_node(state)
    assert update["errors"][0]["node"] == "p4_transitions"
    assert "PHANTOM" in update["errors"][0]["message"]


def test_node_accepts_final_fade_to_synthetic_END(tmp_path):
    transitions = [{
        "from_beat": "PAYOFF", "to_beat": "END", "mechanism": "final-fade",
        "name": "fade-to-black", "duration_s": 0.8, "easing": "power1.in",
        "why": "close",
    }]
    state = _plan_state(tmp_path, transitions=transitions)
    update = p4_transitions_node(state)
    assert "errors" not in update
    patched = update["compose"]["index_html"]
    assert "root.to('#scene-payoff'" in patched


def test_node_errors_when_index_html_missing(tmp_path):
    transitions = [{
        "from_beat": "HOOK", "to_beat": "BUILD", "mechanism": "css",
        "name": "crossfade", "duration_s": 0.5, "easing": "power2.inOut",
        "why": "x",
    }]
    state = {
        "compose": {
            # HOM-239: no `compose.index_html` and no disk fallback — must error.
            "plan": {
                "beats": [
                    {"beat": "HOOK", "duration_s": 3.0},
                    {"beat": "BUILD", "duration_s": 4.0},
                ],
                "transitions": transitions,
            },
        },
    }
    update = p4_transitions_node(state)
    assert update["errors"][0]["node"] == "p4_transitions"


def test_node_rerun_does_not_double_block(tmp_path):
    transitions = [{
        "from_beat": "HOOK", "to_beat": "BUILD", "mechanism": "css",
        "name": "crossfade", "duration_s": 0.5, "easing": "power2.inOut",
        "why": "x",
    }]
    state = _plan_state(tmp_path, transitions=transitions)
    # Feed the first run's output body back as the second run's input
    # (mirrors production: assemble→transitions→materialize on a re-run).
    update1 = p4_transitions_node(state)
    state["compose"]["index_html"] = update1["compose"]["index_html"]
    update2 = p4_transitions_node(state)
    patched = update2["compose"]["index_html"]
    assert patched.count(_BEGIN_MARKER) == 1
    assert patched.count(_END_MARKER) == 1


# ---- cache key ----


def test_cache_key_is_stable_for_identical_state(tmp_path):
    transitions = [{
        "from_beat": "HOOK", "to_beat": "BUILD", "mechanism": "css",
        "name": "crossfade", "duration_s": 0.5, "easing": "power2.inOut",
        "why": "x",
    }]
    state_a = _plan_state(tmp_path, transitions=transitions)
    state_b = _plan_state(tmp_path / "alt", transitions=transitions)
    # Same slug (None → __unbound__), same plan content; key independent of
    # path on disk because the node fingerprints state extras only.
    assert _cache_key(state_a) == _cache_key(state_b)


def test_cache_key_flips_when_transitions_change(tmp_path):
    base = [{
        "from_beat": "HOOK", "to_beat": "BUILD", "mechanism": "css",
        "name": "crossfade", "duration_s": 0.5, "easing": "power2.inOut",
        "why": "x",
    }]
    mutated = [{
        "from_beat": "HOOK", "to_beat": "BUILD", "mechanism": "shader",
        "name": "ripple", "duration_s": 0.5, "easing": "power2.inOut",
        "why": "x",
    }]
    state_base = _plan_state(tmp_path, transitions=base)
    state_mut = _plan_state(tmp_path / "alt", transitions=mutated)
    assert _cache_key(state_base) != _cache_key(state_mut)


def test_cache_key_flips_when_beat_durations_change(tmp_path):
    transitions = [{
        "from_beat": "HOOK", "to_beat": "BUILD", "mechanism": "css",
        "name": "crossfade", "duration_s": 0.5, "easing": "power2.inOut",
        "why": "x",
    }]
    state_a = _plan_state(tmp_path, transitions=transitions)
    state_b = _plan_state(
        tmp_path / "alt",
        transitions=transitions,
        beats=[
            {"beat": "HOOK", "duration_s": 999.0},  # different duration
            {"beat": "BUILD", "duration_s": 4.0},
        ],
    )
    assert _cache_key(state_a) != _cache_key(state_b)


def test_cache_key_rejects_non_dict_state():
    with pytest.raises(TypeError):
        _cache_key("not a dict")


def test_cache_key_flips_when_index_html_body_changes(tmp_path):
    """HOM-259: state-first means a scene-body change upstream (which
    produces a different `compose.index_html` out of assemble) must
    invalidate the transitions cache even when plan.transitions and
    plan.beats are byte-identical. The third `stable_fingerprint(input_index_html)`
    extra in `_cache_key` is the mechanism — this test guards it.
    """
    transitions = [{
        "from_beat": "HOOK", "to_beat": "BUILD", "mechanism": "css",
        "name": "crossfade", "duration_s": 0.5, "easing": "power2.inOut",
        "why": "x",
    }]
    state_a = _plan_state(tmp_path, transitions=transitions)
    state_a["compose"]["index_html"] = "<html><body>VARIANT_A</body></html>"
    state_b = _plan_state(tmp_path / "alt", transitions=transitions)
    state_b["compose"]["index_html"] = "<html><body>VARIANT_B</body></html>"
    assert _cache_key(state_a) != _cache_key(state_b)


# HOM-259: explicit state-first coverage. `_plan_state` exercises the
# disk-fallback path through `_load_root_html`; this builder pins the
# body in state instead so the new state-first branch is also covered
# end-to-end through the node body.
def _state_first_plan_state(
    tmp_path: Path, transitions: list[dict], beats=None
) -> dict:
    if beats is None:
        beats = [
            {"beat": "HOOK", "duration_s": 3.0},
            {"beat": "BUILD", "duration_s": 4.0},
            {"beat": "PAYOFF", "duration_s": 5.0},
        ]
    return {
        "compose": {
            # Disk path intentionally points at a nonexistent file — the
            # state-first read must satisfy the node without falling
            # back to disk. _atomic_write_text would explode on a
            # nonexistent parent dir on save, so we point at tmp_path
            # (which exists) but use a filename that's not on disk yet.
            "index_html_path": str(tmp_path / "ghost.html"),
            "index_html": _scaffolded_index_with_shim(),
            "plan": {"beats": beats, "transitions": transitions},
        },
    }


def test_node_authors_css_block_from_state_index_html(tmp_path):
    """HOM-259: state-first path produces the same compose.index_html
    body update as the disk-fallback path. The dual-write to disk is
    best-effort (its target may not exist); what matters for downstream
    is the body returned in state."""
    transitions = [{
        "from_beat": "HOOK", "to_beat": "BUILD", "mechanism": "css",
        "name": "crossfade", "duration_s": 0.5, "easing": "power2.inOut",
        "why": "soft",
    }]
    state = _state_first_plan_state(tmp_path, transitions=transitions)
    update = p4_transitions_node(state)
    assert "errors" not in update
    body = update["compose"].get("index_html")
    assert isinstance(body, str) and body, (
        "state-first path must return patched index_html body in compose.index_html"
    )
    assert _BEGIN_MARKER in body
    assert _SHIM_BEGIN_MARKER not in body
    assert "root.fromTo('#scene-build'" in body
