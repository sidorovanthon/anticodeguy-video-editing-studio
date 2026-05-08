"""Unit tests for :mod:`tests._helpers.replay_harness` (HOM-180).

These exercise the harness against a mock cache.db (built directly
through the public `SqliteCache` API on a temp dir) — no graph, no
real LLM. Spec §4: validate the three modes round-trip cleanly and
that replay-mode misses raise the canonical message.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
from langgraph.cache.sqlite import SqliteCache

from tests._helpers.replay_harness import (
    ENV_VAR,
    DEFAULT_MODE,
    ReplayCacheMissError,
    finalize_record_on_miss,
    mount_fixture_cache,
    open_cache,
    _resolve_mode,
)


# A FullKey value that is cheap to construct and round-trips through the
# native serde — `int` payload keeps the test independent of Pydantic.
_NS = ("p3_strategy",)
_FP = "fingerprint-abc"
_PAYLOAD = {"hello": "world", "n": 42}


def _seed_cache(path: Path, *, payload=_PAYLOAD) -> None:
    """Write one entry through a vanilla `SqliteCache`."""
    cache = SqliteCache(path=str(path))
    cache.set({(_NS, _FP): (payload, None)})
    # close underlying connection so file is flushed before we copy
    del cache


def _build_fixtures_root(tmp_path: Path, slug: str) -> Path:
    """Return a fixtures_root layout matching tests/fixtures/episodes/<slug>/."""
    fixtures_root = tmp_path / "fixtures"
    (fixtures_root / "episodes" / slug).mkdir(parents=True)
    return fixtures_root


# ---------- _resolve_mode --------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, DEFAULT_MODE),
        ("", DEFAULT_MODE),
        ("replay", "replay"),
        ("record-on-miss", "record-on-miss"),
        ("record", "record"),
    ],
)
def test_resolve_mode_valid(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv(ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(ENV_VAR, raw)
    assert _resolve_mode(None) == expected


def test_resolve_mode_invalid(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "garbage")
    with pytest.raises(ValueError, match="not a valid mode"):
        _resolve_mode(None)


def test_resolve_mode_explicit_overrides_env(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "record")
    assert _resolve_mode("replay") == "replay"


# ---------- replay mode ----------------------------------------------------


def test_replay_mode_hits_existing_recording(tmp_path):
    slug = "fixture-mock"
    fixtures_root = _build_fixtures_root(tmp_path, slug)
    fixture_path = fixtures_root / "episodes" / slug / "cache.db"
    _seed_cache(fixture_path)

    mounted = mount_fixture_cache(slug, mode="replay", fixtures_root=fixtures_root)
    assert mounted.mode == "replay"
    assert mounted.working_path == fixture_path

    cache = open_cache(mounted)
    got = cache.get([(_NS, _FP)])
    assert got == {(_NS, _FP): _PAYLOAD}


def test_replay_mode_miss_raises_with_canonical_message(tmp_path):
    slug = "fixture-mock"
    fixtures_root = _build_fixtures_root(tmp_path, slug)
    fixture_path = fixtures_root / "episodes" / slug / "cache.db"
    _seed_cache(fixture_path)  # has _NS/_FP only

    mounted = mount_fixture_cache(slug, mode="replay", fixtures_root=fixtures_root)
    cache = open_cache(mounted)

    # Attempting to write a brand-new entry simulates a graph node trying
    # to record a fresh result — must raise.
    with pytest.raises(ReplayCacheMissError) as ei:
        cache.set({(("p4_design_system",), "new-fp"): ({"x": 1}, None)})
    msg = str(ei.value)
    assert "no recording for node p4_design_system" in msg
    assert "new-fp" in msg
    assert "HOMESTUDIO_TEST_MODE=record-on-miss" in msg


def test_replay_mode_missing_fixture_raises(tmp_path):
    slug = "missing"
    fixtures_root = tmp_path / "fixtures"
    (fixtures_root / "episodes").mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="replay mode requires fixture"):
        mount_fixture_cache(slug, mode="replay", fixtures_root=fixtures_root)


def test_replay_mode_cache_is_read_only_at_sqlite_level(tmp_path):
    """Sanity: even if a caller bypasses the subclass and tries raw SQL,
    the underlying connection should be ``mode=ro``."""
    slug = "fixture-mock"
    fixtures_root = _build_fixtures_root(tmp_path, slug)
    fixture_path = fixtures_root / "episodes" / slug / "cache.db"
    _seed_cache(fixture_path)

    mounted = mount_fixture_cache(slug, mode="replay", fixtures_root=fixtures_root)
    cache = open_cache(mounted)
    with pytest.raises(sqlite3.OperationalError):
        cache._conn.execute(  # noqa: SLF001 — direct probe is the test
            "INSERT INTO cache (ns, key, expiry, encoding, val) "
            "VALUES (?, ?, NULL, 'json', ?)",
            ("p3_x", "fp", b"{}"),
        )


# ---------- record-on-miss -------------------------------------------------


def test_record_on_miss_seeds_from_existing_fixture(tmp_path):
    slug = "fixture-mock"
    fixtures_root = _build_fixtures_root(tmp_path, slug)
    fixture_path = fixtures_root / "episodes" / slug / "cache.db"
    _seed_cache(fixture_path)

    mounted = mount_fixture_cache(
        slug, mode="record-on-miss", fixtures_root=fixtures_root
    )
    assert mounted.mode == "record-on-miss"
    assert mounted.working_path != fixture_path
    assert mounted.working_path.exists()  # copied from fixture

    cache = open_cache(mounted)
    # Existing entry visible
    assert cache.get([(_NS, _FP)]) == {(_NS, _FP): _PAYLOAD}

    # New entry persisted
    new_key = (("p4_design_system",), "fp-new")
    cache.set({new_key: ({"v": 1}, None)})

    finalize_record_on_miss(mounted, cache)
    del cache  # close working

    # Reopen the fixture and confirm both old + new survived the VACUUM.
    re = SqliteCache(path=str(fixture_path))
    got = re.get([(_NS, _FP), new_key])
    assert got == {(_NS, _FP): _PAYLOAD, new_key: {"v": 1}}
    mounted.cleanup()


def test_record_on_miss_starts_empty_when_fixture_missing(tmp_path):
    slug = "fresh-fixture"
    fixtures_root = tmp_path / "fixtures"
    (fixtures_root / "episodes").mkdir(parents=True)
    # No cache.db at all yet — record-on-miss should still mount.

    mounted = mount_fixture_cache(
        slug, mode="record-on-miss", fixtures_root=fixtures_root
    )
    cache = open_cache(mounted)
    cache.set({(("p3_strategy",), "fp-1"): ({"x": 1}, None)})

    finalize_record_on_miss(mounted, cache)
    del cache

    assert mounted.fixture_path.exists()
    re = SqliteCache(path=str(mounted.fixture_path))
    got = re.get([(("p3_strategy",), "fp-1")])
    assert got == {(("p3_strategy",), "fp-1"): {"x": 1}}
    mounted.cleanup()


# ---------- record (full) --------------------------------------------------


def test_record_mode_starts_empty_even_with_existing_fixture(tmp_path):
    slug = "fixture-mock"
    fixtures_root = _build_fixtures_root(tmp_path, slug)
    fixture_path = fixtures_root / "episodes" / slug / "cache.db"
    _seed_cache(fixture_path, payload={"old": True})

    mounted = mount_fixture_cache(slug, mode="record", fixtures_root=fixtures_root)
    assert mounted.mode == "record"
    # Working file is fresh, even though fixture exists on disk.
    assert mounted.working_path != fixture_path
    assert not mounted.working_path.exists()  # empty until first write

    cache = open_cache(mounted)
    # The OLD payload must NOT be visible — record-mode is a fresh start.
    assert cache.get([(_NS, _FP)]) == {}

    cache.set({(("p3_strategy",), "fp-fresh"): ({"new": True}, None)})
    finalize_record_on_miss(mounted, cache)
    del cache

    re = SqliteCache(path=str(fixture_path))
    # Old key gone, new key present.
    assert re.get([(_NS, _FP)]) == {}
    assert re.get([(("p3_strategy",), "fp-fresh")]) == {
        (("p3_strategy",), "fp-fresh"): {"new": True}
    }
    mounted.cleanup()


# ---------- pytest fixture (replay_mode) -----------------------------------


def test_replay_mode_fixture_default(replay_mode, monkeypatch):
    # The conftest fixture reads the env var at fixture-setup time, so
    # to make this assertion robust we just confirm it's a legal mode.
    assert replay_mode in ("replay", "record-on-miss", "record")


def test_replay_mode_fixture_reads_env(monkeypatch, tmp_path):
    # Direct call to the resolver mirrors what the fixture does — keeps
    # the test deterministic without re-running pytest under a child env.
    monkeypatch.setenv(ENV_VAR, "record-on-miss")
    assert _resolve_mode(None) == "record-on-miss"
    monkeypatch.delenv(ENV_VAR)
    assert _resolve_mode(None) == DEFAULT_MODE
