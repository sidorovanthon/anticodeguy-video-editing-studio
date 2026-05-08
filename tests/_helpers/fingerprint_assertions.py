"""Fingerprint invalidation assertion helpers (HOM-184 / spec §3 L0).

Each creative LLM node carries a ``_cache_key(state)`` function that
feeds ``langgraph.types.CachePolicy``. The HOM-157 mechanism guarantees
that ``cache_key`` changes when:

* ``_CACHE_VERSION`` is bumped (brief / schema / tool-list change).
* ``graph/config.yaml`` for the node changes (tier / model / timeout /
  backend_preference) — covered by ``make_llm_key`` auto-prepending a
  ``cfg:<sha>`` extra.
* An upstream artifact in ``files=`` changes content (sha256-hashed via
  :func:`edit_episode_graph._caching.file_fingerprint`).

This module asserts those invariants per-node so a future refactor that
silently drops one of those inputs surfaces immediately, without paid
LLM dispatches. Spec §3 «Fingerprint invalidation assertion».

Usage:

    from tests._helpers.fingerprint_assertions import (
        assert_brief_change_invalidates,
        assert_model_change_invalidates,
        assert_upstream_artifact_change_invalidates,
    )

    def test_p3_strategy_brief_invalidates():
        assert_brief_change_invalidates("p3_strategy")

The convenience helpers package a sensible base state per known node;
the lower-level :func:`assert_fingerprint_changes_when` is exposed for
custom mutations that aren't covered by the canned set.
"""

from __future__ import annotations

import hashlib
import importlib
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

# ---------------------------------------------------------------------------
# Per-node base-state factories.
#
# Each factory returns a dict that the node's ``_cache_key`` accepts
# (matches the shape it pulls from ``state`` — ``slug``, ``episode_dir``,
# the relevant ``edit``/``compose``/``transcripts`` blobs).
#
# State values are deliberately minimal: just enough for ``_cache_key``
# to pick up every input it fingerprints. The bodies (LLM dispatch,
# validators) are NOT exercised here — this is a key-only L0 check.
# ---------------------------------------------------------------------------


def _p3_strategy_base(tmp_dir: Path) -> dict:
    takes = tmp_dir / "edit" / "takes_packed.md"
    takes.parent.mkdir(parents=True, exist_ok=True)
    takes.write_text("snapshot fixture takes\n", encoding="utf-8")
    return {
        "slug": "fp-fixture",
        "episode_dir": str(tmp_dir),
        "transcripts": {"takes_packed_path": str(takes)},
        "edit": {
            "pre_scan": {"slips": []},
            "strategy": {},
        },
        "strategy_revisions": [],
    }


def _p4_design_system_base(tmp_dir: Path) -> dict:
    transcript = tmp_dir / "edit" / "transcripts" / "raw.json"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text('{"segments":[]}', encoding="utf-8")
    edl = tmp_dir / "edit" / "edl.json"
    edl.write_text('{"ranges":[]}', encoding="utf-8")
    return {
        "slug": "fp-fixture",
        "episode_dir": str(tmp_dir),
        "transcripts": {"final_json_path": str(transcript)},
        "edit": {
            "edl": {"edl_path": str(edl), "ranges": []},
            "strategy": {"shape": "hpp", "takes": ["t1"]},
        },
    }


def _p4_beat_base(tmp_dir: Path) -> dict:
    design_md = tmp_dir / "hyperframes" / "DESIGN.md"
    design_md.parent.mkdir(parents=True, exist_ok=True)
    design_md.write_text("# DESIGN.md fixture\n", encoding="utf-8")
    expanded = tmp_dir / "hyperframes" / ".hyperframes" / "expanded-prompt.md"
    expanded.parent.mkdir(parents=True, exist_ok=True)
    expanded.write_text("# expanded\n", encoding="utf-8")
    return {
        "slug": "fp-fixture",
        "episode_dir": str(tmp_dir),
        "compose": {
            "design_md_path": str(design_md),
            "expanded_prompt_path": str(expanded),
        },
        "_beat_dispatch": {
            "scene_id": "scene-hook",
            "plan_beat": {"beat": "HOOK", "concept": "fixture", "duration_s": 5.0},
        },
    }


# Map node_name → (module_path, base_state_factory, primary_artifact_pointer).
#
# ``primary_artifact_pointer`` is a callable ``(state) -> Path`` returning
# the upstream file the node's ``_cache_key`` content-hashes via
# ``files=`` — used by :func:`assert_upstream_artifact_change_invalidates`.
_NODE_REGISTRY: dict[str, tuple[str, Callable[[Path], dict], Callable[[dict], Path]]] = {
    "p3_strategy": (
        "edit_episode_graph.nodes.p3_strategy",
        _p3_strategy_base,
        lambda s: Path(s["transcripts"]["takes_packed_path"]),
    ),
    "p4_design_system": (
        "edit_episode_graph.nodes.p4_design_system",
        _p4_design_system_base,
        lambda s: Path(s["transcripts"]["final_json_path"]),
    ),
    "p4_beat": (
        "edit_episode_graph.nodes.p4_beat",
        _p4_beat_base,
        lambda s: Path(s["compose"]["design_md_path"]),
    ),
}


def _load_node_module(node_name: str):
    if node_name not in _NODE_REGISTRY:
        raise KeyError(
            f"unknown node {node_name!r}; supported: {sorted(_NODE_REGISTRY)}"
        )
    return importlib.import_module(_NODE_REGISTRY[node_name][0])


