"""Dump prewarmed `cache.db` rows to per-node JSON for PR review.

HOM-182 / spec §4 (JSON dump CLI). The committed `cache.db` is the
canonical fixture, but it is binary, so PR diffs are unreadable. This
module walks the raw SQLite rows produced by
:class:`langgraph.cache.sqlite.SqliteCache`, decodes the msgpack payload
through the same serde the cache uses, and writes one canonically-sorted
JSON file per node into ``tests/fixtures/episodes/<slug>/recordings/``.

Reviewers diff the JSON, not the binary.

Schema of each ``<node_name>.json`` (per spec §4 / HOM-182):

```json
{
  "node": "p3_strategy",
  "namespace": "__pregel_ns_writes,edit_episode_graph.nodes.p3_strategy.p3_strategy_node,p3_strategy",
  "fingerprint": "p3_strategy|v3|fixture-canonical-portrait-talking-head|<hash>|cfg:<sha>",
  "channel_writes": <decoded payload, JSON-shaped where possible>,
  "recorded_at": "2026-05-08T12:34:56+00:00",
  "recording_meta": {"encoding": "msgpack", "value_bytes": 1234}
}
```

When more than one cache row is recorded under the same node (e.g.
``p4_beat`` fanned out across N beats produces N rows with distinct
fingerprints), the JSON file becomes a sorted list of records instead of
a single object. Single-entry files stay bare objects to match the spec
example shape.

Filenames are ``<node_name>.json`` per spec §4 — the canonical node name
extracted from ``ns`` (the last comma-joined segment of LangGraph's
pregel-namespaced cache key). The full ``ns`` string is preserved inside
each record under ``namespace`` so reviewers don't lose the pregel-write
context. This keeps paths short enough to survive Windows MAX_PATH (260)
under nested worktree checkouts — the previous shape (full module path
in the filename) hit ``Filename too long`` from ``git add``.

Field provenance (matters for spec amendments / future readers):

* ``node``: canonical node name — last comma-segment of the SQLite
  ``ns`` column. For LLM nodes ``ns`` looks like
  ``__pregel_ns_writes,<full_module_path>.<wrapper>,<node_name>``; we
  split and keep only ``<node_name>``.
* ``namespace``: the raw ``ns`` column verbatim, retained in-record so
  pregel-write provenance is not lost when the filename is shortened.
* ``fingerprint``: comes from the SQLite ``key`` column verbatim. For
  LLM nodes this is a ``|``-delimited string produced by
  :func:`graph._caching.make_llm_key` (already a stable identifier;
  bumping brief / schema / tier flips it).
* ``channel_writes``: msgpack payload run through the cache's
  ``serde.loads_typed``. For JSON-native shapes (the vast majority,
  Pydantic ``model_dump()`` outputs are dicts/strs/numbers) this lands
  as a plain JSON dict. For genuinely opaque values (raw bytes,
  non-serializable-only objects) we fall back to ``"<binary blob N bytes>"``
  / ``repr()`` so the diff still shows a delta.
* ``recorded_at``: derived from the SQLite ``expiry`` column **only when
  the row carried a TTL**. LangGraph's `SqliteCache` doesn't store the
  absolute set-time, so for the common no-TTL case this is ``null``.
  Documented as a known limitation; spec §4 calls for a recorded_at
  field but the native primitive doesn't supply one — JSON file mtime
  is the fallback for review.
* ``recording_meta.encoding``: SQLite ``encoding`` column (``"msgpack"``
  for the default JsonPlusSerializer; could be ``"json"`` for legacy).
* ``recording_meta.value_bytes``: byte size of the raw stored blob; a
  cheap signal for "did this output grow 100x?" review without
  decoding.

The spec's ``recording_meta.model`` / ``recording_meta.tier`` fields are
**not represented here**: that information is part of the cache *key*
(``cfg:<sha>`` extras inside the fingerprint string), not the cached
value, and the SHA is one-way. Reviewers infer model/tier shifts from a
fingerprint diff, not from a meta block.

CLI:

```
python -m tests.dump_recordings <slug>
python -m tests.dump_recordings <slug> --fixtures-root tests/fixtures
```

Pytest plugin:

```
python -m pytest --dump-recordings=<slug>
```

The pytest hook (defined in :mod:`tests.conftest`) calls
:func:`dump_recordings` on session finish for the supplied slug, so a
``record-on-miss`` run automatically refreshes the JSON companion.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


def _project_root() -> Path:
    """Return the project root for path defaults."""
    return Path(__file__).resolve().parents[1]


def _default_fixtures_root() -> Path:
    return _project_root() / "tests" / "fixtures"


def _episode_dir(slug: str, fixtures_root: Path) -> Path:
    return fixtures_root / "episodes" / slug


def _node_name_from_ns(ns: str) -> str:
    """Extract the canonical node name from a SQLite ``ns`` cell.

    LangGraph's `SqliteCache` joins namespace tuples with ``,``. For the
    pregel-write namespace shape — ``__pregel_ns_writes,<module>,<node>``
    — the canonical node name is the last comma-segment. For 1-tuple
    namespaces seeded directly (e.g. unit tests) the value is already
    just the node name.
    """
    return ns.rsplit(",", 1)[-1].strip() or ns


def _safe_filename(node_name: str) -> str:
    """Sanitize a node name for use as a JSON filename.

    Node names are Python identifiers in practice, but we still defend
    against path separators and control characters so a malformed ``ns``
    can't escape the recordings directory.
    """
    safe = "".join(
        ch if (ch.isalnum() or ch in "_.-") else "_" for ch in node_name
    )
    return safe or "unknown"


def _to_json_shape(value: Any) -> Any:
    """Coerce a decoded payload into something ``json.dumps`` can serialize."""

    def _coerce(v: Any) -> Any:
        if v is None or isinstance(v, (bool, int, float, str)):
            return v
        if isinstance(v, dict):
            return {str(k): _coerce(v[k]) for k in v}
        if isinstance(v, (list, tuple)):
            return [_coerce(x) for x in v]
        if isinstance(v, (set, frozenset)):
            return sorted(
                (_coerce(x) for x in v),
                key=lambda x: json.dumps(x, sort_keys=True, default=str),
            )
        if isinstance(v, (bytes, bytearray)):
            return f"<binary blob {len(v)} bytes>"
        if isinstance(v, datetime):
            return v.isoformat()
        for attr in ("model_dump", "dict"):
            fn = getattr(v, attr, None)
            if callable(fn):
                try:
                    return _coerce(fn())
                except Exception:  # noqa: BLE001
                    pass
        return repr(v)

    return _coerce(value)


def _decode_value(serde: Any, encoding: str, raw: bytes) -> Any:
    """Decode a stored cache value through the cache serde."""
    try:
        decoded = serde.loads_typed((encoding, raw))
    except Exception as e:  # noqa: BLE001 — opaque payload is the point
        return {
            "__decode_error__": f"{type(e).__name__}: {e}",
            "__raw_bytes__": len(raw),
        }
    return _to_json_shape(decoded)


def _read_rows(
    cache_db_path: Path,
) -> Iterable[tuple[str, str, float | None, str, bytes]]:
    """Read raw cache rows in deterministic (ns, key) order, read-only."""
    if not cache_db_path.exists():
        raise FileNotFoundError(f"cache.db not found at {cache_db_path}")
    uri = cache_db_path.as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cursor = conn.execute(
            "SELECT ns, key, expiry, encoding, val FROM cache ORDER BY ns, key"
        )
        return list(cursor.fetchall())
    finally:
        conn.close()


def _build_record(
    *,
    ns: str,
    key: str,
    expiry: float | None,
    encoding: str,
    raw: bytes,
    serde: Any,
) -> dict[str, Any]:
    """Build the per-row JSON record (one cache entry → one dict)."""
    decoded = _decode_value(serde, encoding, raw)
    rec: dict[str, Any] = {
        "node": _node_name_from_ns(ns),
        "namespace": ns,
        "fingerprint": key,
        "channel_writes": decoded,
        "recorded_at": (
            datetime.fromtimestamp(expiry, tz=timezone.utc).isoformat()
            if expiry is not None
            else None
        ),
        "recording_meta": {
            "encoding": encoding,
            "value_bytes": len(raw),
        },
    }
    return rec


def dump_recordings(
    slug: str,
    *,
    fixtures_root: Path | None = None,
    cache_db_path: Path | None = None,
    recordings_dir: Path | None = None,
) -> list[Path]:
    """Dump every cache row for ``slug`` into per-node JSON files.

    Returns the list of file paths written, sorted by node name.
    """
    if fixtures_root is None:
        fixtures_root = _default_fixtures_root()
    if cache_db_path is None:
        cache_db_path = _episode_dir(slug, fixtures_root) / "cache.db"
    if recordings_dir is None:
        recordings_dir = _episode_dir(slug, fixtures_root) / "recordings"

    by_node: dict[str, list[dict[str, Any]]] = {}

    # Use the same serde LangGraph's SqliteCache uses by default
    # (`JsonPlusSerializer`). Instantiated directly so the dump never
    # touches a SQLite file other than the canonical fixture being read.
    serde = JsonPlusSerializer()

    for ns, key, expiry, encoding, raw in _read_rows(cache_db_path):
        rec = _build_record(
            ns=ns,
            key=key,
            expiry=expiry,
            encoding=encoding,
            raw=raw,
            serde=serde,
        )
        by_node.setdefault(_node_name_from_ns(ns), []).append(rec)

    recordings_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for node, records in sorted(by_node.items()):
        # Stable sort key: (namespace, fingerprint). Namespace is the
        # primary discriminator when two distinct ns rows happen to
        # collapse onto the same canonical node name (defence-in-depth —
        # in practice ns→node is many:one only for synthetic seeds).
        records.sort(key=lambda r: (r.get("namespace", ""), r["fingerprint"]))
        # Single-entry: write a bare object (matches spec example shape).
        # Multi-entry: write a sorted list so all variants are visible.
        payload: Any = records[0] if len(records) == 1 else records
        out = recordings_dir / f"{_safe_filename(node)}.json"
        text = json.dumps(
            payload, sort_keys=True, indent=2, ensure_ascii=False
        )
        out.write_text(text + "\n", encoding="utf-8", newline="\n")
        written.append(out)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tests.dump_recordings",
        description="Dump prewarmed cache.db rows to per-node JSON files.",
    )
    parser.add_argument(
        "slug", help="Episode slug (under tests/fixtures/episodes/)"
    )
    parser.add_argument(
        "--fixtures-root",
        type=Path,
        default=None,
        help="Override fixtures root (default: <project>/tests/fixtures).",
    )
    parser.add_argument(
        "--cache-db",
        type=Path,
        default=None,
        help="Override cache.db path (default: <fixtures>/episodes/<slug>/cache.db).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Override recordings output dir (default: <fixtures>/episodes/<slug>/recordings).",
    )
    args = parser.parse_args(argv)

    written = dump_recordings(
        args.slug,
        fixtures_root=args.fixtures_root,
        cache_db_path=args.cache_db,
        recordings_dir=args.out_dir,
    )
    if not written:
        print(
            f"warning: no rows found in cache.db for slug={args.slug!r}; "
            f"nothing written",
            file=sys.stderr,
        )
        return 0
    for p in written:
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
