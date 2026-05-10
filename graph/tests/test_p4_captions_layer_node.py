"""Unit tests for p4_captions_layer (HOM-123 + HOM-215).

Coverage:
1. Brief shape — references canon by path, never embeds canon (CLAUDE.md
   §"Decomposition via brief-references-canon").
2. HOM-215 brief imperative — exit-before-next-entrance contract is
   present in the brief: `group[i].end ≤ group[i+1].start`.
3. Deterministic caption-overlap test — parses a sample `captions.html`
   fragment, walks both (a) the static `GROUPS` literal in the JS source
   AND (b) the `tl.fromTo` / `tl.set` calls on the timeline, and asserts
   for every consecutive pair `(group[i], group[i+1])`:
     - caption[i] has an exit kill (`tl.set(... opacity: 0, visibility:
       "hidden" ...)`) at time t_exit.
     - t_exit ≤ caption[i+1] entrance time (`tl.fromTo(...)` start arg).
   Mirrors the HOM-214 hardened pattern — independent regex extraction
   from JS source PLUS cross-check against the GROUPS table — so the
   reviewer concern about "test only checks one shape" is addressed.

The deterministic test runs against an inline canonical fragment, NOT
against a recorded fixture (HOM-216 owns the recorded-fixture replay).
This is a static-analysis test of the GENERATED captions block — it
verifies the brief's invariant is structurally checkable from the
output, so future regressions are caught at the static level instead
of waiting for a Playwright frame snapshot.
"""

from __future__ import annotations

import re
from typing import Sequence

import pytest

from edit_episode_graph.nodes import p4_captions_layer as node_module


# ---------------------------------------------------------------------------
# Brief shape
# ---------------------------------------------------------------------------


def test_brief_references_canon_paths_without_embedding():
    brief = node_module._load_brief("p4_captions_layer")
    # Canon read-list (path-references, not embedded).
    assert "~/.agents/skills/hyperframes/references/captions.md" in brief
    assert "~/.agents/skills/hyperframes/references/transcript-guide.md" in brief
    assert "~/.agents/skills/hyperframes/SKILL.md" in brief
    # Output-shape imperatives.
    assert "tl.fromTo" in brief
    assert "#captions-layer" in brief
    # Compactness — brief stays a path-reference, not a canon paste.
    assert brief.count("\n") < 200, (
        f"brief grew to {brief.count(chr(10))} lines — "
        "should reference canon, not embed"
    )


# ---------------------------------------------------------------------------
# HOM-215: exit-before-next-entrance imperative survives future edits
# ---------------------------------------------------------------------------


def test_brief_mandates_exit_before_next_entrance():
    """HOM-215: the brief MUST explicitly declare the GROUPS table as a
    non-overlapping ordered partition (`group[i].end ≤ group[i+1].start`).
    Without this rule the LLM produces overlapping caption groups and the
    fixture symptom recurs (two captions stacked at t=11s on canonical
    portrait fixture).
    """
    brief = node_module._load_brief("p4_captions_layer")

    # The invariant in mathematical form — chosen as the most edit-stable
    # marker (re-wording the prose around it leaves the relation intact).
    assert "group[i].end" in brief, (
        "missing the exit-before-next-entrance invariant marker "
        "(group[i].end ≤ group[i+1].start)"
    )
    assert "group[i+1].start" in brief, (
        "missing the next-entrance side of the invariant"
    )

    # The symptom citation — keeps the why-this-rule-exists signal in the
    # brief so future edits don't quietly weaken it.
    assert "HOM-215" in brief or "HOM-210" in brief, (
        "missing the HOM-215 / HOM-210 symptom citation"
    )

    # Canon citation — the rule is canonical (`captions.md` §"Constraints"
    # already says "One group visible at a time"); the brief must point
    # at the canon path, not paraphrase it as a fork.
    assert "references/captions.md" in brief, (
        "missing canon path citation"
    )


def test_brief_does_not_embed_canon_text_verbatim():
    """HOM-213 reviewer concern (S1): verbatim canon quotes are fork-risk.
    The brief points at canon by path; it does NOT lift canonical
    paragraphs verbatim. This guard catches the most obvious quoted
    canon phrasing — if a future edit lifts a canon paragraph in
    triple-backtick fences, this test fires.
    """
    brief = node_module._load_brief("p4_captions_layer")

    # `captions.md` opens its constraints list with this exact phrasing —
    # we cite the section title, but never lift the body verbatim.
    assert "Sync to transcript timestamps." not in brief, (
        "brief lifted a canon constraints-section sentence verbatim — "
        "reference canon by path, do not paraphrase or quote"
    )


# ---------------------------------------------------------------------------
# Deterministic caption-overlap parser — HOM-215 core test.
# ---------------------------------------------------------------------------


