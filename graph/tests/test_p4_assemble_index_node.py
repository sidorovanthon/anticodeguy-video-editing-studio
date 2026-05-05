"""Unit tests for p4_assemble_index node — Pattern A retrofit + v4 shim."""

from __future__ import annotations

from pathlib import Path

from edit_episode_graph.nodes.p4_assemble_index import (
    _SHIM_BEGIN_MARKER,
    _SHIM_END_MARKER,
    assemble_html,
    build_visibility_shim,
    p4_assemble_index_node,
)


SCAFFOLDED_INDEX = """\
<!doctype html>
<html>
  <head><meta name="viewport" content="width=1920, height=1080" /></head>
  <body>
    <div data-composition-id="root" data-width="1920" data-height="1080" data-duration="20">
      <video id="el-video" src="final.mp4" muted playsinline></video>
      <audio id="el-audio" src="final.mp4"></audio>
    </div>
  </body>
</html>
"""


# Pattern A fragment per spec §"Per-scene fragment shape" — direct <div>, NOT
# wrapped in <template>, no data-composition-id (root has it).
def _pattern_a_fragment(scene_id: str, body: str = "X") -> str:
    return (
        f'<div id="scene-{scene_id}" class="scene" '
        f'data-start="0" data-duration="3" data-track-index="1">'
        f"<style>#scene-{scene_id} {{ position: absolute; }}</style>"
        f'<div class="scene-content">{body}</div>'
        f"</div>"
    )


# ---- pure assemble_html ----

def test_assemble_html_injects_beats_before_body_close():
    out = assemble_html(
        root_html=SCAFFOLDED_INDEX,
        beat_html_fragments=[
            ("hook", _pattern_a_fragment("hook", "A")),
            ("payoff", _pattern_a_fragment("payoff", "B")),
        ],
        captions_html=None,
    )
    assert "<!-- beat: hook -->" in out
    assert "<!-- beat: payoff -->" in out
    assert 'id="scene-hook"' in out
    assert 'id="scene-payoff"' in out
    assert "p4_assemble_index: end" in out
    assert out.index("p4_assemble_index: end") < out.index("</body>")
    assert 'data-composition-id="root"' in out


def test_assemble_html_inlines_pattern_a_fragments_as_is():
    """No <template> strip — Pattern A fragments are direct <div> already."""
    frag = _pattern_a_fragment("hook", "verbatim")
    out = assemble_html(
        root_html=SCAFFOLDED_INDEX,
        beat_html_fragments=[("hook", frag)],
        captions_html=None,
    )
    # Fragment appears verbatim — no inner-div extraction
    assert frag in out


def test_assemble_html_injects_captions_when_provided():
    out = assemble_html(
        root_html=SCAFFOLDED_INDEX,
        beat_html_fragments=[("hook", _pattern_a_fragment("hook"))],
        captions_html='<div data-composition-id="captions">C</div>',
    )
    assert "p4_assemble_index: captions" in out
    assert 'data-composition-id="captions"' in out


def test_assemble_html_is_idempotent_on_rerun():
    once = assemble_html(
        root_html=SCAFFOLDED_INDEX,
        beat_html_fragments=[("hook", _pattern_a_fragment("hook"))],
        captions_html=None,
    )
    twice = assemble_html(
        root_html=once,
        beat_html_fragments=[("hook", _pattern_a_fragment("hook"))],
        captions_html=None,
    )
    assert twice.count("p4_assemble_index: beats") == 1
    assert twice.count("p4_assemble_index: end") == 1


def test_assemble_html_recovers_from_partial_injection():
    partial = SCAFFOLDED_INDEX.replace(
        "</body>",
        "<!-- p4_assemble_index: beats -->\n<!-- beat: HALF -->\n<div>half</div>\n</body>",
    )
    out = assemble_html(
        root_html=partial,
        beat_html_fragments=[("hook", _pattern_a_fragment("hook", "fresh"))],
        captions_html=None,
    )
    assert out.count("p4_assemble_index: beats") == 1
    assert out.count("p4_assemble_index: end") == 1
    assert "HALF" not in out
    assert "fresh" in out


