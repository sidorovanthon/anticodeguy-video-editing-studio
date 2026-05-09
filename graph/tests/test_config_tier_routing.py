"""HOM-193 — production config.yaml tier routing audit.

Creative LLM nodes must be flagship per memory rule
`feedback_creative_nodes_flagship_tier` and CLAUDE.md DoD-update note
(HOM-154 retro): Haiku-tier output on creative nodes triggered
`gate:lint` / `gate:design_adherence` redispatch loops costing more than
one successful Opus run.

Loads the production `graph/config.yaml`, resolves each node through
`RouterConfig.resolve_node`, and asserts the effective `(tier, model)`
falls in the right bucket — flagship-only for creative nodes, cheap-allowed
for mechanical structured-write nodes.

Single source of truth: tier→model mapping lives in
`graph.src.edit_episode_graph.backends.claude._MODEL_BY_TIER`. This test
imports it rather than hardcoding strings, so a future model bump
(`claude-opus-4-7` → `claude-opus-5`) doesn't silently invalidate the
guarantee.
"""
from __future__ import annotations

import pytest

from edit_episode_graph.backends.claude import _MODEL_BY_TIER
from edit_episode_graph.config import load_default_config


# Tiers whose model resolves to flagship Opus per the live mapping.
FLAGSHIP_TIERS = {"expensive"}
FLAGSHIP_MODELS = {_MODEL_BY_TIER[t] for t in FLAGSHIP_TIERS}

# Cheap/Sonnet tiers — acceptable for mechanical structured-write nodes.
CHEAP_TIERS = {"cheap", "smart"}
CHEAP_MODELS = {_MODEL_BY_TIER[t] for t in CHEAP_TIERS}


# Creative LLM nodes — palette/typography/expansion/plan/scene composition/
# tone-adaptive captions/strategy. All MUST resolve to flagship Opus.
# See memory `feedback_creative_nodes_flagship_tier` for the rationale.
CREATIVE_NODES = [
    "p3_strategy",
    "p4_design_system",
    "p4_prompt_expansion",
    "p4_plan",
    "p4_beat",
    "p4_redispatch_beat",
    "p4_captions_layer",
]

# Mechanical / structured-write nodes — cheap or smart is fine. These never
# produce brand-defining creative artifacts; their job is reformatting,
# session log appending, or pass/fail evaluation.
MECHANICAL_NODES = [
    "p3_pre_scan",
    "p3_self_eval",
    "p3_persist_session",
    "p4_persist_session",
]


def _resolved(node_name: str):
    """Resolve a node through the live production config.yaml."""
    load_default_config.cache_clear()
    try:
        return load_default_config().resolve_node(node_name)
    finally:
        load_default_config.cache_clear()


@pytest.mark.parametrize("node_name", CREATIVE_NODES)
def test_creative_nodes_resolve_to_flagship(node_name: str) -> None:
    """Each creative node must be tier=expensive AND no cheap model override."""
    cfg = _resolved(node_name)
    assert cfg.tier in FLAGSHIP_TIERS, (
        f"{node_name} resolved to tier={cfg.tier!r}; creative nodes must use "
        f"a flagship tier ({FLAGSHIP_TIERS}). See memory "
        f"`feedback_creative_nodes_flagship_tier` and HOM-154 retro."
    )
    # If a per-node `model` override is set, it must still be flagship —
    # otherwise tier=expensive is a lie. (Today no creative node sets model;
    # this guards against a future copy-paste from p3_pre_scan-style pins.)
    if cfg.model is not None:
        assert cfg.model in FLAGSHIP_MODELS, (
            f"{node_name} has model_override={cfg.model!r} which is not in the "
            f"flagship set {FLAGSHIP_MODELS}; creative nodes must NOT downgrade."
        )


@pytest.mark.parametrize("node_name", MECHANICAL_NODES)
def test_mechanical_nodes_may_be_cheap(node_name: str) -> None:
    """Mechanical nodes are allowed cheap/smart. The assertion here is symmetric:
    they MUST be in {cheap, smart} so a future "let's flagship-everything"
    refactor doesn't silently inflate spend. If a mechanical node legitimately
    needs flagship, move it into CREATIVE_NODES with rationale.
    """
    cfg = _resolved(node_name)
    assert cfg.tier in CHEAP_TIERS, (
        f"{node_name} resolved to tier={cfg.tier!r}; mechanical structured-write "
        f"nodes should stay in {CHEAP_TIERS}. If this node now does creative "
        f"work, move it to CREATIVE_NODES in this test."
    )
