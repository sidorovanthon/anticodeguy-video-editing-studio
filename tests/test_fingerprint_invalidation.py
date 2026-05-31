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
    assert_canon_change_invalidates,
    assert_fingerprint_changes_when,
    assert_model_change_invalidates,
    assert_upstream_artifact_change_invalidates,
)

CREATIVE_NODES = (
    "p3_strategy",
    "p4_design_system",
    "p4_beat",
    # HOM-235: state-first artifacts (Step B of HOM-230 epic). Same three
    # invariants apply (version bump, cfg fingerprint, upstream
    # artifact edit on the primary `design_md_path`).
    "p4_captions_layer",
    # HOM-156 (review S1): cheap-tier classifier extracted into its own
    # graph node so cache_policy= actually fires. Same three invariants
    # apply (version bump, cfg fingerprint, upstream artifact edit).
    "gate_animation_map_classify",
    # HOM-229: persist-session cache key made deterministic by deriving
    # `today` from `assembled_at[:10]` instead of `datetime.now()`.
    "p4_persist_session",
    # HOM-377: these three gained a `canon:<fp>` cache-key extra (verbatim
    # canon pulled into the brief). Registered + parametrised here so the
    # version/model/upstream invariants cover them (they had no fingerprint
    # coverage before); the canon extra itself is asserted by
    # `test_canon_change_invalidates` below.
    "p3_pre_scan",
    "p3_self_eval",
    "p3_edl_select",
)

# HOM-377: nodes whose `_cache_key` folds in `canon_fingerprint(node)`.
# p4_redispatch_beat is intentionally absent — it carries no CachePolicy
# (a retry node must re-run each iteration, never cache-hit).
CANON_CACHED_NODES = (
    "p3_pre_scan",
    "p3_strategy",
    "p3_edl_select",
    "p3_self_eval",
    "p4_beat",
    "p4_captions_layer",
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


@pytest.mark.parametrize("node_name", CANON_CACHED_NODES)
def test_canon_change_invalidates(node_name: str, tmp_path):
    """HOM-377: an upstream canon edit flips the key for every node that pulls
    verbatim canon into its brief. Guards against a future refactor silently
    dropping the `canon:<fp>` extra from a node's `_cache_key`.
    """
    assert_canon_change_invalidates(node_name, tmp_path=tmp_path)


# ---------------------------------------------------------------------------
# Secondary-artifact coverage — files= entries beyond the registry's primary.
# ---------------------------------------------------------------------------


def test_p4_beat_expanded_prompt_invalidates_fingerprint(tmp_path):
    """Mutating the in-state expanded-prompt body MUST flip p4_beat's key.

    The registry's primary mutator for ``p4_beat`` mutates
    ``compose.design.design_md`` (covered by the parametrised
    ``test_upstream_artifact_change_invalidates``), but ``_cache_key``
    fingerprints BOTH ``compose.design.design_md`` AND
    ``compose.expansion.expanded_prompt`` via ``extras=`` (post-HOM-240,
    Step E of HOM-230). This focused test exercises the secondary input
    directly. Pre-HOM-240 it edited the disk file at
    ``EpisodePaths(slug).expanded_prompt_path``; post-migration the
    cache key is body-fingerprint-based and the file is no longer on
    disk pre-materialize.
    """
    from tests._helpers.fingerprint_assertions import (
        _compute_key, _node_base_state,
    )

    state = _node_base_state("p4_beat", tmp_path)
    before = _compute_key("p4_beat", state)
    state.setdefault("compose", {}).setdefault("expansion", {})[
        "expanded_prompt"
    ] = "# expanded mutated\n"
    after = _compute_key("p4_beat", state)
    assert before != after, (
        "p4_beat: cache key did not change when "
        "compose.expansion.expanded_prompt body was edited"
    )


# ---------------------------------------------------------------------------
# Helper-itself unit tests — make sure the assert function actually fails
# when keys match, and passes when they differ.
# ---------------------------------------------------------------------------


def test_p4_scaffold_cache_version_bump_invalidates_key(tmp_path):
    """HOM-280: `p4_scaffold` is deterministic (make_key). The
    CREATIVE_NODES parametrisation exercises `make_llm_key`
    invariants (cfg fingerprint), which don't apply. Pin the version
    bump + slug invariants here as focused tests.
    """
    from tests._helpers.fingerprint_assertions import (
        assert_brief_change_invalidates,
    )

    assert_brief_change_invalidates("p4_scaffold", tmp_path=tmp_path)


def test_p4_scaffold_slug_change_invalidates_key(tmp_path):
    """HOM-280: `_cache_key` reads slug only (files=[]). The registry
    mutator flips the slug, which MUST flip the key."""
    from tests._helpers.fingerprint_assertions import (
        assert_upstream_artifact_change_invalidates,
    )

    assert_upstream_artifact_change_invalidates(
        "p4_scaffold", tmp_path=tmp_path
    )


def test_p3_inventory_cache_version_bump_invalidates_key(tmp_path):
    """HOM-285: `p3_inventory` is deterministic (make_key). Same
    exemption from CREATIVE_NODES as p4_scaffold / p4_assemble_index —
    focused test for the version bump and upstream file edge."""
    from tests._helpers.fingerprint_assertions import (
        assert_brief_change_invalidates,
    )

    assert_brief_change_invalidates("p3_inventory", tmp_path=tmp_path)


def test_p3_inventory_raw_video_edit_invalidates_key(tmp_path):
    """HOM-285: editing the upstream raw video (the canonical
    cache-key input via `pickup.raw_path`) MUST flip the cache key.
    Body hoist itself is an output-shape change captured by the
    version bump above; this asserts the load-bearing file edge."""
    from tests._helpers.fingerprint_assertions import (
        assert_upstream_artifact_change_invalidates,
    )

    assert_upstream_artifact_change_invalidates(
        "p3_inventory", tmp_path=tmp_path
    )


def test_p4_assemble_index_cache_version_bump_invalidates_key(tmp_path):
    """HOM-280: `p4_assemble_index` is deterministic (make_key). Same
    exemption from CREATIVE_NODES — focused test for the version bump."""
    from tests._helpers.fingerprint_assertions import (
        assert_brief_change_invalidates,
    )

    assert_brief_change_invalidates("p4_assemble_index", tmp_path=tmp_path)


def test_p4_assemble_index_scaffold_body_change_invalidates_key(tmp_path):
    """HOM-280: editing `compose.scaffold.index_html` MUST flip the
    cache key. The scaffold body is the HOM-280-specific input added
    to the existing scene/captions/design extras."""
    from tests._helpers.fingerprint_assertions import (
        assert_upstream_artifact_change_invalidates,
    )

    assert_upstream_artifact_change_invalidates(
        "p4_assemble_index", tmp_path=tmp_path
    )


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