def test_assemble_html_replaces_prior_injection_with_new_beats():
    once = assemble_html(
        root_html=SCAFFOLDED_INDEX,
        beat_html_fragments=[("old", _pattern_a_fragment("old"))],
        captions_html=None,
    )
    twice = assemble_html(
        root_html=once,
        beat_html_fragments=[("new", _pattern_a_fragment("new"))],
        captions_html=None,
    )
    assert "scene-old" not in twice
    assert "scene-new" in twice


# ---- v4 visibility shim ----

def test_build_visibility_shim_emits_markers_and_payload():
    shim = build_visibility_shim(["hook", "build", "payoff"], [0.0, 4.5, 8.2])
    assert shim is not None
    assert _SHIM_BEGIN_MARKER in shim
    assert _SHIM_END_MARKER in shim
    # ids + starts injected as JSON literals
    assert '"hook"' in shim
    assert '"build"' in shim
    assert '"payoff"' in shim
    assert "4.5" in shim
    assert "8.2" in shim
    # nests scene timelines + sets opacity for non-first scenes
    assert "__sceneTimelines" in shim
    assert "__timelines" in shim
    assert "opacity" in shim


def test_build_visibility_shim_returns_none_for_empty_scenes():
    assert build_visibility_shim([], []) is None


def test_assemble_html_appends_shim_between_markers():
    shim = build_visibility_shim(["hook", "payoff"], [0.0, 3.0])
    out = assemble_html(
        root_html=SCAFFOLDED_INDEX,
        beat_html_fragments=[
            ("hook", _pattern_a_fragment("hook")),
            ("payoff", _pattern_a_fragment("payoff")),
        ],
        captions_html=None,
        visibility_shim=shim,
    )
    assert _SHIM_BEGIN_MARKER in out
    assert _SHIM_END_MARKER in out
    # shim sits inside body, after end-of-beats marker
    assert out.index(_SHIM_BEGIN_MARKER) > out.index("p4_assemble_index: end")
    assert out.index(_SHIM_END_MARKER) < out.index("</body>")


def test_assemble_html_shim_is_idempotent_on_rerun():
    shim = build_visibility_shim(["hook"], [0.0])
    once = assemble_html(
        root_html=SCAFFOLDED_INDEX,
        beat_html_fragments=[("hook", _pattern_a_fragment("hook"))],
        captions_html=None,
        visibility_shim=shim,
    )
    twice = assemble_html(
        root_html=once,
        beat_html_fragments=[("hook", _pattern_a_fragment("hook"))],
        captions_html=None,
        visibility_shim=shim,
    )
    assert twice.count(_SHIM_BEGIN_MARKER) == 1
    assert twice.count(_SHIM_END_MARKER) == 1


# ---- node: source-of-truth = compose.plan.beats[] + on-disk fragments ----

def _plan_state(tmp_path: Path, beats: list[tuple[str, float]]) -> dict:
    """Build a minimal state with scaffolded index + plan.beats."""
    hf_dir = tmp_path / "hyperframes"
    hf_dir.mkdir()
    index = hf_dir / "index.html"
    index.write_text(SCAFFOLDED_INDEX, encoding="utf-8")
    return {
        "compose": {
            "index_html_path": str(index),
            "plan": {
                "beats": [
                    {"beat": label, "duration_s": dur} for label, dur in beats
                ],
            },
        },
    }


def _write_fragment(state: dict, scene_id: str, body: str = "x") -> Path:
    hf_dir = Path(state["compose"]["index_html_path"]).parent
    comp_dir = hf_dir / "compositions"
    comp_dir.mkdir(exist_ok=True)
    p = comp_dir / f"{scene_id}.html"
    p.write_text(_pattern_a_fragment(scene_id, body), encoding="utf-8")
    return p


def test_node_skips_when_no_plan_beats():
    update = p4_assemble_index_node({"compose": {"index_html_path": "/x/index.html"}})
    assemble = update["compose"]["assemble"]
    assert assemble["skipped"] is True
    reason = assemble["skip_reason"].lower()
    assert "plan" in reason or "beats" in reason


