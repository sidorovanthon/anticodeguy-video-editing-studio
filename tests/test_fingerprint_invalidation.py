"""L0 fingerprint invalidation assertions (HOM-184 / spec §3).

Covers the three creative-node cache-key invariants:

1. **Brief / schema bump** (``_CACHE_VERSION``) — invalidates the node.
2. **Routing-config bump** (HOM-157 ``cfg:<sha>`` extra in
   ``make_llm_key``) — invalidates the node.
3. **Upstream artifact edit** (``files=`` content hash) — invalidates
   the node.

If any of these silently regresses (e.g. ``make_llm_key`` drops the cfg
extra, a node forgets to pass an artifact through ``files=``, the
version arg gets ignored), the L1 fixture-replay layer would stop
detecting brief-change regressions and cache hits would mask real
output changes. Catching it at L0 costs $0 and runs in milliseconds.
"""

from __future__ import annotations

import pytest

from tests._helpers.fingerprint_assertions import (
    assert_brief_change_invalidates,
    assert_fingerprint_changes_when,
    assert_model_change_invalidates,
    assert_upstream_artifact_change_invalidates,
)

CREATIVE_NODES = (
    "p3_strategy",
    "p4_design_system",
    "p4_beat",
    # HOM-156 (review S1): cheap-tier classifier extracted into its own
    # graph node so cache_policy= actually fires. Same three invariants
    # apply (version bump, cfg fingerprint, upstream artifact edit).
    "gate_animation_map_classify",
    # HOM-229: persist-session cache key made deterministic by deriving
    # `today` from `assembled_at[:10]` instead of `datetime.now()`.
    "p4_persist_session",
)


# ---------------------------------------------------------------------------
# Convenience-helper coverage — one parametrised test per invariant per node.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("node_name", CREATIVE_NODES)
def test_brief_change_invalidates(node_name: str, tmp_path):
    """Bumping ``_CACHE_VERSION`` flips the cache key for every creative node."""
    assert_brief_change_invalidates(node_name, tmp_path=tmp_path)


@pytest.mark.parametrize("node_name", CREATIVE_NODES)
def test_model_change_invalidates(node_name: str, tmp_path):
    """Bumping ``graph/config.yaml`` (tier/model/timeout) flips the key.

    Exercises HOM-157 ``cfg:<sha>`` extra prepended by ``make_llm_key``.
    """
    assert_model_change_invalidates(node_name, tmp_path=tmp_path)


@pytest.mark.parametrize("node_name", CREATIVE_NODES)
def test_upstream_artifact_change_invalidates(node_name: str, tmp_path):
    """Editing the upstream file the brief consumes flips the key.

    Default artifact per node is registered in
    :mod:`tests._helpers.fingerprint_assertions`.
    """
    assert_upstream_artifact_change_invalidates(node_name, tmp_path=tmp_path)


# ---------------------------------------------------------------------------
# Secondary-artifact coverage — files= entries beyond the registry's primary.
# ---------------------------------------------------------------------------


def test_p4_beat_expanded_prompt_invalidates_fingerprint(tmp_path):
    """Editing ``expanded-prompt.md`` MUST flip p4_beat's cache key.

    The registry's ``primary_artifact_pointer`` for ``p4_beat`` points at
    ``design.md`` (covered by the parametrised
    ``test_upstream_artifact_change_invalidates``), but ``_cache_key``
    hashes BOTH ``design_md_path`` AND ``expanded_prompt_path`` via
    ``files=`` (see ``nodes/p4_beat.py::_cache_key`` lines 96-105). This
    focused test exercises the secondary input directly rather than
    extending the registry schema (HOM-234 PR #140 review S2).
    """
    assert_upstream_artifact_change_invalidates(
        "p4_beat",
        tmp_path=tmp_path,
        artifact_path=tmp_path / "episodes" / "fp-fixture" / "hyperframes"
        / ".hyperframes" / "expanded-prompt.md",
    )


# ---------------------------------------------------------------------------
# Helper-itself unit tests — make sure the assert function actually fails
# when keys match, and passes when they differ.
# ---------------------------------------------------------------------------


def test_helper_raises_when_keys_match(tmp_path):
    """A no-op mutation must trigger AssertionError — proves the helper checks."""
    from tests._helpers.fingerprint_assertions import _node_base_state

    state = _node_base_state("p3_strategy", tmp_path)
    with pytest.raises(AssertionError, match="cache key did not change"):
        assert_fingerprint_changes_when("p3_strategy", state, lambda s: None)


def test_helper_passes_when_state_mutates(tmp_path):
    """A real mutation (slug rename) flips the key for every node."""
    from tests._helpers.fingerprint_assertions import _node_base_state

    state = _node_base_state("p4_design_system", tmp_path)
    before, after = assert_fingerprint_changes_when(
        "p4_design_system",
        state,
        lambda s: s.update(slug="fp-fixture-v2"),
    )
    assert before != after
    assert "fp-fixture-v2" in after  # slug is rendered into make_llm_key directly


def test_helper_rejects_unknown_node(tmp_path):
    """Bad node name surfaces a clear KeyError, not an obscure ImportError."""
    from tests._helpers.fingerprint_assertions import _load_node_module

    with pytest.raises(KeyError, match="unknown node"):
        _load_node_module("p99_does_not_exist")