def _node_base_state(node_name: str, tmp_dir: Path) -> dict:
    return _NODE_REGISTRY[node_name][1](tmp_dir)


def _primary_artifact_path(node_name: str, state: dict) -> Path:
    return _NODE_REGISTRY[node_name][2](state)


def _compute_key(node_name: str, state: dict) -> str:
    """Invoke the node's ``_cache_key(state)`` — the production call shape."""
    mod = _load_node_module(node_name)
    return mod._cache_key(state)


# ---------------------------------------------------------------------------
# Core assertion + convenience wrappers.
# ---------------------------------------------------------------------------


def assert_fingerprint_changes_when(
    node_name: str,
    base_state: dict,
    mutation_fn: Callable[[dict], None],
) -> tuple[str, str]:
    """Assert ``_cache_key`` differs after ``mutation_fn`` mutates ``state``.

    ``mutation_fn`` receives the (single, shared) state dict and mutates
    it in place. Both calls go through the node module's real
    ``_cache_key`` so any drift in cache-key plumbing is caught.

    Returns the ``(before, after)`` keys for downstream assertions if the
    caller wants to inspect them.
    """
    before = _compute_key(node_name, base_state)
    mutation_fn(base_state)
    after = _compute_key(node_name, base_state)
    assert before != after, (
        f"{node_name}: cache key did not change after mutation\n"
        f"  before={before}\n"
        f"  after ={after}\n"
        f"  state ={base_state!r}"
    )
    return before, after


def assert_brief_change_invalidates(node_name: str, *, tmp_path: Path) -> None:
    """Bumping the node's ``_CACHE_VERSION`` MUST change the cache key.

    Modeled by monkey-bumping the module's ``_CACHE_VERSION`` constant
    around a key-recompute. Restores on exit so other tests in the same
    session see the original value.
    """
    mod = _load_node_module(node_name)
    state = _node_base_state(node_name, tmp_path)
    original = mod._CACHE_VERSION
    try:
        before = _compute_key(node_name, state)
        mod._CACHE_VERSION = original + 1
        after = _compute_key(node_name, state)
    finally:
        mod._CACHE_VERSION = original
    assert before != after, (
        f"{node_name}: cache key did not change when _CACHE_VERSION bumped "
        f"from {original} to {original + 1} — make_llm_key/make_key may not "
        f"be honoring the version arg"
    )


@contextmanager
def _patched_node_config_fingerprint(target_node: str, override: str) -> Iterator[None]:
    """Force :func:`_caching.node_config_fingerprint` to a stable override.

    Only intercepts calls for ``target_node`` so other LLM nodes evaluated
    transitively (none in our helpers, but defensive) keep their real
    fingerprint.
    """
    from edit_episode_graph import _caching

    original = _caching.node_config_fingerprint

    def _patched(name: str) -> str:
        if name == target_node:
            return override
        return original(name)

    _caching.node_config_fingerprint = _patched
    try:
        yield
    finally:
        _caching.node_config_fingerprint = original


def assert_model_change_invalidates(node_name: str, *, tmp_path: Path) -> None:
    """Changing routing-config (tier/model/timeout) MUST change the key.

    HOM-157 mechanism (3): ``make_llm_key`` prepends ``cfg:<sha>`` from
    :func:`node_config_fingerprint`. We monkeypatch that single function
    to return two different sentinel values around two key-recomputes —
    if the prepend isn't actually wired, the keys would match.
    """
    state = _node_base_state(node_name, tmp_path)
    with _patched_node_config_fingerprint(node_name, "cfg-fp-A"):
        before = _compute_key(node_name, state)
    with _patched_node_config_fingerprint(node_name, "cfg-fp-B"):
        after = _compute_key(node_name, state)
    assert before != after, (
        f"{node_name}: cache key did not change when node_config_fingerprint "
        f"flipped (A→B) — make_llm_key may have dropped the cfg extra "
        f"(HOM-157 regression)"
    )


def assert_upstream_artifact_change_invalidates(
    node_name: str,
    *,
    tmp_path: Path,
    artifact_path: Path | None = None,
) -> None:
    """Editing a file in ``files=`` MUST change the key.

    Default: uses the per-node ``primary_artifact_pointer`` from the
    registry. Pass ``artifact_path`` to override (e.g. when checking a
    secondary artifact in the node's ``files=`` list).
    """
    state = _node_base_state(node_name, tmp_path)
    target = artifact_path if artifact_path is not None else _primary_artifact_path(node_name, state)
    target = Path(target)
    if not target.exists():
        raise FileNotFoundError(
            f"{node_name}: primary artifact {target} not seeded by base-state factory"
        )

    before = _compute_key(node_name, state)
    # Append distinct content so sha256 differs deterministically.
    target.write_bytes(target.read_bytes() + b"\n# fp-mutated\n")
    after = _compute_key(node_name, state)
    assert before != after, (
        f"{node_name}: cache key did not change when {target} content was edited "
        f"— files= list may not include this artifact (or file_fingerprint "
        f"is no longer content-hashing)"
    )


__all__ = [
    "assert_fingerprint_changes_when",
    "assert_brief_change_invalidates",
    "assert_model_change_invalidates",
    "assert_upstream_artifact_change_invalidates",
]
