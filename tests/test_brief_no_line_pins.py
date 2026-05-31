"""Structural guard: briefs/gates must cite external skill canon by stable
section anchor, never by line number (HOM-376).

The `hyperframes` and `video-use` skills auto-update via Task Scheduler
(`~/bin/hf-skills-update.vbs`, `video-use-update.vbs`, pulling from npm).
**Line numbers are not stable across those updates; section names are.** A
brief that cites `SKILL.md L227` silently rots the moment an upstream pull
shifts that section — verified 2026-05-31, where `p4_beat.j2`'s
`SKILL.md L227 + L240` pins had already drifted to empty lines, sending the
per-scene sub-agent to nonexistent canon.

This test fails the build on any external-canon line-pin in
`edit_episode_graph/briefs/*.j2` or `edit_episode_graph/gates/*.py`, so the
regression cannot recur. The fix is always the same: replace `<file>.md L<n>`
with `<file>.md §"Section name"`.

Detection is two-pronged, because the pins appear in two shapes in practice:

1. **Filename-adjacent** — ``SKILL.md:74``, ``catalog.md L9``,
   ``motion-principles.md L115-123``. Caught by `_ADJACENT_PIN`
   (the ticket's primary regex `\\.md[: ]L?\\d+`).
2. **Section-separated / trailing** — ``SKILL.md §"Animation Guardrails"
   L227 + Rules L240``, ``catalog.md`` L13`` (backtick between name and pin).
   The pin is NOT adjacent to the filename, so a filename-anchored regex
   misses it. Caught by `_LINE_PIN`: on any line that references a markdown
   file, a standalone ``L<n>`` / ``L<n>-<m>`` token is a line-pin.

Test-tier labels (``L0``/``L1``/``L2`` — the test-pyramid tiers in this
repo's own docstrings) are never co-located with a ``.md`` reference on the
same line, so prong 2 does not false-positive on them.

Memory: `feedback_briefs_anchor_not_line_pin`. Audit:
`docs/retros/retro-2026-05-31-langgraph-architecture-audit.md` F1 + §6.
"""

from __future__ import annotations

import re
from pathlib import Path

import edit_episode_graph
import pytest

_PKG_ROOT = Path(edit_episode_graph.__file__).resolve().parent
_BRIEFS_DIR = _PKG_ROOT / "briefs"
_GATES_DIR = _PKG_ROOT / "gates"

# Prong 1 — filename-adjacent pin: ``.md L227``, ``.md:74``, ``.md L36-80``.
# The optional ``L`` covers both the ``:74`` (no-L colon) and ``L9`` forms.
_ADJACENT_PIN = re.compile(r"\.md[: ]L?\d+(?:-\d+)?")

# Prong 2 — a markdown-file reference anywhere on the line, plus a standalone
# line-pin token elsewhere on the same line (``§"…" L227``, ``` ` L13``,
# trailing ``+ L240``). The ``(?<![\w])`` guard keeps ``HTML5``/``GSAP3``-style
# suffixes from matching; the token must be an isolated ``L<digits>``.
_MD_REF = re.compile(r"\.md\b")
_STANDALONE_PIN = re.compile(r"(?<![\w])L\d+(?:-\d+)?\b")


def _scan_text(text: str) -> list[tuple[int, str]]:
    """Return ``(line_number, line)`` for every line carrying an
    external-canon line-pin (either prong). 1-indexed line numbers."""
    hits: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _ADJACENT_PIN.search(line):
            hits.append((lineno, line))
            continue
        if _MD_REF.search(line) and _STANDALONE_PIN.search(line):
            hits.append((lineno, line))
    return hits


def _scanned_files() -> list[Path]:
    files = sorted(_BRIEFS_DIR.glob("*.j2")) + sorted(_GATES_DIR.glob("*.py"))
    return files


def test_scan_targets_exist() -> None:
    """Guard the guard: if the briefs/gates dirs move (or a glob silently
    stops matching a subtree), fail loudly rather than scanning nothing and
    passing vacuously.

    The explicit per-file coverage assertions below are load-bearing: the
    whole point of HOM-376 was to put `gates/animation_map.py` and the
    `briefs/_macros.j2` partial under the guard, so a regression that drops
    either subtree from the scan must turn this test red on its own."""
    assert _BRIEFS_DIR.is_dir(), f"briefs dir not found at {_BRIEFS_DIR}"
    assert _GATES_DIR.is_dir(), f"gates dir not found at {_GATES_DIR}"
    scanned = _scanned_files()
    assert scanned, "no briefs/*.j2 or gates/*.py files were scanned"

    by_rel = {f"{p.parent.name}/{p.name}" for p in scanned}
    # Files that MUST be covered — each carried a line-pin the real fix
    # removed, plus the shared macro partial.
    required = {
        "briefs/p4_beat.j2",
        "briefs/p4_redispatch_beat.j2",
        "briefs/p4_captions_layer.j2",
        "briefs/_macros.j2",
        "gates/animation_map.py",
        "gates/design_adherence.py",
    }
    missing = required - by_rel
    assert not missing, (
        f"the line-pin guard is not scanning required files: {sorted(missing)} "
        f"(scanned: {sorted(by_rel)})"
    )


