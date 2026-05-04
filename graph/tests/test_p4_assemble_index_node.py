"""Unit tests for p4_assemble_index node — assembly logic + skip + errors."""

from __future__ import annotations

from pathlib import Path

from edit_episode_graph.nodes.p4_assemble_index import (
    assemble_html,
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


def test_assemble_html_injects_beats_before_body_close():
    out = assemble_html(
        root_html=SCAFFOLDED_INDEX,
        beat_html_fragments=[
            ("HOOK", '<div data-composition-id="hook">A</div>'),
            ("PAYOFF", '<div data-composition-id="payoff">B</div>'),
        ],
        captions_html=None,
    )
    assert "<!-- beat: HOOK -->" in out
    assert "<!-- beat: PAYOFF -->" in out
    assert 'data-composition-id="hook"' in out
    assert "p4_assemble_index: end" in out
    # injected before </body>, not after
    assert out.index("p4_assemble_index: end") < out.index("</body>")
    # scaffold content preserved
    assert 'data-composition-id="root"' in out


def test_assemble_html_injects_captions_when_provided():
    out = assemble_html(
        root_html=SCAFFOLDED_INDEX,
        beat_html_fragments=[("X", "<div>x</div>")],
        captions_html='<div data-composition-id="captions">C</div>',
    )
    assert "p4_assemble_index: captions" in out
    assert 'data-composition-id="captions"' in out


def test_assemble_html_is_idempotent_on_rerun():
    once = assemble_html(
        root_html=SCAFFOLDED_INDEX,
        beat_html_fragments=[("A", "<div>1</div>")],
        captions_html=None,
    )
    twice = assemble_html(
        root_html=once,
        beat_html_fragments=[("A", "<div>1</div>")],
        captions_html=None,
    )
    # Only one injection block, not two stacked
    assert twice.count("p4_assemble_index: beats") == 1
    assert twice.count("p4_assemble_index: end") == 1


def test_assemble_html_recovers_from_partial_injection():
    """If a prior write was interrupted (begin marker without end marker),
    the next assembly drops the half-written block and injects fresh content
    rather than doubling up."""
    partial = SCAFFOLDED_INDEX.replace(
        "</body>",
        "<!-- p4_assemble_index: beats -->\n<!-- beat: HALF -->\n<div>half</div>\n</body>",
    )
    out = assemble_html(
        root_html=partial,
        beat_html_fragments=[("FRESH", "<div>fresh</div>")],
        captions_html=None,
    )
    assert out.count("p4_assemble_index: beats") == 1
    assert out.count("p4_assemble_index: end") == 1
    assert "HALF" not in out
    assert "FRESH" in out


def test_assemble_html_replaces_prior_injection_with_new_beats():
    once = assemble_html(
        root_html=SCAFFOLDED_INDEX,
        beat_html_fragments=[("OLD", "<div>old</div>")],
        captions_html=None,
    )
    twice = assemble_html(
        root_html=once,
        beat_html_fragments=[("NEW", "<div>new</div>")],
        captions_html=None,
    )
    assert "OLD" not in twice
    assert "NEW" in twice


def test_node_skips_when_no_beats():
    update = p4_assemble_index_node({"compose": {"index_html_path": "/x/index.html"}})
    assemble = update["compose"]["assemble"]
    assert assemble["skipped"] is True
    assert "no beats" in assemble["skip_reason"]


def test_node_errors_when_index_html_missing(tmp_path):
    beat = tmp_path / "hook.html"
    beat.write_text("<div>hook</div>", encoding="utf-8")
    state = {
        "compose": {
            "index_html_path": str(tmp_path / "missing.html"),
            "beats": [{"name": "HOOK", "html_path": str(beat)}],
        },
    }
    update = p4_assemble_index_node(state)
    assert update["errors"][0]["node"] == "p4_assemble_index"


def test_node_writes_assembled_html(tmp_path):
    index = tmp_path / "index.html"
    index.write_text(SCAFFOLDED_INDEX, encoding="utf-8")
    hook = tmp_path / "hook.html"
    hook.write_text('<div data-composition-id="hook">H</div>', encoding="utf-8")
    captions = tmp_path / "captions.html"
    captions.write_text('<div data-composition-id="captions">C</div>', encoding="utf-8")
    state = {
        "compose": {
            "index_html_path": str(index),
            "beats": [{"name": "HOOK", "html_path": str(hook)}],
            "captions_block_path": str(captions),
        },
    }
    update = p4_assemble_index_node(state)
    assert "errors" not in update
    assemble = update["compose"]["assemble"]
    assert assemble["beat_names"] == ["HOOK"]
    assert assemble["captions_included"] is True
    on_disk = index.read_text(encoding="utf-8")
    assert 'data-composition-id="hook"' in on_disk
    assert 'data-composition-id="captions"' in on_disk


def test_node_errors_when_beat_html_missing(tmp_path):
    index = tmp_path / "index.html"
    index.write_text(SCAFFOLDED_INDEX, encoding="utf-8")
    state = {
        "compose": {
            "index_html_path": str(index),
            "beats": [{"name": "GHOST", "html_path": str(tmp_path / "ghost.html")}],
        },
    }
    update = p4_assemble_index_node(state)
    assert update["errors"][0]["node"] == "p4_assemble_index"
    assert "html_path does not exist" in update["errors"][0]["message"]
