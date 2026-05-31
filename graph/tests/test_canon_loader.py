"""Unit tests for the runtime canon-section loader (HOM-377, spec §9).

Covers the three contracts:
  * anchor-based extraction (heading ``startswith`` + sub-list-item by leading
    text); index/line extraction is never offered;
  * fail-loud — missing/ambiguous heading, missing list item, missing file,
    and a renamed section at ``verify_anchors`` time all raise
    :class:`CanonAnchorMissing`;
  * cache-correct — ``canon_fingerprint`` flips when a consumed section is
    edited and stays put for a node that does not consume it.

The hermetic tests build a fixture skill tree under ``tmp_path`` and point the
``HOMESTUDIO_CANON_ROOT_*`` env overrides at it. One test resolves the real
manifest against the *live* skills — that is the integration check the whole
ticket exists to guarantee (an upstream rename turns it red).
"""

from __future__ import annotations

import pytest

from edit_episode_graph import _canon_loader as cl


# --------------------------------------------------------------------------- #
# Fixture skill tree
# --------------------------------------------------------------------------- #

_HF_SKILL_MD = """\
# HyperFrames

## Layout Before Animation

Lay out the static frame first.

### The process

1. Place elements at their rest positions.
2. The CSS position is the ground truth.

## Rules (Non-Negotiable)

- No `repeat: -1` in any tween.
- Every clip needs `data-start`.

## Scene Transitions (Non-Negotiable)

NEVER use exit animations except on the final scene.

## Animation Guardrails

At least 3 distinct eases per scene.

## Data Attributes

Trailing section — proves the level-aware boundary stops before here.
"""

_HF_MOTION_MD = """\
# Motion Principles

## Guardrails

Some guardrails.

## Load-Bearing GSAP Rules

- Prefer `tl.fromTo()` over `tl.from()` inside `.clip` scenes.
- Ambient pulses must attach to the seekable `tl`.

These are the exact rules — don't summarize or shorten them.
"""

_HF_CAPTIONS_MD = """\
# Captions

## Positioning

Use `position: absolute`, never `left: 50%`.

## Text Overflow Prevention

Use `window.__hyperframes.fitTextFontSize`.

## Caption Exit Guarantee

Every group MUST `tl.set(... { opacity: 0, visibility: "hidden" }, group.end)`.

## Constraints

Deterministic — no `Math.random()`, no `Date.now()`.
"""

_VU_SKILL_MD = """\
# Video Use

## Hard Rules (production correctness — non-negotiable)

6. Cut on word boundaries.
7. Padding working window: 30-200ms.

## The process

1. **Inventory.** `ffprobe` every source, then transcribe.
2. **Pre-scan for problems.** One pass to note slips.
3. **Converse.** Describe what you see in plain English.
4. **Propose strategy.** 4-8 sentences. Wait for confirmation.
5. **Execute.** Produce `edl.json`.
7. **Self-eval (before showing the user).** Run timeline_view on the output.
   - Visual discontinuity at the cut.
   - Waveform spike at the boundary.

   Also sample first 2s and last 2s.
8. **Iterate + persist.** Append to `project.md`.

## Cut craft (techniques)

- **Audio-first.** Candidate cuts from word boundaries.
- **Preserve peaks.** Laughs, punchlines.

## Color grade (when requested)

Image/CDL direction only — not audio or codec.
"""


def _write_fixture_skills(tmp_path):
    hf = tmp_path / "hyperframes"
    (hf / "references").mkdir(parents=True)
    (hf / "SKILL.md").write_text(_HF_SKILL_MD, encoding="utf-8")
    (hf / "references" / "motion-principles.md").write_text(_HF_MOTION_MD, encoding="utf-8")
    (hf / "references" / "captions.md").write_text(_HF_CAPTIONS_MD, encoding="utf-8")
    vu = tmp_path / "video-use"
    vu.mkdir(parents=True)
    (vu / "SKILL.md").write_text(_VU_SKILL_MD, encoding="utf-8")
    return hf, vu


