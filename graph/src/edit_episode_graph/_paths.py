"""Filesystem path helpers shared by graph nodes and smoke scripts.

Smoke scripts historically resolved ``REPO_ROOT = Path(__file__).resolve().parent.parent``,
which from a feature worktree picks the worktree dir, not the main repo.
Episodes written under ``<worktree>/episodes/`` vanish when the worktree
is cleaned up after merge — see HOM-131.

``repo_root()`` walks up from a starting path looking for a ``.git``
*directory*. A linked git worktree has ``.git`` as a *file* pointing
back to the main repo, so the search skips past it and lands at the
main worktree's root. This matches how ``git rev-parse --show-toplevel``
would resolve from the main repo, deterministically.

``project_root()`` is the helper graph nodes use to locate ``inbox/``
and ``episodes/``. It honors the ``HOMESTUDIO_PROJECT_ROOT`` env var
(explicit override — pin a worktree to read/write data from any path,
including the main checkout) and otherwise delegates to ``repo_root()``.
The env var is the long-term fix for HOM-159: worktrees no longer need
NTFS junctions to ``inbox/``+``episodes/``, which were a destructive
footgun under ``Remove-Item -Recurse`` (lost 6 episodes 2026-05-06).

``scripts_root()`` is the helper for resolving the ``cwd`` of subprocess
calls that invoke ``python -m scripts.X``. It always returns
``repo_root()`` — the directory containing the ``scripts/`` package —
regardless of ``HOMESTUDIO_PROJECT_ROOT``. Conflating the data root
(``project_root()``) with the scripts package root broke pickup when
``HOMESTUDIO_PROJECT_ROOT`` pointed at ``tests/fixtures`` (no ``scripts/``
there), producing ``ModuleNotFoundError: No module named 'scripts'``.
The two responsibilities — *where data lives* vs *where the package is
importable from* — are now distinct helpers.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT_ENV_VAR = "HOMESTUDIO_PROJECT_ROOT"


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


def project_root() -> Path:
    """Return the project root for ``inbox/``+``episodes/`` resolution.

    Order: ``$HOMESTUDIO_PROJECT_ROOT`` if set and non-empty (resolved to
    absolute); else ``repo_root()`` from this file (which lands at the
    main git worktree even when imported from a linked worktree).
    """
    override = os.environ.get(PROJECT_ROOT_ENV_VAR)
    if override:
        return Path(override).resolve()
    return repo_root()


def scripts_root() -> Path:
    """Return the directory containing the ``scripts/`` package.

    This is the correct ``cwd`` for ``python -m scripts.X`` subprocess
    invocations. Always equal to ``repo_root()``; never affected by
    ``HOMESTUDIO_PROJECT_ROOT``. The data root (``project_root()``) and
    the scripts root are independent — see module docstring.
    """
    return repo_root()
