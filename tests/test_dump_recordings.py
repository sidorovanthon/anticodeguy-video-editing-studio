"""Unit tests for :mod:`tests.dump_recordings` (HOM-182).

These build a tiny synthetic ``cache.db`` through the **real**
``langgraph.cache.sqlite.SqliteCache`` API (so the schema and serde are
genuinely live, not mocked), then run the dump CLI / function against it
and assert:

* shape of the per-node JSON files matches spec §4,
* JSON output is canonically sorted + stable across re-records,
* round-trip — record same content twice, dump both times → identical
  bytes (the whole point: reproducible diffs).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from langgraph.cache.sqlite import SqliteCache

from tests.dump_recordings import dump_recordings, main as cli_main

_NS_A = ("p3_strategy",)
_NS_B = ("p4_design_system",)


def _seed(path: Path, entries: list[tuple[tuple[tuple[str, ...], str], object]]) -> None:
    """Write ``entries`` through a fresh `SqliteCache` (closes after)."""
    cache = SqliteCache(path=str(path))
    cache.set({k: (v, None) for k, v in entries})
    cache._conn.close()  # noqa: SLF001 — needed on Windows before file moves
    del cache


def _build_layout(tmp_path: Path, slug: str) -> tuple[Path, Path, Path]:
    fixtures_root = tmp_path / "fixtures"
    episode = fixtures_root / "episodes" / slug
    episode.mkdir(parents=True)
    cache_db = episode / "cache.db"
    return fixtures_root, episode, cache_db


# ---------- function-level: shape + content ------------------------------


def test_dump_writes_one_file_per_node(tmp_path):
    slug = "fixture-mock"
    fixtures_root, episode, cache_db = _build_layout(tmp_path, slug)
    _seed(
        cache_db,
        [
            ((_NS_A, "fp-a"), {"selected": ["scene-1", "scene-2"]}),
            ((_NS_B, "fp-b"), {"palette": ["#fff", "#000"]}),
        ],
    )

    written = dump_recordings(slug, fixtures_root=fixtures_root)
    names = sorted(p.name for p in written)
    assert names == ["p3_strategy.json", "p4_design_system.json"]

    rec_a = json.loads((episode / "recordings" / "p3_strategy.json").read_text(encoding="utf-8"))
    assert rec_a["node"] == "p3_strategy"
    assert rec_a["fingerprint"] == "fp-a"
    assert rec_a["channel_writes"] == {"selected": ["scene-1", "scene-2"]}
    assert rec_a["recorded_at"] is None
    assert rec_a["recording_meta"]["encoding"] == "msgpack"
    assert rec_a["recording_meta"]["value_bytes"] > 0


def test_dump_groups_multiple_entries_per_node(tmp_path):
    """Two cache rows for the same node → JSON is a sorted list."""
    slug = "fixture-mock"
    fixtures_root, episode, cache_db = _build_layout(tmp_path, slug)
    _seed(
        cache_db,
        [
            ((_NS_A, "fp-z"), {"v": 2}),
            ((_NS_A, "fp-a"), {"v": 1}),
        ],
    )

    dump_recordings(slug, fixtures_root=fixtures_root)
    payload = json.loads(
        (episode / "recordings" / "p3_strategy.json").read_text(encoding="utf-8")
    )
    assert isinstance(payload, list)
    # Sorted by fingerprint regardless of insert order
    assert [r["fingerprint"] for r in payload] == ["fp-a", "fp-z"]


def test_dump_canonical_formatting(tmp_path):
    """Output is sorted-keys, indent=2, trailing newline, UTF-8."""
    slug = "fixture-mock"
    fixtures_root, episode, cache_db = _build_layout(tmp_path, slug)
    _seed(
        cache_db,
        [
            (
                (_NS_A, "fp-a"),
                {"zeta": 1, "alpha": "héllo", "mid": ["b", "a"]},
            ),
        ],
    )

    dump_recordings(slug, fixtures_root=fixtures_root)
    text = (episode / "recordings" / "p3_strategy.json").read_text(encoding="utf-8")
    # trailing newline
    assert text.endswith("\n")
    # sorted keys: 'alpha' before 'zeta' textually
    assert text.index('"alpha"') < text.index('"zeta"')
    # indent=2: nested dicts indented two spaces
    assert "\n  " in text
    # ensure_ascii=False: non-ASCII preserved literally
    assert "héllo" in text


def test_round_trip_identical_bytes(tmp_path):
    """Record same content twice → dumped JSON is byte-for-byte identical.

    This is the spec §4 reproducibility guarantee: the JSON dump is the
    review surface, so if you re-record-with-no-changes, the diff must
    be empty. Tests sort_keys + indent + insert-order-insensitivity.
    """
    slug = "fixture-mock"

    def _run(seed_order):
        fixtures_root = tmp_path / f"run-{id(seed_order)}"
        episode = fixtures_root / "episodes" / slug
        episode.mkdir(parents=True)
        cache_db = episode / "cache.db"
        _seed(cache_db, seed_order)
        dump_recordings(slug, fixtures_root=fixtures_root)
        return (episode / "recordings" / "p3_strategy.json").read_bytes()

    # Same content, different insert order — bytes must match.
    a = _run(
        [
            ((_NS_A, "fp-a"), {"k": "v", "n": 1}),
            ((_NS_A, "fp-b"), {"k": "v", "n": 2}),
        ]
    )
    b = _run(
        [
            ((_NS_A, "fp-b"), {"n": 2, "k": "v"}),
            ((_NS_A, "fp-a"), {"n": 1, "k": "v"}),
        ]
    )
    assert a == b, "JSON dump is not deterministic across insert order"


def test_dump_missing_cache_db_raises(tmp_path):
    fixtures_root = tmp_path / "fixtures"
    (fixtures_root / "episodes" / "nope").mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="cache.db not found"):
        dump_recordings("nope", fixtures_root=fixtures_root)


def test_dump_does_not_mutate_cache_db(tmp_path):
    """Read-only open: cache.db bytes don't change across a dump.

    Spec §4 stability concern: dumping must not perturb the canonical
    fixture. We sha256 the file before and after.
    """
    import hashlib

    slug = "fixture-mock"
    fixtures_root, episode, cache_db = _build_layout(tmp_path, slug)
    _seed(cache_db, [((_NS_A, "fp-a"), {"v": 1})])

    before = hashlib.sha256(cache_db.read_bytes()).hexdigest()
    dump_recordings(slug, fixtures_root=fixtures_root)
    after = hashlib.sha256(cache_db.read_bytes()).hexdigest()
    assert before == after


def test_dump_handles_datetimes_and_bytes(tmp_path):
    """Non-JSON-native values still produce a readable JSON record."""
    import datetime as dt

    slug = "fixture-mock"
    fixtures_root, episode, cache_db = _build_layout(tmp_path, slug)
    _seed(
        cache_db,
        [
            (
                (_NS_A, "fp-a"),
                {
                    "when": dt.datetime(2026, 5, 8, 12, 0, 0),
                    "blob": b"\x00\x01\x02",
                },
            ),
        ],
    )

    dump_recordings(slug, fixtures_root=fixtures_root)
    rec = json.loads(
        (episode / "recordings" / "p3_strategy.json").read_text(encoding="utf-8")
    )
    cw = rec["channel_writes"]
    assert cw["when"].startswith("2026-05-08T12:00:00")
    assert cw["blob"] == "<binary blob 3 bytes>"


# ---------- CLI entry point ----------------------------------------------


def test_cli_main_writes_files(tmp_path, capsys):
    slug = "fixture-mock"
    fixtures_root, episode, cache_db = _build_layout(tmp_path, slug)
    _seed(cache_db, [((_NS_A, "fp-a"), {"v": 1})])

    rc = cli_main([slug, "--fixtures-root", str(fixtures_root)])
    assert rc == 0
    captured = capsys.readouterr()
    # Path printed to stdout
    assert "p3_strategy.json" in captured.out


def test_cli_module_invocation_smoke(tmp_path):
    """``python -m tests.dump_recordings`` runs end-to-end."""
    slug = "fixture-mock"
    fixtures_root, episode, cache_db = _build_layout(tmp_path, slug)
    _seed(cache_db, [((_NS_A, "fp-a"), {"v": 1})])

    project_root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.dump_recordings",
            slug,
            "--fixtures-root",
            str(fixtures_root),
        ],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"stderr={proc.stderr}"
    assert "p3_strategy.json" in proc.stdout
    assert (episode / "recordings" / "p3_strategy.json").exists()
