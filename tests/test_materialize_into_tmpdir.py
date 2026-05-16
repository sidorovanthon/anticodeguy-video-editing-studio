"""Smokes for :func:`tests._helpers.materialize_into_tmpdir`.

HOM-255 / Step D1 of HOM-230. Proves the materializer reproduces the
expected Phase-4 text artifacts under an isolated tmpdir.

Tests skip when the fixture cache.db is missing, matching the existing
``requires_fixture_cache`` pattern in ``tests/test_graph_replay.py``.

Historical note (HOM-239 Step D2, 2026-05-16): a third test,
``test_materialize_into_tmpdir_regenerates_committed_content``, used to
compare materialized output against the committed fixture tree at
``SOURCE_EPISODE_DIR / "hyperframes"``. After D2 ``git rm``ed those
artifacts (cache.db is now the only ground truth), the comparison loop
became structurally tautological — ``source.is_file()`` is always
False, the loop early-returns, ``deltas`` stays empty, the assert
passes vacuously. Test deleted in the D2 follow-up. The cache.db rows
plus the other two smokes here carry the contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests._helpers.materialize_into_tmpdir import materialize_into_tmpdir


FIXTURE_SLUG = "canonical-portrait-talking-head"
_REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_EPISODE_DIR = (
    _REPO_ROOT / "tests" / "fixtures" / "episodes" / FIXTURE_SLUG
)
SOURCE_CACHE_DB = SOURCE_EPISODE_DIR / "cache.db"

requires_fixture_cache = pytest.mark.skipif(
    not SOURCE_CACHE_DB.exists(),
    reason=(
        "fixture cache.db not yet prewarmed at "
        f"{SOURCE_CACHE_DB.relative_to(_REPO_ROOT)} — operator prewarm tracked "
        "in HOM-181 follow-up. Until then materialize_into_tmpdir falls back "
        "on the source hyperframes/ tree alone, which is still committed in "
        "D1 and only ``git rm``ed in D2 (HOM-239)."
    ),
)


# Files the materializer is expected to write under the materialized hyperframes/.
# Keys are paths relative to the hyperframes/ dir; absence of a key here means
# the materializer should NOT touch that path (mirrors compositions/ glob in
# the source so the test is robust to scene-id changes in the fixture).
_EXPECTED_HF_FILES = (
    "DESIGN.md",
    ".hyperframes/expanded-prompt.md",
    "captions.html",
    "index.html",
)


def _scene_files(hf_dir: Path) -> list[Path]:
    """Every ``compositions/*.html`` under ``hf_dir``."""
    comp = hf_dir / "compositions"
    if not comp.is_dir():
        return []
    return sorted(comp.glob("*.html"))


@requires_fixture_cache
def test_materialize_into_tmpdir_writes_expected_files(tmp_path):
    """All canonical HyperFrames text artifacts land under the
    materialized tmpdir; ``edit/project.md`` is appended to."""
    materialized = materialize_into_tmpdir(
        FIXTURE_SLUG,
        source_episode_dir=SOURCE_EPISODE_DIR,
        tmpdir=tmp_path,
    )
    assert materialized.is_dir(), (
        f"materializer did not create hyperframes dir at {materialized}"
    )
    for relpath in _EXPECTED_HF_FILES:
        target = materialized / relpath
        assert target.is_file(), (
            f"materializer did not write expected artifact {relpath} "
            f"(looked at {target})"
        )
    # At least one scene fragment should have been written — the
    # canonical fixture has multiple beats (hook/problem/pivot/payoff).
    scenes = _scene_files(materialized)
    assert scenes, (
        f"materializer did not write any compositions/*.html under {materialized}"
    )
    # project.md appended under edit/ (sibling of hyperframes/) — only
    # when the cache.db carries `compose.persist.session_block`. The
    # canonical fixture's HOM-241 wave-acceptance record happens to have
    # an empty `session_block` slot (the recorded sub-agent did not
    # return one), so this assertion gates on cache content rather than
    # raising unconditionally. Re-recording the fixture with a full
    # persist body is the follow-up to fully exercise this path.
    project_md = materialized.parent / "edit" / "project.md"
    if (SOURCE_EPISODE_DIR / "cache.db").is_file():
        from tests._helpers.materialize_into_tmpdir import _decode_cache_rows
        by_node = _decode_cache_rows(SOURCE_EPISODE_DIR / "cache.db")
        recorded_session_block = next(
            (
                ((e.get("compose") or {}).get("persist") or {}).get("session_block")
                for e in by_node.get("p4_persist_session", [])
            ),
            None,
        )
        if isinstance(recorded_session_block, str) and recorded_session_block:
            assert project_md.is_file(), (
                f"materializer did not write edit/project.md at {project_md}"
            )


@requires_fixture_cache
def test_materialize_into_tmpdir_idempotent(tmp_path):
    """Calling the helper twice into the same tmpdir → second call writes
    nothing (every file already matches by content; session_block is a
    substring of project.md so its append is skipped)."""
    materialize_into_tmpdir(
        FIXTURE_SLUG,
        source_episode_dir=SOURCE_EPISODE_DIR,
        tmpdir=tmp_path,
    )
    # Capture mtimes of every materialized file after the first call.
    materialized = tmp_path / "episodes" / FIXTURE_SLUG / "hyperframes"
    project_md = tmp_path / "episodes" / FIXTURE_SLUG / "edit" / "project.md"

    artifacts = [materialized / r for r in _EXPECTED_HF_FILES]
    artifacts += _scene_files(materialized)
    artifacts.append(project_md)
    mtimes_before = {str(p): p.stat().st_mtime_ns for p in artifacts if p.is_file()}

    # Second call.
    materialize_into_tmpdir(
        FIXTURE_SLUG,
        source_episode_dir=SOURCE_EPISODE_DIR,
        tmpdir=tmp_path,
    )

    mtimes_after = {str(p): p.stat().st_mtime_ns for p in artifacts if p.is_file()}
    changed = [
        p for p in mtimes_before
        if mtimes_after.get(p) != mtimes_before[p]
    ]
    assert not changed, (
        f"idempotency violation — second call rewrote files: {changed}"
    )


# NOTE: ``test_materialize_into_tmpdir_regenerates_committed_content``
# was deleted in HOM-239 Step D2 (2026-05-16). See module docstring.