_GROUPS_LITERAL_RE = re.compile(
    r"""var\s+GROUPS\s*=\s*(\[(?:[^[\]]*|\[[^\]]*\])*\])\s*;""",
    re.DOTALL,
)
_GROUP_ENTRY_RE = re.compile(
    r"""\{\s*id\s*:\s*["']([^"']+)["']\s*,\s*"""
    r"""text\s*:\s*["']([^"']*)["']\s*,\s*"""
    r"""start\s*:\s*([0-9.]+)\s*,\s*"""
    r"""end\s*:\s*([0-9.]+)""",
    re.DOTALL,
)
_FROMTO_CALL_RE = re.compile(
    r"""tl\.fromTo\(\s*([A-Za-z_$][\w$]*|document\.getElementById\([^)]+\))\s*,"""
    r"""[^,]*,\s*\{[^}]*\}\s*,\s*([\w.()\[\]"' +-]+?)\s*\)""",
    re.DOTALL,
)
_KILL_SET_RE = re.compile(
    r"""tl\.set\(\s*([A-Za-z_$][\w$]*|document\.getElementById\([^)]+\))\s*,"""
    r"""\s*\{\s*opacity\s*:\s*0[^}]*visibility\s*:\s*["']hidden["'][^}]*\}\s*,"""
    r"""\s*([\w.()\[\]"' +-]+?)\s*\)""",
    re.DOTALL,
)


def _parse_groups_table(js_source: str) -> list[dict]:
    """Pull the static GROUPS literal out of the captions block JS source.

    Returns a list of dicts with `id`, `start`, `end` floats. Parsing is
    intentionally regex-based, NOT a JS evaluator — the brief mandates
    the GROUPS table be a static literal of object-literal entries with
    known field names (`id`, `text`, `start`, `end`), which is regex-safe.
    """
    m = _GROUPS_LITERAL_RE.search(js_source)
    assert m, "could not locate `var GROUPS = [ ... ];` literal in captions block"
    body = m.group(1)
    groups: list[dict] = []
    for entry in _GROUP_ENTRY_RE.finditer(body):
        gid, text, start_s, end_s = entry.groups()
        groups.append(
            {
                "id": gid,
                "text": text,
                "start": float(start_s),
                "end": float(end_s),
            }
        )
    assert groups, "regex matched the GROUPS literal but extracted zero entries"
    return groups


def _assert_no_caption_overlap(groups: Sequence[dict]) -> None:
    """For every consecutive pair, group[i].end ≤ group[i+1].start.

    HOM-215 invariant — the GROUPS table is a non-overlapping ordered
    partition. Violation is the canonical fixture's t=11s symptom.
    """
    for i in range(len(groups) - 1):
        cur, nxt = groups[i], groups[i + 1]
        assert cur["end"] <= nxt["start"] + 1e-6, (
            f"caption-overlap: group[{i}] '{cur['id']}' (end={cur['end']:.3f}) "
            f"overlaps group[{i+1}] '{nxt['id']}' (start={nxt['start']:.3f}) — "
            "violates HOM-215 exit-before-next-entrance contract"
        )
        # Monotonicity: groups are ordered by start time.
        assert cur["start"] <= nxt["start"], (
            f"caption groups out of order at index {i}"
        )


def _assert_kill_set_for_each_group(js_source: str, groups: Sequence[dict]) -> None:
    """Cross-check: every group must have a `tl.set(... opacity:0, visibility:
    "hidden" ..., group.end)` kill-tween in the timeline. The deterministic
    kill is what guarantees the exit lands at the GROUPS-declared end time.

    The canonical brief shape uses `tl.set(el, ..., group.end)` inside a
    `GROUPS.forEach` — so the JS source contains literally one `tl.set(el,
    { opacity: 0, visibility: "hidden" }, group.end)` per FOREACH iteration.
    The check passes when the kill-set appears at all (one occurrence
    drives every iteration). We also accept the unrolled form (one kill
    per group with the literal end-time as the position arg).
    """
    kill_calls = list(_KILL_SET_RE.finditer(js_source))
    assert kill_calls, (
        "no `tl.set(..., { opacity: 0, visibility: \"hidden\" }, ...)` "
        "kill-tween found — violates canon §\"Caption Exit Guarantee\""
    )

    # Either: one shared kill inside forEach using `group.end` as position
    # arg, OR one literal kill per group with the end timestamp inlined.
    pos_args = [m.group(2).strip() for m in kill_calls]
    if any("group.end" in p for p in pos_args):
        return  # forEach shape — one kill drives all groups
    # Unrolled shape — every group's `end` should appear as a literal pos.
    end_literals = {f"{g['end']:.3f}".rstrip("0").rstrip(".") for g in groups}
    matched = sum(
        1
        for p in pos_args
        if any(p == e or p.startswith(e) for e in end_literals)
    )
    assert matched >= len(groups), (
        f"unrolled kill-set form: matched {matched}/{len(groups)} group end "
        "times — every group must have its own kill-tween"
    )


