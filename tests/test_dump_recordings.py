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
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from langgraph.cache.sqlite import SqliteCache

from tests.dump_recordings import (
    _node_name_from_ns,
    dump_recordings,
    main as cli_main,
)

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
    # 1-tuple synthetic ns: namespace cell is just the node name
    assert rec_a["namespace"] == "p3_strategy"
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


# ---------- HOM-182 bug fix: pregel-namespace ns shape -------------------


def test_node_name_extracted_from_pregel_namespace():
    """``ns`` from real `SqliteCache` writes is comma-joined; last
    segment is the canonical node name (per spec §4)."""
    real_ns = (
        "__pregel_ns_writes,edit_episode_graph.nodes.p4_beat.p4_beat_node,p4_beat"
    )
    assert _node_name_from_ns(real_ns) == "p4_beat"
    # 1-tuple namespace (synthetic seed) is already the bare node name
    assert _node_name_from_ns("p3_strategy") == "p3_strategy"
    # Deterministic-wrapper shape (closures show up as `<locals>`)
    deterministic = (
        "__pregel_ns_writes,edit_episode_graph.nodes._deterministic."
        "deterministic_node.<locals>.node,p4_scaffold"
    )
    assert _node_name_from_ns(deterministic) == "p4_scaffold"


def test_dump_uses_short_filename_under_pregel_namespace(tmp_path):
    """Bypassing `SqliteCache.set` to write a real-shape pregel ``ns``,
    we assert the produced filename is just ``<node>.json`` — short
    enough to survive Windows MAX_PATH under nested worktree paths."""
    slug = "fixture-mock"
    fixtures_root, episode, cache_db = _build_layout(tmp_path, slug)

    # Seed a row directly via raw SQL so we can plant a comma-joined
    # pregel-style ``ns`` (`SqliteCache.set` only takes tuple-ns keys).
    # Schema mirrors langgraph.cache.sqlite.SqliteCache.
    conn = sqlite3.connect(str(cache_db))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cache ("
        "ns TEXT NOT NULL, key TEXT NOT NULL, expiry REAL, "
        "encoding TEXT NOT NULL, val BLOB NOT NULL, "
        "PRIMARY KEY (ns, key))"
    )
    long_ns = (
        "__pregel_ns_writes,edit_episode_graph.nodes.p4_beat.p4_beat_node,p4_beat"
    )
    # Encode a trivial msgpack payload via the same serde the dump uses.
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    enc, raw = JsonPlusSerializer().dumps_typed({"v": 1})
    conn.execute(
        "INSERT INTO cache (ns, key, expiry, encoding, val) VALUES (?, ?, ?, ?, ?)",
        (long_ns, "fp-a", None, enc, raw),
    )
    conn.commit()
    conn.close()

    written = dump_recordings(slug, fixtures_root=fixtures_root)
    names = [p.name for p in written]
    assert names == ["p4_beat.json"], names
    rec = json.loads(written[0].read_text(encoding="utf-8"))
    assert rec["node"] == "p4_beat"
    assert rec["namespace"] == long_ns
    assert rec["fingerprint"] == "fp-a"
    # Sanity: filename length is reasonable (well under MAX_PATH-260
    # even nested deep in worktree paths).
    assert len(written[0].name) < 64


def test_dump_aggregates_multiple_pregel_rows_for_same_node(tmp_path):
    """Distinct pregel ``ns`` values that map to the same canonical
    node (e.g. p4_beat fan-out shards) collapse into a single
    ``<node>.json`` whose payload is a sorted list."""
    slug = "fixture-mock"
    fixtures_root, episode, cache_db = _build_layout(tmp_path, slug)

    conn = sqlite3.connect(str(cache_db))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cache ("
        "ns TEXT NOT NULL, key TEXT NOT NULL, expiry REAL, "
        "encoding TEXT NOT NULL, val BLOB NOT NULL, "
        "PRIMARY KEY (ns, key))"
    )
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    serde = JsonPlusSerializer()
    ns = (
        "__pregel_ns_writes,edit_episode_graph.nodes.p4_beat.p4_beat_node,p4_beat"
    )
    for fp, val in [("fp-z", {"v": 2}), ("fp-a", {"v": 1})]:
        enc, raw = serde.dumps_typed(val)
        conn.execute(
            "INSERT INTO cache (ns, key, expiry, encoding, val) VALUES (?, ?, ?, ?, ?)",
            (ns, fp, None, enc, raw),
        )
    conn.commit()
    conn.close()

    dump_recordings(slug, fixtures_root=fixtures_root)
    payload = json.loads(
        (episode / "recordings" / "p4_beat.json").read_text(encoding="utf-8")
    )
    assert isinstance(payload, list)
    assert [r["fingerprint"] for r in payload] == ["fp-a", "fp-z"]
    for r in payload:
        assert r["namespace"] == ns
        assert r["node"] == "p4_beat"


def test_safe_filename_rejects_path_separators():
    """Defensive: malformed ns mustn't escape recordings/."""
    from tests.dump_recordings import _safe_filename

    # Path separators are scrubbed (`.` is allowed since node names like
    # `foo.bar` are legal — defence is against `/` and `\`).
    assert _safe_filename("../etc/passwd") == ".._etc_passwd"
    assert _safe_filename("p4/beat") == "p4_beat"
    assert _safe_filename(r"p4\beat") == "p4_beat"
    assert _safe_filename("") == "unknown"
    # Allowed chars pass through.
    assert _safe_filename("p3_strategy") == "p3_strategy"
    assert _safe_filename("foo.bar-baz") == "foo.bar-baz"
