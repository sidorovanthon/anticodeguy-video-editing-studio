"""Tests for `edit_episode_graph._paths.repo_root` (HOM-131)."""

from __future__ import annotations

from pathlib import Path

import pytest

from edit_episode_graph._paths import repo_root


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
