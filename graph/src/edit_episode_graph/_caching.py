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
import json
from pathlib import Path
from typing import Any, Iterable

_CHUNK = 64 * 1024


def stable_fingerprint(value: Any) -> str:
    """Stable sha256 hex of any JSON-serialisable value.

    Used by node `_cache_key` functions to fingerprint in-memory state
    that is rendered verbatim into the brief but is NOT covered by an
    upstream file. `sort_keys=True` makes the digest order-independent for
    dicts; `default=str` is a defensive fall-through for non-JSON scalars
    (e.g. Path) that occasionally land in compose namespaces.
    """
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def strategy_fingerprint(strategy: dict | None) -> str:
    """Fingerprint a `state.edit.strategy` dict, excluding non-content metadata.

    `source_path` is a filesystem locator, not output-affecting content;
    `skipped`/`skip_reason` are transient skip markers that should not
    namespace a successful run away from a prior skipped run.
    """
    stable = {
        k: v for k, v in (strategy or {}).items()
        if k not in {"source_path", "skipped", "skip_reason"}
    }
    return stable_fingerprint(stable)


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


def node_config_fingerprint(node_name: str) -> str:
    """Stable fingerprint of the effective `NodeConfig` for an LLM node.

    HOM-157: the inputs that determine an LLM node's output are not just
    its brief and upstream artifacts — they also include the per-node
    routing config from ``graph/config.yaml`` (``tier``, ``model``,
    ``backend_preference``, ``timeout_s``). Two prior runs with the same
    slug + same upstream files but different ``timeout_s`` are NOT the
    same function-of-input: one may exhaust backends where the other
    succeeds. Including this fingerprint in the cache key makes a config
    bump invalidate the affected node naturally — no manual cache wipe,
    no SqliteCache override, no swallow-vs-raise tradeoff.

    Resolution goes through ``load_default_config().resolve_node`` so
    pattern-glob overrides + defaults are applied identically to how the
    router resolves them at dispatch time. Resolved on every key build —
    ``load_default_config`` is itself ``lru_cache``'d, so the cost is one
    YAML parse per process.
    """
    # Local import: `_caching` is imported by every node module, while
    # `config` is leaf-level. Top-level import works fine today, but a
    # local import keeps the dependency direction unambiguous and avoids
    # surprising future readers.
    from .config import load_default_config
    cfg = load_default_config().resolve_node(node_name)
    return stable_fingerprint({
        "tier": cfg.tier,
        "backend_preference": cfg.backend_preference,
        "timeout_s": cfg.timeout_s,
        "model": cfg.model,
    })


def make_llm_key(
    *,
    node: str,
    version: int,
    slug: str,
    files: Iterable[str | Path | None] = (),
    extras: Iterable[object] = (),
) -> str:
    """Build a cache key for an LLM node, baking in routing-config fingerprint.

    Identical signature to :func:`make_key`; the only difference is an
    auto-prepended ``cfg:<sha>`` extra resolved via
    :func:`node_config_fingerprint`. Use from any node whose dispatch
    goes through ``LLMNode`` (i.e. is sensitive to ``graph/config.yaml``).
    Deterministic nodes (ffmpeg, file-IO) keep using :func:`make_key`.
    """
    cfg_fp = node_config_fingerprint(node)
    return make_key(
        node=node, version=version, slug=slug, files=files,
        extras=(f"cfg:{cfg_fp}", *extras),
    )
