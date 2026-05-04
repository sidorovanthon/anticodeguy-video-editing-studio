"""Topology assertions for the Phase 4 LLM chain.

Compiles the graph and inspects its node-set + edge-set. Catches the
"node added but not wired" regression that earlier P4 PRs (HOM-118,
HOM-119) hit by deferring wiring to HOM-127. Per CLAUDE.md the wire-up
is now part of every LLM-node ticket's DoD; this test is the cheap
deterministic gate that enforces it.

The test inspects the LangGraph runtime's `get_graph()` output, which
the LangGraph Studio renderer uses for its static graph view — so a
green test here also implies Studio shows the node correctly.
"""

from __future__ import annotations

from edit_episode_graph.graph import build_graph_uncompiled


def _compiled_graph_repr():
    return build_graph_uncompiled().compile().get_graph()


def test_phase4_nodes_present_in_compiled_graph():
    nodes = set(_compiled_graph_repr().nodes.keys())
    expected = {
        "p4_scaffold",
        "p4_design_system",
        "gate_design_ok",
        "p4_prompt_expansion",
        "p4_plan",
        "gate_plan_ok",
    }
    missing = expected - nodes
    assert not missing, f"Phase 4 nodes missing from compiled graph: {sorted(missing)}"


def test_phase4_chain_edges_wired():
    """The expected end-to-end Phase 4 LLM chain must be reachable.

    Edges asserted (matches v4 topology in graph.py):
      glue_remap_transcript → p4_scaffold (skip_phase4 conditional, on the
        no-index.html branch)
      p4_scaffold → p4_design_system
      p4_design_system → gate_design_ok
      gate_design_ok → p4_prompt_expansion
      p4_prompt_expansion → p4_plan
      p4_plan → gate_plan_ok
      gate_plan_ok → halt_llm_boundary
    """
    graph = _compiled_graph_repr()
    edges = {(e.source, e.target) for e in graph.edges}
    expected_edges = {
        ("glue_remap_transcript", "p4_scaffold"),
        ("p4_scaffold", "p4_design_system"),
        ("p4_design_system", "gate_design_ok"),
        ("gate_design_ok", "p4_prompt_expansion"),
        ("p4_prompt_expansion", "p4_plan"),
        ("p4_plan", "gate_plan_ok"),
        ("gate_plan_ok", "halt_llm_boundary"),
    }
    missing = expected_edges - edges
    assert not missing, (
        f"Phase 4 wire-up edges missing in compiled graph: {sorted(missing)}\n"
        f"Present edges from p4_*: {sorted(e for e in edges if 'p4_' in e[0] or 'p4_' in e[1])}"
    )


def test_design_ok_gate_failure_routes_to_halt():
    """gate:design_ok fail-path must terminate on halt_llm_boundary, not END,
    so the boundary's notice surfaces in Studio (v4-sans-HITL spec)."""
    edges = {(e.source, e.target) for e in _compiled_graph_repr().edges}
    assert ("gate_design_ok", "halt_llm_boundary") in edges, (
        "gate_design_ok must route to halt_llm_boundary on fail "
        "(v4-sans-HITL — retry-with-violations is HOM-77)"
    )
