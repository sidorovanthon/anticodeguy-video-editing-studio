"""Tests for `edit_episode_graph._paths` (HOM-131 + HOM-159)."""

from __future__ import annotations

from pathlib import Path

import pytest

from edit_episode_graph._paths import (
    PROJECT_ROOT_ENV_VAR,
    REPO_ROOT_ENV_VAR,
    EpisodePaths,
    project_root,
    repo_root,
)


def test_resolves_main_worktree(tmp_path: Path) -> None:
    """A real `.git/` directory marks the main worktree."""
    main = tmp_path / "repo"
    (main / ".git").mkdir(parents=True)
    nested = main / "graph"
    nested.mkdir()
    smoke = nested / "smoke_hom999.py"
    smoke.write_text("# fixture\n", encoding="utf-8")

    assert repo_root(smoke) == main


def test_skips_linked_worktree(tmp_path: Path) -> None:
    """A `.git` *file* (linked worktree) is skipped — caller lands at main."""
    main = tmp_path / "repo"
    (main / ".git").mkdir(parents=True)
    worktree = main / ".claude" / "worktrees" / "feature-x"
    worktree.mkdir(parents=True)
    # Mirror git's actual format for a linked worktree's .git pointer.
    (worktree / ".git").write_text(
        f"gitdir: {main / '.git' / 'worktrees' / 'feature-x'}\n",
        encoding="utf-8",
    )
    smoke = worktree / "graph" / "smoke_hom999.py"
    smoke.parent.mkdir()
    smoke.write_text("# fixture\n", encoding="utf-8")

    assert repo_root(smoke) == main


def test_raises_when_no_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(REPO_ROOT_ENV_VAR, raising=False)
    inside = tmp_path / "no-repo" / "deep" / "tree"
    inside.mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        repo_root(inside)


def test_repo_root_env_override_when_no_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HOM-347: container deployments have no .git/ — env var must work."""
    inside = tmp_path / "no-repo" / "deep"
    inside.mkdir(parents=True)
    override = tmp_path / "deps"
    override.mkdir()
    monkeypatch.setenv(REPO_ROOT_ENV_VAR, str(override))
    assert repo_root(inside) == override.resolve()


def test_repo_root_env_takes_precedence_over_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HOM-347: env var wins even if a .git/ marker exists above start."""
    main = tmp_path / "repo"
    (main / ".git").mkdir(parents=True)
    nested = main / "graph"
    nested.mkdir()
    override = tmp_path / "deps"
    override.mkdir()
    monkeypatch.setenv(REPO_ROOT_ENV_VAR, str(override))
    assert repo_root(nested) == override.resolve()


def test_repo_root_empty_env_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Empty-string env var is treated as unset, like PROJECT_ROOT."""
    main = tmp_path / "repo"
    (main / ".git").mkdir(parents=True)
    nested = main / "graph"
    nested.mkdir()
    monkeypatch.setenv(REPO_ROOT_ENV_VAR, "")
    assert repo_root(nested) == main


def test_default_start_resolves_this_repo() -> None:
    """Called with no args, finds the actual checkout this test runs from."""
    root = repo_root()
    assert (root / ".git").is_dir()


def test_project_root_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``HOMESTUDIO_PROJECT_ROOT`` overrides the git-walk default (HOM-159)."""
    custom = tmp_path / "custom-root"
    custom.mkdir()
    monkeypatch.setenv(PROJECT_ROOT_ENV_VAR, str(custom))
    assert project_root() == custom.resolve()


def test_project_root_default_falls_back_to_repo_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the env var, ``project_root()`` matches ``repo_root()``."""
    monkeypatch.delenv(PROJECT_ROOT_ENV_VAR, raising=False)
    assert project_root() == repo_root()


def test_project_root_empty_env_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty-string env var is treated as unset, not as ``Path('').resolve()``."""
    monkeypatch.setenv(PROJECT_ROOT_ENV_VAR, "")
    assert project_root() == repo_root()


# ---------------------------------------------------------------------------
# EpisodePaths (HOM-222 / HOM-195 Sub-1)
# ---------------------------------------------------------------------------


SLUG = "canonical-portrait-talking-head"


def _set_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setenv(PROJECT_ROOT_ENV_VAR, str(root))