def test_node_errors_when_index_html_missing(tmp_path):
    state = {
        "compose": {
            "index_html_path": str(tmp_path / "missing.html"),
            "plan": {"beats": [{"beat": "Hook", "duration_s": 3.0}]},
        },
    }
    update = p4_assemble_index_node(state)
    assert update["errors"][0]["node"] == "p4_assemble_index"


def test_node_inlines_fragments_in_plan_order(tmp_path):
    state = _plan_state(tmp_path, [("Hook", 3.0), ("Build", 4.0), ("Payoff", 5.0)])
    _write_fragment(state, "hook", "h-body")
    _write_fragment(state, "build", "b-body")
    _write_fragment(state, "payoff", "p-body")

    update = p4_assemble_index_node(state)
    assert "errors" not in update
    assemble = update["compose"]["assemble"]
    assert assemble["beat_names"] == ["hook", "build", "payoff"]

    on_disk = Path(state["compose"]["index_html_path"]).read_text(encoding="utf-8")
    assert on_disk.index("h-body") < on_disk.index("b-body") < on_disk.index("p-body")
    assert 'id="scene-hook"' in on_disk
    assert 'id="scene-payoff"' in on_disk


def test_node_aggregates_missing_scenes_into_single_skip(tmp_path):
    state = _plan_state(tmp_path, [("Hook", 3.0), ("Build", 4.0), ("Payoff", 5.0)])
    # Only the middle one exists; first and last are missing
    _write_fragment(state, "build", "b-body")

    update = p4_assemble_index_node(state)
    assemble = update["compose"]["assemble"]
    assert assemble["skipped"] is True
    reason = assemble["skip_reason"]
    assert "missing scenes" in reason
    # Both gaps surfaced — operator sees all of them at once
    assert "hook" in reason
    assert "payoff" in reason
    assert "build" not in reason


def test_node_emits_v4_shim_with_cumulative_starts(tmp_path):
    state = _plan_state(tmp_path, [("Hook", 3.0), ("Build", 4.5), ("Payoff", 5.0)])
    _write_fragment(state, "hook")
    _write_fragment(state, "build")
    _write_fragment(state, "payoff")

    update = p4_assemble_index_node(state)
    assert "errors" not in update
    on_disk = Path(state["compose"]["index_html_path"]).read_text(encoding="utf-8")

    assert _SHIM_BEGIN_MARKER in on_disk
    assert _SHIM_END_MARKER in on_disk
    # Cumulative starts: 0.0, 3.0, 7.5
    assert "3.0" in on_disk
    assert "7.5" in on_disk
    assert '"hook"' in on_disk
    assert '"build"' in on_disk
    assert '"payoff"' in on_disk


def test_node_rerun_does_not_double_shim(tmp_path):
    state = _plan_state(tmp_path, [("Hook", 3.0), ("Payoff", 5.0)])
    _write_fragment(state, "hook")
    _write_fragment(state, "payoff")

    p4_assemble_index_node(state)
    p4_assemble_index_node(state)

    on_disk = Path(state["compose"]["index_html_path"]).read_text(encoding="utf-8")
    assert on_disk.count(_SHIM_BEGIN_MARKER) == 1
    assert on_disk.count(_SHIM_END_MARKER) == 1
    assert on_disk.count("p4_assemble_index: beats") == 1


def test_node_supports_captions_path(tmp_path):
    state = _plan_state(tmp_path, [("Hook", 3.0)])
    _write_fragment(state, "hook")
    captions = tmp_path / "captions.html"
    captions.write_text('<div data-composition-id="captions">C</div>', encoding="utf-8")
    state["compose"]["captions_block_path"] = str(captions)

    update = p4_assemble_index_node(state)
    assert "errors" not in update
    assert update["compose"]["assemble"]["captions_included"] is True
    on_disk = Path(state["compose"]["index_html_path"]).read_text(encoding="utf-8")
    assert 'data-composition-id="captions"' in on_disk


def test_node_errors_when_captions_path_missing(tmp_path):
    state = _plan_state(tmp_path, [("Hook", 3.0)])
    _write_fragment(state, "hook")
    state["compose"]["captions_block_path"] = str(tmp_path / "nope.html")
    update = p4_assemble_index_node(state)
    assert update["errors"][0]["node"] == "p4_assemble_index"
