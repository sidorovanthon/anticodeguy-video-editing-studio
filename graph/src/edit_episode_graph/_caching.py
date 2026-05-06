"""Cache-key helper for `langgraph.types.CachePolicy`.

Per spec `docs/superpowers/specs/2026-05-06-langgraph-node-caching-design.md`
§5.3, this module is the single canonical place where we build node cache
keys. Each cached node module imports `make_key`, defines a per-node
`_CACHE_VERSION`, and exposes a `CACHE_POLICY = CachePolicy(key_func=...)`
constant for `graph.py` to wire via `add_node(..., cache_policy=...)`.

Design choices live in the spec; this file only implements them.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

_CHUNK = 64 * 1024


def file_fingerprint(path: str | Path | None) -> str:
    """Return sha256 hex of file content, or ``"absent"`` if missing/empty path.

    Content-hashing (vs mtime+size) is deliberate: mtime lies after
    ``git checkout``, ``cp -p``, restore-from-trash. Spec §5.3.
    """
    if not path:
        return "absent"
    p = Path(path)
    if not p.exists():
        return "absent"
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def make_key(
    *,
    node: str,
    version: int,
    slug: str,
    files: Iterable[str | Path | None] = (),
    extras: Iterable[object] = (),
) -> str:
    """Build a deterministic cache key for a graph node.

    - ``node`` + ``version`` literal makes brief/schema bumps invalidate
      (per-node ``_CACHE_VERSION`` constant; bump on brief / schema /
      tool-list change — see spec §8 review checkpoint).
    - ``slug`` namespaces per-episode.
    - ``files`` are content-hashed via :func:`file_fingerprint`; edits
      or deletions invalidate naturally.
    - ``extras`` is an optional iterable of stable scalars (e.g. iteration
      counter) appended verbatim via ``repr``.
    """
    parts = [node, f"v{version}", slug]
    parts.extend(file_fingerprint(p) for p in files)
    parts.extend(repr(x) for x in extras)
    return "|".join(parts)