@pytest.fixture
def fixture_skills(tmp_path, monkeypatch):
    hf, vu = _write_fixture_skills(tmp_path)
    monkeypatch.setenv("HOMESTUDIO_CANON_ROOT_HYPERFRAMES", str(hf))
    monkeypatch.setenv("HOMESTUDIO_CANON_ROOT_VIDEO_USE", str(vu))
    return tmp_path


# --------------------------------------------------------------------------- #
# Section extraction
# --------------------------------------------------------------------------- #


def test_resolve_whole_section_includes_heading_and_subheadings(fixture_skills):
    block = cl.load_skill_section("hyperframes", "SKILL.md", "## Layout Before Animation")
    assert block.startswith("## Layout Before Animation")
    # ### subheading stays in (level-aware: only stops at next ## or #)
    assert "### The process" in block
    assert "The CSS position is the ground truth." in block
    # bounded before the next ## section
    assert "## Data Attributes" not in block
    assert "Trailing section" not in block


def test_startswith_match_tolerates_heading_suffix(fixture_skills):
    # Anchor is a prefix of the full heading text.
    block = cl.load_skill_section("hyperframes", "SKILL.md", "## Rules (Non-Negotiable)")
    assert "No `repeat: -1`" in block


def test_missing_heading_raises(fixture_skills):
    with pytest.raises(cl.CanonAnchorMissing) as ei:
        cl.load_skill_section("hyperframes", "SKILL.md", "## Nonexistent Section")
    assert "heading not found" in str(ei.value)


def test_ambiguous_heading_raises(tmp_path, monkeypatch):
    hf = tmp_path / "hyperframes"
    hf.mkdir()
    (hf / "SKILL.md").write_text(
        "## Duplicated Heading\n\nfirst\n\n## Duplicated Heading\n\nsecond\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOMESTUDIO_CANON_ROOT_HYPERFRAMES", str(hf))
    with pytest.raises(cl.CanonAnchorMissing) as ei:
        cl.load_skill_section("hyperframes", "SKILL.md", "## Duplicated Heading")
    assert "ambiguous" in str(ei.value)


def test_missing_file_raises(fixture_skills):
    with pytest.raises(cl.CanonAnchorMissing) as ei:
        cl.load_skill_section("hyperframes", "references/nope.md", "## Whatever Heading")
    assert "file not found" in str(ei.value)


@pytest.mark.parametrize("anchor", ["## ab", "## abcdef"])
def test_too_short_anchor_is_programming_error(fixture_skills, anchor):
    # Both are below _MIN_ANCHOR_TEXT (8): "ab"=2, "abcdef"=6. The 6-char case
    # would have passed under the prior min of 4 — guards the HOM-377 bump.
    with pytest.raises(ValueError):
        cl.load_skill_section("hyperframes", "SKILL.md", anchor)


def test_anchor_without_heading_marker_is_programming_error(fixture_skills):
    with pytest.raises(ValueError):
        cl.load_skill_section("hyperframes", "SKILL.md", "Layout Before Animation")


# --------------------------------------------------------------------------- #
# Sub-list-item extraction (by leading text, never index)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "item,expect_first,expect_absent",
    [
        ("Inventory", "1. **Inventory.**", "2. **Pre-scan"),
        ("Pre-scan", "2. **Pre-scan for problems.**", "3. **Converse"),
        ("Propose strategy", "4. **Propose strategy.**", "5. **Execute"),
    ],
)
def test_list_item_extraction(fixture_skills, item, expect_first, expect_absent):
    block = cl.load_skill_section(
        "video-use", "SKILL.md", "## The process", item=item
    )
    assert block.lstrip().startswith(expect_first)
    assert expect_absent not in block


def test_list_item_captures_indented_continuation(fixture_skills):
    block = cl.load_skill_section(
        "video-use", "SKILL.md", "## The process", item="Self-eval"
    )
    assert block.lstrip().startswith("7. **Self-eval")
    # nested sub-bullets + the indented paragraph are part of the item
    assert "Waveform spike at the boundary." in block
    assert "Also sample first 2s and last 2s." in block
    # stops at the next top-level numbered item
    assert "8. **Iterate" not in block


