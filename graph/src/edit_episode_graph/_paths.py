"""Filesystem path helpers shared by smoke scripts.

Smoke scripts historically resolved ``REPO_ROOT = Path(__file__).resolve().parent.parent``,
which from a feature worktree picks the worktree dir, not the main repo.
Episodes written under ``<worktree>/episodes/`` vanish when the worktree
is cleaned up after merge — see HOM-131.

``repo_root()`` walks up from a starting path looking for a ``.git``
*directory*. A linked git worktree has ``.git`` as a *file* pointing
back to the main repo, so the search skips past it and lands at the
main worktree's root. This matches how ``git rev-parse --show-toplevel``
would resolve from the main repo, deterministically — no env var, no
convention coupling to ``.claude/worktrees``.
"""

from __future__ import annotations

from pathlib import Path


def repo_root(start: Path | None = None) -> Path:
    """Return the main git worktree's root by walking up from ``start``.

    ``.git`` as a directory marks the main worktree; ``.git`` as a file
    marks a linked worktree (and is skipped). Raises ``FileNotFoundError``
    if no main ``.git`` directory is found above ``start``.
    """
    here = (start or Path(__file__)).resolve()
    if here.is_file():
        here = here.parent
    for candidate in (here, *here.parents):
        if (candidate / ".git").is_dir():
            return candidate
    raise FileNotFoundError(f"no main git worktree found above {here}")
