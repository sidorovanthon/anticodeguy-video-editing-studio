"""Regression: deterministic-node cwd separates data root from scripts root.

The bug (pre-fix): every deterministic node bound ``cwd=PROJECT_ROOT``
(which honors ``HOMESTUDIO_PROJECT_ROOT``). When that env var pointed at
``tests/fixtures`` (which has no ``scripts/`` package),
``python -m scripts.pickup`` failed with
``ModuleNotFoundError: No module named 'scripts'``.

The fix: ``scripts_root()`` is the cwd for ``python -m scripts.X`` calls
— always the main git worktree root, never the env-var override.
``project_root()`` continues to govern where ``inbox/`` and ``episodes/``
live.

These tests pin both invariants so future refactors can't recreate the trap.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from edit_episode_graph._paths import project_root, repo_root, scripts_root
from edit_episode_graph.nodes import (
    glue_remap_transcript,
    isolate_audio,
    p4_scaffold,
    pickup,
)


@pytest.fixture
def fixture_data_root(tmp_path: Path, monkeypatch) -> Path:
    """A temp data root that has NO ``scripts/`` package next to it.

    Mirrors the canonical recipe (``HOMESTUDIO_PROJECT_ROOT=tests/fixtures``)
    that originally exposed the bug.
    """
    (tmp_path / "inbox").mkdir()
    (tmp_path / "episodes").mkdir()
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    return tmp_path


def test_scripts_root_independent_of_env_override(fixture_data_root: Path) -> None:
    """``scripts_root()`` ignores ``HOMESTUDIO_PROJECT_ROOT``."""
    assert project_root() == fixture_data_root
    sr = scripts_root()
    assert sr != fixture_data_root
    assert sr == repo_root()
    assert (sr / "scripts" / "__init__.py").is_file(), (
        f"scripts_root() must point at the directory containing the scripts/ package, got {sr}"
    )


def test_scripts_root_unaffected_when_env_var_unset(monkeypatch) -> None:
    """Without the env var, both helpers fall back to the same repo root."""
    monkeypatch.delenv("HOMESTUDIO_PROJECT_ROOT", raising=False)
    assert scripts_root() == repo_root()
    assert project_root() == repo_root()


@pytest.mark.parametrize(
    "module_name, attr_module",
    [
        ("pickup", pickup),
        ("isolate_audio", isolate_audio),
        ("p4_scaffold", p4_scaffold),
        ("glue_remap_transcript", glue_remap_transcript),
    ],
)
def test_deterministic_node_modules_use_scripts_root(module_name, attr_module) -> None:
    """Each deterministic-node module pins its cwd to ``scripts_root()``.

    Asserts the module-level constant the node binds for cwd points at the
    scripts package root (where ``scripts/__init__.py`` lives), NOT at the
    data root. This is the structural fix for the
    ``ModuleNotFoundError: No module named 'scripts'`` regression.
    """
    cwd_const = getattr(attr_module, "SCRIPTS_ROOT", None)
    assert cwd_const is not None, (
        f"{module_name}: expected module-level SCRIPTS_ROOT (subprocess cwd) to exist"
    )
    assert (cwd_const / "scripts" / "__init__.py").is_file(), (
        f"{module_name}: SCRIPTS_ROOT={cwd_const} does not contain scripts/__init__.py"
    )
    # And the bug-prone PROJECT_ROOT alias should not be used as cwd anymore.
    # pickup retains a PROJECT_ROOT constant only for absolutizing parsed
    # paths (--inbox/--episodes args); it should never be the subprocess cwd.


def test_pickup_cmd_uses_absolute_data_paths(fixture_data_root: Path, monkeypatch) -> None:
    """``pickup`` builds ``--inbox`` / ``--episodes`` as absolute paths.

    With ``HOMESTUDIO_PROJECT_ROOT`` pointed at a data dir lacking
    ``scripts/``, the absolute-path argv plus a ``cwd=scripts_root()``
    is the combo that makes pickup work.
    """
    # Reload pickup so it picks up the env-var-influenced project_root.
    # The module captures PROJECT_ROOT at import time; in normal Studio
    # usage the env var is set before import. In-test we monkeypatch
    # the module attribute to mirror that.
    monkeypatch.setattr(pickup, "PROJECT_ROOT", fixture_data_root)
    cmd = pickup._cmd({"slug": "demo"})
    # argv contract: python -m scripts.pickup --inbox <ABS> --episodes <ABS> [--slug demo]
    assert cmd[1:3] == ["-m", "scripts.pickup"]
    assert "--inbox" in cmd and "--episodes" in cmd
    inbox = Path(cmd[cmd.index("--inbox") + 1])
    episodes = Path(cmd[cmd.index("--episodes") + 1])
    assert inbox.is_absolute(), f"--inbox must be absolute, got {inbox}"
    assert episodes.is_absolute(), f"--episodes must be absolute, got {episodes}"
    assert inbox == fixture_data_root / "inbox"
    assert episodes == fixture_data_root / "episodes"
