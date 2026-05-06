"""Tests for `edit_episode_graph._paths` (HOM-131 + HOM-159)."""

from __future__ import annotations

from pathlib import Path

import pytest

from edit_episode_graph._paths import (
    PROJECT_ROOT_ENV_VAR,
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


def test_raises_when_no_git(tmp_path: Path) -> None:
    inside = tmp_path / "no-repo" / "deep" / "tree"
    inside.mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        repo_root(inside)


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
