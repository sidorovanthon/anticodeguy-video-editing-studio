"""Smokes for :func:`tests._helpers.materialize_into_tmpdir`.

HOM-255 / Step D1 of HOM-230. Proves the materializer reproduces the
committed fixture tree byte-for-byte under an isolated tmpdir — the
foundational invariant Step D2 (HOM-239) leans on when it ``git rm``s
the committed hyperframes/ artifacts.

Tests skip when the fixture cache.db is missing, matching the existing
``requires_fixture_cache`` pattern in ``tests/test_graph_replay.py``.
"""

from __future__ import annotations

import hashlib
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


def _sha256_normalized(path: Path) -> str:
    """Hash file bytes after normalizing line endings to LF.

    Git's ``core.autocrlf`` on Windows checks out text files with CRLF,
    while the materializer always writes UTF-8 LF (deterministic
    production output — see ``_atomic_write``'s ``newline=""`` contract).
    Comparing raw bytes would surface that purely-cosmetic difference;
    normalizing both sides to LF compares the actual content the
    materializer is responsible for.
    """
    raw = path.read_bytes()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


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
    # project.md appended under edit/ (sibling of hyperframes/).
    project_md = materialized.parent / "edit" / "project.md"
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


@requires_fixture_cache
def test_materialize_into_tmpdir_regenerates_committed_content(tmp_path):
    """For each materialized artifact, sha256(materialized) ==
    sha256(committed) under the source fixture tree.

    Foundational invariant for HOM-239 (Step D2): when D2 ``git rm``s
    the committed hyperframes/ files, this test path keeps green via
    materializer regeneration. Any per-file delta surfaces here LOUDLY
    before D2 lands — a delta means either the cache.db is stale
    relative to the committed tree (HOM-216 territory) or the
    materializer's write logic doesn't match the producer's.
    """
    materialized = materialize_into_tmpdir(
        FIXTURE_SLUG,
        source_episode_dir=SOURCE_EPISODE_DIR,
        tmpdir=tmp_path,
    )

    source_hf = SOURCE_EPISODE_DIR / "hyperframes"

    deltas: list[str] = []

    def _compare(source: Path, target: Path, label: str) -> None:
        if not source.is_file():
            return
        if not target.is_file():
            deltas.append(f"{label}: materializer did not produce {target}")
            return
        s = _sha256_normalized(source)
        t = _sha256_normalized(target)
        if s != t:
            deltas.append(
                f"{label}: sha256 mismatch — source={s[:16]}…, materialized={t[:16]}…"
            )

    for relpath in _EXPECTED_HF_FILES:
        _compare(source_hf / relpath, materialized / relpath, relpath)
    for source_scene in _scene_files(source_hf):
        relname = f"compositions/{source_scene.name}"
        _compare(source_scene, materialized / "compositions" / source_scene.name, relname)

    # project.md is appended; for an empty tmpdir the appended block IS
    # the entire project.md content (no prior session), so byte equality
    # with the source is expected.
    _compare(
        SOURCE_EPISODE_DIR / "edit" / "project.md",
        tmp_path / "episodes" / FIXTURE_SLUG / "edit" / "project.md",
        "edit/project.md",
    )

    assert not deltas, (
        "materializer output diverges from committed fixture — D2 cannot "
        "safely `git rm` these files until the deltas are reconciled:\n  - "
        + "\n  - ".join(deltas)
    )
