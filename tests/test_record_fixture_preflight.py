"""Unit tests for the HOM-307 preflight in :mod:`scripts.record_fixture`.

The preflight must abort with exit code 2 before any LangGraph import or
``SqliteCache`` mount when its checks fail — verifying that property is
the whole point of running this $0 test before a $3–12 paid prewarm.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# scripts.record_fixture has module-level side effects (env pin, sys.path
# mutation). Importing it is acceptable — those are idempotent and do not
# import edit_episode_graph. The graph imports live inside main() and
# run_preflight() defers project_root_fn import too.
from scripts import record_fixture as rf


@pytest.fixture(autouse=True)
def _block_graph_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if the test path imports edit_episode_graph.

    Guarantees the preflight does not touch the LangGraph compile path.
    Modules already imported are left alone (other tests may have loaded
    them); we only assert no NEW import happens during this test.
    """
    already = set(sys.modules)

    yield  # type: ignore[misc]

    new = set(sys.modules) - already
    leaked = [m for m in new if m.startswith("edit_episode_graph") or m.startswith("langgraph")]
    assert not leaked, f"preflight leaked LangGraph imports: {leaked}"


def test_run_preflight_aborts_when_project_root_outside_fixtures(
    tmp_path: Path,
) -> None:
    """A project_root() outside tests/fixtures must trip check 1 and exit 2.

    Mocks ``project_root_fn`` to return ``tmp_path`` (which does NOT
    contain ``tests/fixtures``). The preflight must exit non-zero on
    check 1 and never reach the SqliteCache mount.
    """
    bogus_root = tmp_path / "C--Temp--nope"
    bogus_root.mkdir()

    rc = rf.run_preflight(
        "canonical-portrait-talking-head",
        project_root_fn=lambda: bogus_root,
    )

    assert rc != 0, "preflight must abort on out-of-fixtures project_root"
    assert rc == 2, f"expected exit code 2, got {rc}"


def test_run_preflight_aborts_when_episode_dir_missing(
    tmp_path: Path,
) -> None:
    """A path under tests/fixtures but with no episode dir must trip check 1."""
    fake_fixtures = tmp_path / "tests" / "fixtures"
    fake_fixtures.mkdir(parents=True)

    rc = rf.run_preflight(
        "canonical-portrait-talking-head",
        project_root_fn=lambda: fake_fixtures,
    )

    assert rc == 2


def test_satisfies_pin_compat() -> None:
    """Crude semver pin satisfier — npm caret semantics, incl. 0.x special case."""
    assert rf._satisfies_pin("0.4.42", "^0.4.39")
    assert rf._satisfies_pin("0.4.39", "^0.4.39")
    assert not rf._satisfies_pin("0.4.38", "^0.4.39")
    assert not rf._satisfies_pin("1.0.0", "^0.4.39")  # major mismatch
    assert rf._satisfies_pin("0.34.5", "~0.34.5")
    assert rf._satisfies_pin("0.34.10", "0.34.5")

    # npm caret on 0.x: ^0.4.39 means >=0.4.39 <0.5.0 — minor must match.
    assert not rf._satisfies_pin("0.5.0", "^0.4.39")  # crosses 0.x minor boundary
    assert rf._satisfies_pin("0.4.40", "^0.4.39")
    assert not rf._satisfies_pin("0.4.38", "^0.4.39")  # below pin

    # ≥1.x: caret allows any minor/patch within the same major.
    assert rf._satisfies_pin("1.5.0", "^1.4.39")
    assert not rf._satisfies_pin("2.0.0", "^1.4.39")  # major mismatch
