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
from dataclasses import dataclass
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


@dataclass(frozen=True)
class EpisodePaths:
    """Lazy, slug-keyed resolver for every canonical artifact path in an episode.

    HOM-195 Sub-1 (foundational refactor — no callers migrated in this PR;
    Sub-2 owns p3 migration, Sub-3 owns p4 migration). The state schema today
    stores absolute paths (``state["episode_dir"]``, ``compose.captions_block_path``,
    …) that bake the resolution moment into the checkpoint. That makes a
    Studio time-travel run from a different ``HOMESTUDIO_PROJECT_ROOT`` (or a
    fresh worktree) read paths that point at the recording machine. The
    long-term fix is "state stores ``slug``; nodes resolve paths via this API
    at access time".

    **Lazy contract.** Every property calls :func:`project_root` at the moment
    of attribute access — no precomputation in ``__post_init__``, no
    ``@cached_property``. Mutating ``HOMESTUDIO_PROJECT_ROOT`` (e.g. between
    two reads inside a fixture-replay test, or between a record run and a
    Studio time-travel run) takes effect on the next read. Construction is
    pure: ``EpisodePaths("foo")`` does no I/O and never raises.

    The dataclass is ``frozen=True`` so ``slug`` cannot be mutated post-hoc
    (the slug is the logical identity of the episode — changing it mid-run
    would corrupt every downstream path).

    Filenames mirror the layout enforced today by node bodies — see
    CLAUDE.md §"Layout convention" and the per-node literals in
    ``nodes/p3_*.py`` / ``nodes/p4_*.py``. Do not invent new filenames here;
    every property below was cross-checked against the production node that
    writes the artifact (``p3_inventory`` for transcripts dirs,
    ``p3_render_segments`` / ``p3_persist_session`` for ``final.mp4``,
    ``p4_design_system`` for ``DESIGN.md``, ``p4_prompt_expansion`` for
    ``.hyperframes/expanded-prompt.md``, ``p4_captions_layer`` for
    ``captions.html``, ``p4_assemble_index`` for ``index.html`` +
    ``compositions/<scene_id>.html``).
    """

    slug: str

    @property
    def episode_dir(self) -> Path:
        return project_root() / "episodes" / self.slug

    def raw_path(self, ext: str) -> Path:
        """Path to the raw upload (``raw<ext>``). ``ext`` includes the dot."""
        return self.episode_dir / f"raw{ext}"

    @property
    def edit_dir(self) -> Path:
        return self.episode_dir / "edit"

    @property
    def final_mp4_path(self) -> Path:
        return self.edit_dir / "final.mp4"

    @property
    def transcripts_dir(self) -> Path:
        return self.edit_dir / "transcripts"

    @property
    def transcripts_raw_json_path(self) -> Path:
        return self.transcripts_dir / "raw.json"

    @property
    def transcripts_final_json_path(self) -> Path:
        return self.transcripts_dir / "final.json"

    @property
    def hyperframes_dir(self) -> Path:
        return self.episode_dir / "hyperframes"

    @property
    def hyperframes_state_dir(self) -> Path:
        # Canonical HF dotdir for orchestrator-house state files
        # (currently just `expanded-prompt.md`; future per-node JSON dumps,
        # cache scratch, etc. land here too). See memory
        # `feedback_hf_step2_prompt_expansion`.
        return self.hyperframes_dir / ".hyperframes"

    @property
    def index_html_path(self) -> Path:
        return self.hyperframes_dir / "index.html"

    @property
    def design_md_path(self) -> Path:
        return self.hyperframes_dir / "DESIGN.md"

    @property
    def expanded_prompt_path(self) -> Path:
        # See nodes/p4_prompt_expansion.py::_expanded_prompt_path —
        # canonical name is `.hyperframes/expanded-prompt.md` per
        # memory `feedback_hf_step2_prompt_expansion`.
        return self.hyperframes_state_dir / "expanded-prompt.md"

    @property
    def compositions_dir(self) -> Path:
        return self.hyperframes_dir / "compositions"

    @property
    def captions_block_path(self) -> Path:
        # See nodes/p4_captions_layer.py::_captions_path.
        return self.hyperframes_dir / "captions.html"

    def beat_fragment_path(self, scene_id: str) -> Path:
        """Per-beat HTML fragment under ``compositions/<scene_id>.html``."""
        return self.compositions_dir / f"{scene_id}.html"


def scripts_root() -> Path:
    """Return the directory containing the ``scripts/`` package.

    This is the correct ``cwd`` for ``python -m scripts.X`` subprocess
    invocations. Always equal to ``repo_root()``; never affected by
    ``HOMESTUDIO_PROJECT_ROOT``. The data root (``project_root()``) and
    the scripts root are independent — see module docstring.
    """
    return repo_root()
