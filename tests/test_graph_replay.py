"""Graph-replay smoke surface (HOM-180 placeholder).

Per spec §4 / HOM-180 DoD: the harness module must be exercisable end-
to-end without a real graph. Subsequent tickets (HOM-181+, M6 wave
work) plug actual node-replays into this file under names like
``test_p3_strategy_smoke``. For HOM-180 we only verify the harness
itself round-trips.
"""

from __future__ import annotations

from pathlib import Path

from langgraph.cache.sqlite import SqliteCache

from tests._helpers.replay_harness import (
    finalize_record_on_miss,
    mount_fixture_cache,
    open_cache,
)


def test_replay_harness_smoke(tmp_path):
    """Mount a synthetic fixture, open the cache, do a get, close.

    No real graph. Demonstrates the full HOM-180 contract: mount
    seeds the working file, ``open_cache`` returns a usable
    `SqliteCache`-shaped object, the canonical entry round-trips,
    teardown is clean.
    """
    slug = "smoke-fixture"
    fixtures_root = tmp_path / "fixtures"
    fixture_dir = fixtures_root / "episodes" / slug
    fixture_dir.mkdir(parents=True)
    fixture_path = fixture_dir / "cache.db"

    # Pre-seed via the public API so the file is in canonical form.
    seed = SqliteCache(path=str(fixture_path))
    key = (("p3_pre_scan",), "fp-smoke")
    seed.set({key: ({"slug": slug, "ok": True}, None)})
    del seed

    # --- replay round-trip ---
    mounted = mount_fixture_cache(slug, mode="replay", fixtures_root=fixtures_root)
    cache = open_cache(mounted)
    assert cache.get([key]) == {key: {"slug": slug, "ok": True}}
    # Close the read-only handle so the next phase's atomic rename can
    # overwrite the fixture on Windows (POSIX would not need this).
    cache._conn.close()  # noqa: SLF001 — explicit handle release

    # --- record-on-miss round-trip (writes a new entry, persists) ---
    mounted_rec = mount_fixture_cache(
        slug, mode="record-on-miss", fixtures_root=fixtures_root
    )
    cache_rec = open_cache(mounted_rec)
    new_key = (("p4_design_system",), "fp-smoke-2")
    cache_rec.set({new_key: ({"design": "ok"}, None)})
    finalize_record_on_miss(mounted_rec, cache_rec)
    del cache_rec
    mounted_rec.cleanup()

    # The persisted fixture now contains BOTH entries.
    re = SqliteCache(path=str(fixture_path))
    got = re.get([key, new_key])
    assert got == {key: {"slug": slug, "ok": True}, new_key: {"design": "ok"}}
