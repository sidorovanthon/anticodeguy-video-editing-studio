"""Unit tests for p4_assemble_index node — Pattern A retrofit + v4 shim."""

from __future__ import annotations

from pathlib import Path

from edit_episode_graph.nodes.p4_assemble_index import (
    _SHIM_BEGIN_MARKER,
    _SHIM_END_MARKER,
    _TOKENS_BEGIN_MARKER,
    _TOKENS_END_MARKER,
    _ensure_inlined_script_iife,
    _ensure_scene_clip_class,
    _reconcile_root_data_duration,
    assemble_html,
    build_root_tokens_block,
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
        f'<div id="scene-{scene_id}" class="scene clip" '
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


def test_build_visibility_shim_unpauses_child_timeline_before_nesting():
    """HOM-164 regression: per-scene `gsap.timeline({ paused: true })` must
    have its `paused` flag cleared before being added to root, otherwise the
    HF runtime's `seek()` of `__timelines["root"]` does not advance the
    child and every scene stays at the fromTo from-state — Phase 4 black
    screen. Verified end-to-end against `npx hyperframes snapshot` in a
    bare `hyperframes init` scaffold.
    """
    shim = build_visibility_shim(["hook", "payoff"], [0.0, 3.0])
    assert shim is not None
    # The shim must call `paused(false)` on the child timeline AND it must
    # appear before the `root.add(...)` call so the unpause takes effect for
    # the immediate-render of any `fromTo` initial values.
    assert "sceneTl.paused(false)" in shim
    paused_pos = shim.index("sceneTl.paused(false)")
    add_pos = shim.index("root.add(sceneTl,")
    assert paused_pos < add_pos, (
        "sceneTl.paused(false) must precede root.add(sceneTl, ...) — "
        "GSAP child-paused-under-parent.seek() bug, see HOM-164"
    )


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


# ---- HOM-142: scene `class="clip"` enforcement ----

def test_ensure_scene_clip_class_appends_to_existing_class():
    frag = (
        '<div id="scene-hook" class="scene" data-start="0" data-duration="3">'
        "<style></style></div>"
    )
    out = _ensure_scene_clip_class(frag)
    assert 'class="scene clip"' in out


def test_ensure_scene_clip_class_is_idempotent():
    frag = (
        '<div id="scene-hook" class="scene clip" data-start="0" data-duration="3">'
        "</div>"
    )
    assert _ensure_scene_clip_class(frag) == frag


def test_ensure_scene_clip_class_handles_single_quoted_attrs():
    frag = (
        "<div id='scene-hook' class='scene' data-start='0' data-duration='3'>"
        "</div>"
    )
    out = _ensure_scene_clip_class(frag)
    assert "class='scene clip'" in out


def test_ensure_scene_clip_class_injects_when_no_class_attr():
    frag = '<div id="scene-hook" data-start="0" data-duration="3"></div>'
    out = _ensure_scene_clip_class(frag)
    assert 'class="clip"' in out
    assert 'id="scene-hook"' in out


def test_assemble_html_injects_clip_class_into_fragments_missing_it(tmp_path):
    """Defensive post-process: brief drift shouldn't leave lint-broken HTML."""
    bad_frag = (
        '<div id="scene-hook" class="scene" data-start="0" data-duration="3">'
        "<style>#scene-hook { position: absolute; }</style>"
        '<div class="scene-content">x</div></div>'
    )
    out = assemble_html(
        root_html=SCAFFOLDED_INDEX,
        beat_html_fragments=[("hook", bad_frag)],
        captions_html=None,
    )
    assert 'class="scene clip"' in out


# ---- HOM-143: IIFE wrapping for inlined script blocks ----

def test_ensure_iife_wraps_unwrapped_script_body():
    frag = (
        '<div id="scene-hook"><script>\n'
        "  const tl = gsap.timeline({ paused: true });\n"
        "  window.__sceneTimelines['hook'] = tl;\n"
        "</script></div>"
    )
    out = _ensure_inlined_script_iife(frag)
    assert "(function() {" in out
    assert "})();" in out
    # Original body is preserved inside the wrapper.
    assert "const tl = gsap.timeline({ paused: true });" in out


def test_ensure_iife_idempotent_when_already_wrapped():
    body = (
        "\n    (function() {\n"
        "      const tl = gsap.timeline({ paused: true });\n"
        "    })();\n  "
    )
    frag = f"<div><script>{body}</script></div>"
    assert _ensure_inlined_script_iife(frag) == frag


def test_ensure_iife_idempotent_for_arrow_iife():
    frag = "<div><script>(() => { const tl = 1; })();</script></div>"
    assert _ensure_inlined_script_iife(frag) == frag


def test_ensure_iife_idempotent_for_defensive_leading_semicolon():
    """Defensive `;(function(){…})()` IIFEs must be recognised as already wrapped."""
    frag = "<div><script>;(function() { const tl = 1; })();</script></div>"
    assert _ensure_inlined_script_iife(frag) == frag


def test_ensure_iife_skips_external_script_src():
    frag = '<div><script src="gsap.min.js"></script></div>'
    assert _ensure_inlined_script_iife(frag) == frag


def test_ensure_iife_skips_empty_body():
    frag = "<div><script>   \n</script></div>"
    assert _ensure_inlined_script_iife(frag) == frag


def test_ensure_iife_handles_leading_comments_in_iife_detection():
    """Body that begins with a // comment then an IIFE should not be re-wrapped."""
    frag = (
        "<div><script>\n"
        "// scene timeline\n"
        "(function() { const tl = 1; })();\n"
        "</script></div>"
    )
    assert _ensure_inlined_script_iife(frag) == frag


def test_ensure_iife_wraps_each_script_block_independently():
    frag = (
        "<div>"
        "<script>const tl = 1;</script>"
        "<script>(function() { const tl = 2; })();</script>"
        "<script>const tl = 3;</script>"
        "</div>"
    )
    out = _ensure_inlined_script_iife(frag)
    # Two unwrapped blocks gain wrappers; the middle one is unchanged.
    assert out.count("(function() {") == 3  # middle's existing + 2 new
    assert out.count("})();") == 3


def test_assemble_html_wraps_unwrapped_captions_script(tmp_path):
    """Defensive: brief drift in p4_captions_layer shouldn't collide with
    the scaffold's top-level `const tl`."""
    bad_captions = (
        '<div id="captions-layer"><script>\n'
        "  var tl = gsap.timeline({ paused: true });\n"
        "  window.__captionTimelines['captions'] = tl;\n"
        "</script></div>"
    )
    out = assemble_html(
        root_html=SCAFFOLDED_INDEX,
        beat_html_fragments=[("hook", _pattern_a_fragment("hook"))],
        captions_html=bad_captions,
    )
    captions_idx = out.index('id="captions-layer"')
    body_close_idx = out.index("</body>")
    captions_section = out[captions_idx:body_close_idx]
    assert "(function() {" in captions_section
    assert "var tl = gsap.timeline" in captions_section


def test_assemble_html_wraps_unwrapped_scene_script():
    bad_scene = (
        '<div id="scene-hook" class="scene clip" '
        'data-start="0" data-duration="3" data-track-index="1">'
        "<script>\n"
        "  const tl = gsap.timeline({ paused: true });\n"
        "  window.__sceneTimelines['hook'] = tl;\n"
        "</script></div>"
    )
    out = assemble_html(
        root_html=SCAFFOLDED_INDEX,
        beat_html_fragments=[("hook", bad_scene)],
        captions_html=None,
    )
    scene_idx = out.index('id="scene-hook"')
    end_idx = out.index("p4_assemble_index: end")
    section = out[scene_idx:end_idx]
    assert "(function() {" in section


# ---- HOM-191: design tokens :root block ----

def test_build_root_tokens_block_emits_palette_and_typography():
    block = build_root_tokens_block(
        palette=[
            {"role": "background", "hex": "#1a1614"},
            {"role": "foreground", "hex": "#f4ebdc"},
            {"role": "accent", "hex": "#e8a14a"},
        ],
        typography=[
            {"role": "body", "family": "Inter", "weight": 400},
            {"role": "headline", "family": "Playfair Display", "weight": 600},
        ],
    )
    assert block is not None
    assert _TOKENS_BEGIN_MARKER in block
    assert _TOKENS_END_MARKER in block
    assert ":root {" in block
    assert "--bg: #1a1614;" in block
    assert "--fg: #f4ebdc;" in block
    assert "--accent: #e8a14a;" in block
    assert "--font-body: Inter, sans-serif;" in block
    # Multi-word family must be quoted.
    assert '--font-display: "Playfair Display", sans-serif;' in block


def test_build_root_tokens_block_returns_none_for_unknown_roles():
    """No recognised palette/typography roles → no block, callers omit cleanly."""
    assert (
        build_root_tokens_block(
            palette=[{"role": "exotic", "hex": "#abcdef"}],
            typography=[{"role": "label", "family": "Foo"}],
        )
        is None
    )
    assert build_root_tokens_block(None, None) is None
    assert build_root_tokens_block([], []) is None


def test_build_root_tokens_block_skips_malformed_entries():
    block = build_root_tokens_block(
        palette=[
            "not-a-dict",  # type: ignore[list-item]
            {"role": "background", "hex": "#1a1614"},
            {"role": "background", "hex": "#deadbe"},  # duplicate role — first wins
        ],
        typography=[
            {"role": "body"},  # missing family
            {"role": "body", "family": "Inter"},
        ],
    )
    assert block is not None
    # First-wins dedup on duplicate role.
    assert block.count("--bg:") == 1
    assert "#1a1614" in block
    assert "#deadbe" not in block


def test_assemble_html_injects_tokens_block_when_provided():
    tokens = build_root_tokens_block(
        palette=[{"role": "background", "hex": "#1a1614"}],
        typography=[{"role": "body", "family": "Inter"}],
    )
    out = assemble_html(
        root_html=SCAFFOLDED_INDEX,
        beat_html_fragments=[("hook", _pattern_a_fragment("hook"))],
        captions_html=None,
        tokens_block=tokens,
    )
    assert _TOKENS_BEGIN_MARKER in out
    assert _TOKENS_END_MARKER in out
    assert "--bg: #1a1614;" in out
    # Tokens block sits before the beats (so subsequent rules can reference vars).
    assert out.index(_TOKENS_BEGIN_MARKER) < out.index("p4_assemble_index: beats")


def test_assemble_html_tokens_block_is_idempotent_on_rerun():
    tokens = build_root_tokens_block(
        palette=[{"role": "background", "hex": "#1a1614"}],
        typography=[{"role": "body", "family": "Inter"}],
    )
    once = assemble_html(
        root_html=SCAFFOLDED_INDEX,
        beat_html_fragments=[("hook", _pattern_a_fragment("hook"))],
        captions_html=None,
        tokens_block=tokens,
    )
    twice = assemble_html(
        root_html=once,
        beat_html_fragments=[("hook", _pattern_a_fragment("hook"))],
        captions_html=None,
        tokens_block=tokens,
    )
    assert twice.count(_TOKENS_BEGIN_MARKER) == 1
    assert twice.count(_TOKENS_END_MARKER) == 1


def test_node_writes_tokens_block_from_compose_design(tmp_path):
    """End-to-end: state carries `compose.design.{palette,typography}` →
    `:root { … }` block lands in the assembled `index.html` so
    `p4_scaffold`'s `var(--bg, transparent)` placeholder resolves to the
    DESIGN.md palette without a literal hex (HOM-191 fix).
    """
    state = _plan_state(tmp_path, [("Hook", 3.0)])
    _write_fragment(state, "hook")
    state["compose"]["design"] = {
        "palette": [
            {"role": "background", "hex": "#1a1614"},
            {"role": "foreground", "hex": "#f4ebdc"},
        ],
        "typography": [{"role": "body", "family": "Inter"}],
    }

    update = p4_assemble_index_node(state)
    assert "errors" not in update

    on_disk = Path(state["compose"]["index_html_path"]).read_text(encoding="utf-8")
    assert _TOKENS_BEGIN_MARKER in on_disk
    assert "--bg: #1a1614;" in on_disk
    assert "--fg: #f4ebdc;" in on_disk
    assert "--font-body: Inter, sans-serif;" in on_disk


def test_node_omits_tokens_block_when_design_missing(tmp_path):
    """No `compose.design` → no tokens block injected, no marker pollution."""
    state = _plan_state(tmp_path, [("Hook", 3.0)])
    _write_fragment(state, "hook")
    update = p4_assemble_index_node(state)
    assert "errors" not in update
    on_disk = Path(state["compose"]["index_html_path"]).read_text(encoding="utf-8")
    assert _TOKENS_BEGIN_MARKER not in on_disk
    assert _TOKENS_END_MARKER not in on_disk


def test_node_errors_when_captions_path_missing(tmp_path):
    state = _plan_state(tmp_path, [("Hook", 3.0)])
    _write_fragment(state, "hook")
    state["compose"]["captions_block_path"] = str(tmp_path / "nope.html")
    update = p4_assemble_index_node(state)
    assert update["errors"][0]["node"] == "p4_assemble_index"


# ---- HOM-214: root-timeline scene-position chain + data-duration reconciliation ----


import re as _re  # local alias to avoid colliding with module top imports
import json as _json


_ROOT_SET_OPACITY_RE = _re.compile(
    r"""root\.set\(\s*['"]#scene-['"]\s*\+\s*id\s*,\s*\{\s*opacity\s*:\s*1\s*\}\s*,\s*starts\[i\]\s*\)"""
)
_IDS_LITERAL_RE = _re.compile(r"""var\s+ids\s*=\s*(\[[^\]]*\])\s*;""")
_STARTS_LITERAL_RE = _re.compile(r"""var\s+starts\s*=\s*(\[[^\]]*\])\s*;""")


def _extract_root_positions(html: str) -> list[tuple[str, float]]:
    """Parse the v4 shim's `ids` + `starts` JSON literals → [(scene_id, start), …]
    in plan order. Mirrors what the runtime sees when forEach iterates."""
    ids_match = _IDS_LITERAL_RE.search(html)
    starts_match = _STARTS_LITERAL_RE.search(html)
    assert ids_match, "shim missing `var ids = [...]`"
    assert starts_match, "shim missing `var starts = [...]`"
    ids = _json.loads(ids_match.group(1))
    starts = _json.loads(starts_match.group(1))
    assert len(ids) == len(starts)
    return list(zip(ids, starts))


def test_visibility_shim_anchors_first_scene_at_t_zero():
    """HOM-214: scene-0 MUST receive an explicit `root.set(..., starts[0])`
    so the first-scene-at-t=0 property is observable from the shim alone.
    Before HOM-214 the i==0 case was skipped on the assumption that the
    fragment's `opacity: 1` CSS sufficed; the canonical fixture's empty
    t=0..2 window (Hook absent) made that assumption fail closed."""
    shim = build_visibility_shim(["hook", "build", "payoff"], [0.0, 4.5, 8.2])
    assert shim is not None
    # The shim uses a forEach over `ids` with `'#scene-' + id` selectors and
    # `starts[i]` positions — one set call covers all scenes including i=0.
    # Confirm the call shape exists AND that there is no `if (i > 0)` guard
    # around it any more (HOM-214 dropped that skip).
    assert _ROOT_SET_OPACITY_RE.search(shim), (
        "shim missing root.set('#scene-' + id, { opacity: 1 }, starts[i])"
    )
    # The pre-HOM-214 shim wrapped the set in `if (i > 0) { ... }`. Verify
    # that guard is gone — otherwise scene-0 reverts to relying on fragment CSS.
    assert "if (i > 0)" not in shim, (
        "HOM-214: i==0 skip must be removed; scene-0 needs an explicit anchor"
    )
    # First start position is t=0.
    assert "0.0" in shim or "[0," in shim or "[0]" in shim


def test_visibility_shim_chain_is_monotonic_and_starts_at_zero():
    """First scene at t=0; subsequent positions chain by predecessor duration
    (cumulative). Asserts the structural property the canonical Pattern A
    root-timeline composition mandates."""
    shim = build_visibility_shim(["hook", "build", "payoff"], [0.0, 3.0, 7.5])
    assert shim is not None
    # Extract starts from the embedded JSON literal.
    starts_match = _STARTS_LITERAL_RE.search(shim)
    assert starts_match
    starts = _json.loads(starts_match.group(1))
    assert starts[0] == 0.0, "first scene must anchor at t=0"
    for i in range(1, len(starts)):
        assert starts[i] > starts[i - 1], (
            f"scene positions must be strictly monotonic; got {starts}"
        )


def test_node_root_position_chain_in_assembled_index(tmp_path):
    """End-to-end: parse generated index.html, extract root-timeline
    positions, assert (scene_id, start) sequence matches plan beats with
    first scene at t=0 and chain monotonic by predecessor duration."""
    plan = [("Hook", 3.0), ("Build", 4.5), ("Payoff", 5.0)]
    state = _plan_state(tmp_path, plan)
    _write_fragment(state, "hook")
    _write_fragment(state, "build")
    _write_fragment(state, "payoff")

    update = p4_assemble_index_node(state)
    assert "errors" not in update

    on_disk = Path(state["compose"]["index_html_path"]).read_text(encoding="utf-8")
    positions = _extract_root_positions(on_disk)

    # Order matches plan, ids derived from beat labels.
    assert [sid for sid, _ in positions] == ["hook", "build", "payoff"]
    # First at t=0.
    assert positions[0][1] == 0.0
    # Chain by predecessor duration.
    expected = 0.0
    for (sid, start), (_label, dur) in zip(positions, plan):
        assert start == expected, (
            f"scene {sid!r} expected at t={expected}, got t={start}"
        )
        expected += dur


def test_reconcile_root_data_duration_extends_when_short():
    html = (
        '<div data-composition-id="root" data-width="1920" data-height="1080" '
        'data-duration="22.367"></div>'
    )
    out = _reconcile_root_data_duration(html, 26.5)
    assert 'data-duration="26.5"' in out
    assert "22.367" not in out


def test_reconcile_root_data_duration_is_idempotent_when_already_long_enough():
    html = (
        '<div data-composition-id="root" data-duration="30.0"></div>'
    )
    out = _reconcile_root_data_duration(html, 26.5)
    # Untouched.
    assert out == html


def test_reconcile_root_data_duration_does_not_touch_nested_data_duration():
    """Only the root composition's data-duration should be patched. Sibling
    timed-element data-durations (video/audio/scene divs) live outside the
    root opening tag and must not be rewritten — they map to clip lengths."""
    html = (
        '<div data-composition-id="root" data-duration="22.367">'
        '<video id="el-video" src="final.mp4" data-duration="22.367"></video>'
        '<audio id="el-audio" src="final.mp4" data-duration="22.367"></audio>'
        "</div>"
    )
    out = _reconcile_root_data_duration(html, 26.5)
    # Root patched.
    assert 'data-composition-id="root" data-duration="26.5"' in out
    # Audio/video clip durations untouched (still 22.367 — they map to
    # final.mp4's actual length, which is the correct audio cutoff).
    assert out.count('data-duration="22.367"') == 2


def test_node_reconciles_root_data_duration_to_cumulative(tmp_path):
    """End-to-end: scaffolded root has data-duration='20' (from the test
    fixture's `SCAFFOLDED_INDEX`); plan cumulative is 12.5 (3+4.5+5).
    20 >= 12.5 → no reconciliation. Then re-scaffold with shorter root
    duration and verify it grows."""
    state = _plan_state(tmp_path, [("Hook", 3.0), ("Build", 4.5), ("Payoff", 5.0)])
    _write_fragment(state, "hook")
    _write_fragment(state, "build")
    _write_fragment(state, "payoff")

    update = p4_assemble_index_node(state)
    assert "errors" not in update
    on_disk = Path(state["compose"]["index_html_path"]).read_text(encoding="utf-8")
    # 20 > 12.5 → unchanged.
    assert 'data-duration="20"' in on_disk

    # Now write a short-rooted index and re-run.
    short_index = (
        '<!doctype html><html><body>'
        '<div data-composition-id="root" data-width="1920" data-height="1080" '
        'data-duration="5.0">'
        '<video id="el-video" src="final.mp4" data-duration="5.0"></video>'
        '</div></body></html>'
    )
    Path(state["compose"]["index_html_path"]).write_text(short_index, encoding="utf-8")
    update2 = p4_assemble_index_node(state)
    assert "errors" not in update2
    on_disk2 = Path(state["compose"]["index_html_path"]).read_text(encoding="utf-8")
    # Cumulative 12.5 > 5.0 → reconciled.
    assert 'data-composition-id="root" data-width="1920" data-height="1080" data-duration="12.5"' in on_disk2
    # The clip-level data-duration on <video> is left alone.
    assert '<video id="el-video" src="final.mp4" data-duration="5.0">' in on_disk2


def test_assemble_html_skips_reconciliation_when_cumulative_end_s_none():
    """Backwards compatible — callers that don't pass cumulative_end_s
    (older tests, hand-written callers) leave data-duration alone."""
    out = assemble_html(
        root_html=SCAFFOLDED_INDEX,
        beat_html_fragments=[("hook", _pattern_a_fragment("hook"))],
        captions_html=None,
        cumulative_end_s=None,
    )
    assert 'data-duration="20"' in out