@pytest.mark.parametrize(
    "path",
    _scanned_files(),
    ids=lambda p: f"{p.parent.name}/{p.name}",
)
def test_no_external_canon_line_pins(path: Path) -> None:
    """No brief or gate may cite external skill canon by line number.

    Per-file parametrization for readable failure attribution. The
    aggregate counterpart below re-scans every file in a single
    non-parametrized body so coverage does not depend on collection-time
    parametrization."""
    text = path.read_text(encoding="utf-8")
    hits = _scan_text(text)
    if hits:
        rel = path.relative_to(_PKG_ROOT)
        detail = "\n".join(f"  {rel}:{ln}: {line.strip()}" for ln, line in hits)
        pytest.fail(
            "External-canon line-number citation(s) found — cite the section "
            'anchor (§"Section name") instead; skill line numbers drift on '
            "auto-update (HOM-376):\n" + detail
        )


def test_no_external_canon_line_pins_aggregate() -> None:
    """Belt-and-suspenders: scan every brief/gate in one in-process pass.

    The parametrized test fans out at collection time; this body resolves
    the file set and reads each file at run time, so a single deterministic
    assertion covers the whole tree regardless of parametrization."""
    all_hits: list[str] = []
    for path in _scanned_files():
        rel = path.relative_to(_PKG_ROOT)
        for ln, line in _scan_text(path.read_text(encoding="utf-8")):
            all_hits.append(f"  {rel}:{ln}: {line.strip()}")
    assert not all_hits, (
        "External-canon line-number citation(s) found — cite the section "
        'anchor (§"Section name") instead; skill line numbers drift on '
        "auto-update (HOM-376):\n" + "\n".join(all_hits)
    )


def test_detector_catches_a_reintroduced_pin() -> None:
    """Self-test: the detector MUST flag every pin shape the real fix
    removed, and MUST NOT flag the section-anchor replacements or the
    repo's own L0/L1/L2 test-tier labels.

    This is the DoD's "re-adding a line-pin turns it red" check, exercised
    against the detector directly so it does not require mutating a real
    brief on disk."""
    # Every shape that appeared in the pre-HOM-376 briefs/gates must be caught.
    # These are the actual offending lines (verbatim) the real fix removed —
    # each carries the canon `.md` ref AND its line-pin on one line.
    must_flag = [
        # Section-separated trailing pins (prong 2): the pin follows the §name.
        '1. `~/.agents/skills/hyperframes/SKILL.md` — §"Animation Guardrails" L227 + Rules L240.',
        # Filename-adjacent space pin (prong 1).
        "3. `~/.agents/skills/hyperframes/references/motion-principles.md` — L115-123 the `tl.fromTo()` mandate.",
        # Multiple pins on one canon line (prong 1 catches the first; line fails).
        "2. `~/.agents/skills/hyperframes/references/transitions/catalog.md` — Hard Rules (CSS) L9 + L13, scene template L36-80.",
        "4. `~/.agents/skills/hyperframes/references/video-composition.md` — density floor (8-10 elements per scene, L15-23).",
        # Colon pin, no L (prong 1).
        '  - `offscreen` flag, unconditional. Per `SKILL.md:74` "CSS position is',
        # Backtick between filename and pin defeats adjacency — prong 2 catches it.
        "Standalone-composition canon (`transitions/catalog.md` L13) omits both timing attrs",
        # Bare-basename adjacent pin in a script comment (prong 1).
        "// entrance via tl.fromTo() — see motion-principles.md L115-123",
    ]
    for sample in must_flag:
        assert _scan_text(sample), f"detector failed to flag a line-pin: {sample!r}"

    # The section-anchor replacements and benign tokens must NOT be flagged.
    must_pass = [
        '1. `~/.agents/skills/hyperframes/SKILL.md` — §"Animation Guardrails", §"Rules (Non-Negotiable)".',
        '3. `~/.agents/skills/hyperframes/references/motion-principles.md` — §"Load-Bearing GSAP Rules".',
        '2. `~/.agents/skills/hyperframes/references/transitions/catalog.md` — §"Hard Rules (CSS)", §"Scene Template".',
        '- `offscreen` flag. Per `SKILL.md` §"Layout Before Animation" "CSS position is the ground truth".',
        # Test-tier label on a line with no .md reference — not a canon pin.
        "# Cache key — exposed for the L0 fingerprint-invalidation registry only.",
        "# v9 (HOM-376): brief gained L0/L1/L2 coverage notes.",  # L-labels, no .md
        # `repeat: -1` must not be read as a line-pin even near a .md ref.
        "(canon: SKILL.md §\"Rules (Non-Negotiable)\" — the \"No `repeat: -1`\" rule).",
    ]
    for sample in must_pass:
        assert not _scan_text(sample), f"detector false-positived on: {sample!r}"
