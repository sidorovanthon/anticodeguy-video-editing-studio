"""HOM-157: cache key for LLM nodes invalidates when graph/config.yaml changes.

Symptom (ticket repro): operator bumps ``p3_strategy.timeout_s`` from 120 →
300 to fix a flaky-timeout failure; submits a fresh thread on the same slug;
fresh thread serves the cached failure verbatim because the cache key
didn't include ``timeout_s``.

Fix: ``make_llm_key`` resolves the effective ``NodeConfig`` via
``load_default_config().resolve_node(name)`` and prepends a fingerprint of
``{tier, backend_preference, timeout_s, model}`` to the key extras. A
config bump → different fingerprint → different cache key → cache miss →
re-execute. Fully native LangGraph (key change is the canonical
invalidation primitive); no SqliteCache subclass, no exception filtering.

These tests are storage-layer-agnostic: we assert on the key string only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from edit_episode_graph import config as config_module
from edit_episode_graph._caching import (
    make_key,
    make_llm_key,
    node_config_fingerprint,
)
from edit_episode_graph.config import RouterConfig, load_default_config


@pytest.fixture(autouse=True)
def _isolated_config(monkeypatch):
    """Replace the cached config with a writable in-memory one.

    `load_default_config` is `lru_cache`'d. Tests mutate the resolved
    config via ``RouterConfig.node_overrides`` and clear the lru_cache
    around each assertion so subsequent ``node_config_fingerprint`` calls
    re-resolve. Nothing touches the actual ``graph/config.yaml`` on disk.
    """
    base = RouterConfig(
        backend_preference=["claude"],
        concurrency={"claude": 1},
        defaults={"timeout_s": 120},
        node_overrides={
            "demo_node": {"tier": "smart", "timeout_s": 120, "backend_preference": ["claude"]},
        },
    )

    def _fake_load(*_a, **_kw):
        return base

    monkeypatch.setattr(config_module, "load_config", _fake_load)
    load_default_config.cache_clear()
    monkeypatch.setattr(config_module, "_REPO_CONFIG_PATH", Path("/__nonexistent__"), raising=False)
    # Patch `config_module.load_default_config` to a closure that returns our
    # in-memory `base`. `node_config_fingerprint` does
    # `from .config import load_default_config` at call time, which resolves
    # via `config`'s module namespace — so this single patch covers the
    # production code path. (We do NOT patch `_caching.load_default_config`
    # because `_caching` never reads it from its own namespace.)
    monkeypatch.setattr(
        config_module,
        "load_default_config",
        lambda: base,
    )

    yield base
    load_default_config.cache_clear()


def test_node_config_fingerprint_is_stable(_isolated_config):
    a = node_config_fingerprint("demo_node")
    b = node_config_fingerprint("demo_node")
    assert a == b


def test_node_config_fingerprint_changes_on_timeout_bump(_isolated_config):
    before = node_config_fingerprint("demo_node")
    _isolated_config.node_overrides["demo_node"]["timeout_s"] = 300
    after = node_config_fingerprint("demo_node")
    assert before != after, (
        "config bump must alter the fingerprint — otherwise HOM-157 returns: "
        "operator's timeout fix is silently ignored by the cache"
    )


def test_node_config_fingerprint_changes_on_model_override(_isolated_config):
    before = node_config_fingerprint("demo_node")
    _isolated_config.node_overrides["demo_node"]["model"] = "claude-haiku-4-5-20251001"
    after = node_config_fingerprint("demo_node")
    assert before != after


def test_node_config_fingerprint_changes_on_tier(_isolated_config):
    before = node_config_fingerprint("demo_node")
    _isolated_config.node_overrides["demo_node"]["tier"] = "cheap"
    after = node_config_fingerprint("demo_node")
    assert before != after


def test_node_config_fingerprint_changes_on_backend_preference(_isolated_config):
    before = node_config_fingerprint("demo_node")
    _isolated_config.node_overrides["demo_node"]["backend_preference"] = ["codex", "claude"]
    after = node_config_fingerprint("demo_node")
    assert before != after


def test_make_llm_key_invalidates_on_config_bump(_isolated_config):
    """End-to-end: same slug + same files + bumped timeout → different cache key."""
    args = dict(node="demo_node", version=1, slug="ep-2026-05-06", files=[], extras=())

    before = make_llm_key(**args)
    _isolated_config.node_overrides["demo_node"]["timeout_s"] = 300
    after = make_llm_key(**args)

    assert before != after


def test_make_llm_key_differs_from_make_key(_isolated_config):
    """Sanity: ``make_llm_key`` is not just an alias — it embeds the config
    fingerprint. A deterministic node using ``make_key`` with the same
    name+version+slug must NOT collide with an LLM node's key."""
    plain = make_key(node="demo_node", version=1, slug="ep-2026-05-06")
    llm = make_llm_key(node="demo_node", version=1, slug="ep-2026-05-06")
    assert plain != llm
    assert "cfg:" in llm and "cfg:" not in plain