def test_missing_list_item_raises(fixture_skills):
    with pytest.raises(cl.CanonAnchorMissing) as ei:
        cl.load_skill_section(
            "video-use", "SKILL.md", "## The process", item="Nonexistent step"
        )
    assert "list item not found" in str(ei.value)


# --------------------------------------------------------------------------- #
# verify_anchors — fail-loud on rename
# --------------------------------------------------------------------------- #


def test_verify_anchors_passes_then_fails_after_rename(tmp_path, monkeypatch):
    hf, _vu = _write_fixture_skills(tmp_path)
    monkeypatch.setenv("HOMESTUDIO_CANON_ROOT_HYPERFRAMES", str(hf))
    refs = [
        cl.CanonRef("gsap", "hyperframes", "references/motion-principles.md", "## Load-Bearing GSAP Rules"),
    ]
    # Resolves cleanly against the fixture.
    cl.verify_anchors(refs)

    # Rename the section upstream — verify must now hard-fail.
    motion = hf / "references" / "motion-principles.md"
    motion.write_text(
        _HF_MOTION_MD.replace("## Load-Bearing GSAP Rules", "## Renamed GSAP Section"),
        encoding="utf-8",
    )
    with pytest.raises(cl.CanonAnchorMissing):
        cl.verify_anchors(refs)


# --------------------------------------------------------------------------- #
# canon_fingerprint — invalidates exactly the consuming node
# --------------------------------------------------------------------------- #


def test_canon_edit_invalidates_only_the_consuming_node(fixture_skills):
    hf = fixture_skills / "hyperframes"

    # p4_beat consumes hyperframes/motion-principles §Load-Bearing GSAP Rules.
    # p3_strategy consumes video-use sections only.
    beat_before = cl.canon_fingerprint("p4_beat")
    strategy_before = cl.canon_fingerprint("p3_strategy")

    motion = hf / "references" / "motion-principles.md"
    motion.write_text(
        _HF_MOTION_MD.replace(
            "Ambient pulses must attach to the seekable `tl`.",
            "Ambient pulses must attach to the seekable `tl` (EDITED).",
        ),
        encoding="utf-8",
    )

    beat_after = cl.canon_fingerprint("p4_beat")
    strategy_after = cl.canon_fingerprint("p3_strategy")

    assert beat_after != beat_before, "p4_beat fingerprint must flip on a canon edit it consumes"
    assert strategy_after == strategy_before, (
        "p3_strategy consumes no hyperframes canon — its fingerprint must be stable"
    )


def test_load_canon_blocks_keyed_by_ref_key(fixture_skills):
    blocks = cl.load_canon_blocks("p4_captions_layer")
    assert set(blocks) == {
        "caption_exit_guarantee",
        "text_overflow_prevention",
        "positioning",
        "constraints",
    }
    assert blocks["positioning"].startswith("## Positioning")


def test_empty_node_fingerprint_is_stable_constant(fixture_skills):
    assert cl.canon_fingerprint("node_with_no_anchors") == cl.canon_fingerprint("another_empty")


# --------------------------------------------------------------------------- #
# Live-canon integration — the guarantee the whole ticket exists for
# --------------------------------------------------------------------------- #


def test_every_registered_anchor_resolves_against_live_canon():
    """No env override — resolve the real manifest against the installed skills.

    Turns red the moment an upstream skill pull renames/moves a section the
    graph pulls verbatim (the fail-loud contract). Requires the live skills to
    be present (dev machine / TrueNAS); they are part of this project's setup.
    """
    cl.verify_anchors(cl.all_refs())
    # Every node's blocks resolve and are non-empty.
    for node in cl.NODE_CANON_ANCHORS:
        blocks = cl.load_canon_blocks(node)
        assert blocks, f"{node} produced no canon blocks"
        for key, body in blocks.items():
            assert body.strip(), f"{node}.{key} resolved empty"