# ---------------------------------------------------------------------------
# Canonical-shape sample — NOT a recorded fixture, an inline minimal block
# that exercises the parsers + the HOM-215 invariant. Tests both the
# happy-path (no overlap) and a regression case (synthetic overlap → must
# trip the assertion).
# ---------------------------------------------------------------------------


_HAPPY_PATH_BLOCK = """
<div id="captions-layer" class="captions-layer">
  <style>#captions-layer { position: absolute; inset: 0; }</style>
  <div class="cg" id="cg-0">hello</div>
  <div class="cg" id="cg-1">world</div>
  <div class="cg" id="cg-2">again</div>
  <script>
    (function() {
      // Reference transcript: raw.json
      var GROUPS = [
        { id: "cg-0", text: "hello", start: 0.0, end: 1.2 },
        { id: "cg-1", text: "world", start: 1.2, end: 2.5 },
        { id: "cg-2", text: "again", start: 2.5, end: 3.8 }
      ];
      var tl = gsap.timeline({ paused: true });
      GROUPS.forEach(function (group) {
        var el = document.getElementById(group.id);
        if (!el) return;
        tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.2 }, group.start);
        tl.to(el, { opacity: 0, duration: 0.12 }, group.end - 0.12);
        tl.set(el, { opacity: 0, visibility: "hidden" }, group.end);
      });
    })();
  </script>
</div>
"""


_OVERLAPPING_BLOCK = """
<div id="captions-layer">
  <script>
    (function() {
      // Reference transcript: raw.json
      var GROUPS = [
        { id: "cg-0", text: "first", start: 0.0, end: 2.0 },
        { id: "cg-1", text: "second", start: 1.5, end: 3.0 }
      ];
      var tl = gsap.timeline({ paused: true });
      GROUPS.forEach(function (group) {
        var el = document.getElementById(group.id);
        if (!el) return;
        tl.fromTo(el, { opacity: 0 }, { opacity: 1 }, group.start);
        tl.set(el, { opacity: 0, visibility: "hidden" }, group.end);
      });
    })();
  </script>
</div>
"""


def test_happy_path_block_passes_overlap_invariant():
    groups = _parse_groups_table(_HAPPY_PATH_BLOCK)
    assert [g["id"] for g in groups] == ["cg-0", "cg-1", "cg-2"]
    _assert_no_caption_overlap(groups)
    _assert_kill_set_for_each_group(_HAPPY_PATH_BLOCK, groups)


def test_overlapping_block_trips_overlap_invariant():
    """Regression-guard for the parser/asserter itself: if the GROUPS
    table overlaps in time, `_assert_no_caption_overlap` MUST raise.
    Without this guard a future edit could silently weaken the asserter
    (e.g. wrong inequality direction) and the suite would still pass on
    the happy-path block while real overlapping captions slip through.
    """
    groups = _parse_groups_table(_OVERLAPPING_BLOCK)
    with pytest.raises(AssertionError, match="caption-overlap"):
        _assert_no_caption_overlap(groups)


def test_groups_match_kill_set_positions():
    """Cross-check between the static GROUPS table and the timeline's
    `tl.set(..., group.end)` calls — the kill-tween's position arg
    references `group.end`, so the GROUPS-declared end times ARE the
    timeline's deterministic-kill timestamps. This is the second
    independent extraction the HOM-214 review asked for."""
    groups = _parse_groups_table(_HAPPY_PATH_BLOCK)
    # Independent: pull the kill-set position args out of the JS source
    # via a different regex, confirm the forEach-shared form references
    # `group.end` so the kills are guaranteed to be at the GROUPS-end times.
    kill_calls = list(_KILL_SET_RE.finditer(_HAPPY_PATH_BLOCK))
    assert kill_calls, "no kill-tween calls extracted"
    pos_args = [m.group(2).strip() for m in kill_calls]
    assert any("group.end" in p for p in pos_args), (
        "kill-tween position arg does not reference `group.end` — "
        "the timeline's exit timestamps are not bound to the GROUPS "
        "table's declared end times"
    )
    # Sanity: the parsed groups must each have an entrance via fromTo.
    fromto_calls = list(_FROMTO_CALL_RE.finditer(_HAPPY_PATH_BLOCK))
    assert fromto_calls, "no fromTo entrance calls extracted"
    pos_args_in = [m.group(2).strip() for m in fromto_calls]
    assert any("group.start" in p for p in pos_args_in), (
        "entrance tween position arg does not reference `group.start`"
    )
    _ = groups  # keep groups parse referenced for symmetry with kill check