def test_episode_paths_construction_is_pure(tmp_path: Path) -> None:
    """Construction does no I/O and never raises — even for a nonexistent root."""
    # No env var set, no fs lookups required to instantiate.
    ep = EpisodePaths(slug=SLUG)
    assert ep.slug == SLUG


def test_episode_paths_is_frozen() -> None:
    """`slug` cannot be mutated post-construction (logical identity is fixed)."""
    ep = EpisodePaths(slug=SLUG)
    with pytest.raises(Exception):  # FrozenInstanceError
        ep.slug = "other"  # type: ignore[misc]


def test_episode_paths_all_properties_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every documented property + method resolves under the configured root."""
    _set_root(monkeypatch, tmp_path)
    ep = EpisodePaths(slug=SLUG)
    base = tmp_path / "episodes" / SLUG

    assert ep.episode_dir == base
    assert ep.raw_path(".mp4") == base / "raw.mp4"
    assert ep.raw_path(".mov") == base / "raw.mov"
    assert ep.edit_dir == base / "edit"
    assert ep.final_mp4_path == base / "edit" / "final.mp4"
    assert ep.transcripts_dir == base / "edit" / "transcripts"
    assert ep.transcripts_raw_json_path == base / "edit" / "transcripts" / "raw.json"
    assert (
        ep.transcripts_final_json_path == base / "edit" / "transcripts" / "final.json"
    )
    assert ep.hyperframes_dir == base / "hyperframes"
    assert ep.hyperframes_state_dir == base / "hyperframes" / ".hyperframes"
    assert ep.index_html_path == base / "hyperframes" / "index.html"
    assert ep.design_md_path == base / "hyperframes" / "DESIGN.md"
    assert (
        ep.expanded_prompt_path
        == base / "hyperframes" / ".hyperframes" / "expanded-prompt.md"
    )
    assert ep.compositions_dir == base / "hyperframes" / "compositions"
    assert ep.captions_block_path == base / "hyperframes" / "captions.html"
    assert (
        ep.beat_fragment_path("hook")
        == base / "hyperframes" / "compositions" / "hook.html"
    )


def test_episode_paths_lazy_resolution_no_caching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Load-bearing: changing HOMESTUDIO_PROJECT_ROOT between two reads of the
    same property produces different absolute paths. Proves no precomputation,
    no caching — `project_root()` is invoked at attribute access time.
    """
    root_a = tmp_path / "root-a"
    root_b = tmp_path / "root-b"
    root_a.mkdir()
    root_b.mkdir()

    ep = EpisodePaths(slug=SLUG)

    _set_root(monkeypatch, root_a)
    first = ep.episode_dir
    assert first == root_a / "episodes" / SLUG

    _set_root(monkeypatch, root_b)
    second = ep.episode_dir
    assert second == root_b / "episodes" / SLUG

    assert first != second  # the same property yielded two different paths


def test_episode_paths_lazy_resolution_applies_to_all_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spot-check: a downstream property and a method also re-resolve."""
    root_a = tmp_path / "root-a"
    root_b = tmp_path / "root-b"
    root_a.mkdir()
    root_b.mkdir()

    ep = EpisodePaths(slug=SLUG)

    _set_root(monkeypatch, root_a)
    final_a = ep.final_mp4_path
    beat_a = ep.beat_fragment_path("hook")

    _set_root(monkeypatch, root_b)
    final_b = ep.final_mp4_path
    beat_b = ep.beat_fragment_path("hook")

    assert final_a.is_relative_to(root_a)
    assert final_b.is_relative_to(root_b)
    assert beat_a.is_relative_to(root_a)
    assert beat_b.is_relative_to(root_b)


def test_episode_paths_worktree_mode_resolves_to_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without HOMESTUDIO_PROJECT_ROOT, paths fall back to repo_root() — i.e.
    the main worktree, even when the test runs under a linked worktree (the
    `project_root()` contract from HOM-159).
    """
    monkeypatch.delenv(PROJECT_ROOT_ENV_VAR, raising=False)
    ep = EpisodePaths(slug=SLUG)
    expected = repo_root() / "episodes" / SLUG
    assert ep.episode_dir == expected


def test_episode_paths_distinct_slugs_yield_distinct_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_root(monkeypatch, tmp_path)
    a = EpisodePaths(slug="alpha")
    b = EpisodePaths(slug="beta")
    assert a.episode_dir != b.episode_dir
    assert a.episode_dir.name == "alpha"
    assert b.episode_dir.name == "beta"
