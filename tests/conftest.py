"""Pytest configuration shared across the orchestrator test suite.

Exposes:

* ``replay_mode`` fixture (HOM-180) — resolved value of
  ``HOMESTUDIO_TEST_MODE``.
* ``--dump-recordings <slug>`` CLI option (HOM-182) — runs
  :func:`tests.dump_recordings.dump_recordings` for the given slug on
  ``pytest_sessionfinish``. Also auto-fires when
  ``HOMESTUDIO_TEST_MODE in ("record-on-miss", "record")`` and the slug
  is supplied — keeps the JSON companion in sync with the cache.db
  writeback without an extra command.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tests._helpers.replay_harness import Mode, _resolve_mode
from tests.dump_recordings import dump_recordings


@pytest.fixture
def replay_mode() -> Mode:
    """Resolved value of ``HOMESTUDIO_TEST_MODE`` (default ``replay``).

    Tests should branch off this rather than reading the env var
    themselves so the default is centralized in one place (spec §4
    open question 3 — env var unset = ``replay``, the safe default).
    """
    return _resolve_mode(None)


# ---------- --dump-recordings plugin hook ---------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the ``--dump-recordings`` flag.

    HOM-182 / spec §4: an explicit flag for "after this test session,
    dump cache.db to JSON for review". Independent of the auto-dump on
    record-on-miss — useful for refreshing JSON without re-running any
    tests, and for sessions that didn't touch cache.db at all.
    """
    parser.addoption(
        "--dump-recordings",
        action="store",
        default=None,
        metavar="SLUG",
        help=(
            "After the session finishes, dump tests/fixtures/episodes/"
            "<SLUG>/cache.db rows to recordings/<node>.json (HOM-182)."
        ),
    )


def pytest_sessionfinish(
    session: pytest.Session, exitstatus: int
) -> None:  # noqa: ARG001
    """Auto-dump on session finish.

    Triggers when:

    * ``--dump-recordings <slug>`` was passed explicitly, OR
    * ``HOMESTUDIO_TEST_MODE`` is ``record`` / ``record-on-miss`` AND
      ``--dump-recordings <slug>`` was passed (we still need a slug — the
      harness doesn't track which slug was mounted from a session-wide
      hook).

    The "auto on record" path therefore still requires the user to
    supply the slug; the convenience is that they don't need to *also*
    re-run a separate dump command.
    """
    slug = session.config.getoption("--dump-recordings")
    if not slug:
        return
    try:
        written = dump_recordings(slug)
    except FileNotFoundError as e:
        # Don't fail the test session if there is no cache.db yet — a
        # record-from-scratch run that errored out before the first
        # write would land here. Surface a clear message and move on.
        print(f"[dump-recordings] {e}", file=sys.stderr)
        return
    mode = _resolve_mode(None)
    print(
        f"[dump-recordings] mode={mode} slug={slug} wrote {len(written)} file(s):",
        file=sys.stderr,
    )
    for p in written:
        try:
            rel = p.relative_to(Path.cwd())
        except ValueError:
            rel = p
        print(f"  {rel}", file=sys.stderr)
