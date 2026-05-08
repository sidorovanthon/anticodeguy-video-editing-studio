"""Pytest configuration shared across the orchestrator test suite.

Currently exposes the ``replay_mode`` fixture (HOM-180) so any future
``test_graph_replay.py`` test can pick it up without re-importing the
harness directly.
"""

from __future__ import annotations

import pytest

from tests._helpers.replay_harness import Mode, _resolve_mode


@pytest.fixture
def replay_mode() -> Mode:
    """Resolved value of ``HOMESTUDIO_TEST_MODE`` (default ``replay``).

    Tests should branch off this rather than reading the env var
    themselves so the default is centralized in one place (spec §4
    open question 3 — env var unset = ``replay``, the safe default).
    """
    return _resolve_mode(None)
