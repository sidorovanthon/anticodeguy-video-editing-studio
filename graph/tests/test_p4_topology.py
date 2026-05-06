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
        "p4_catalog_scan",
        "p4_captions_layer",
        "p4_dispatch_beats",
        "p4_beat",
        "p4_assemble_index",
        # HOM-127: post-assemble gate cluster (spec §4.3, §6.2)
        "gate_lint",
        "gate_validate",
        "gate_inspect",
        "gate_design_adherence",
        "gate_animation_map",
        "gate_snapshot",
        "gate_captions_track",
        "p4_persist_session",
        "studio_launch",
        "gate_static_guard",
        # HOM-146: Phase 3 → Phase 4 bridge interrupt
        "p3_review_interrupt",
        # HOM-148: cluster-gate retry node — re-authors offending scene
        "p4_redispatch_beat",
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
      gate_plan_ok → {p4_catalog_scan, halt_llm_boundary}
      p4_catalog_scan → p4_captions_layer (HOM-123)
      p4_captions_layer → {p4_dispatch_beats (beats), p4_assemble_index (skip)}
      p4_dispatch_beats → {p4_beat (Send fan-out), p4_assemble_index (skip)}
      p4_beat → p4_assemble_index (static fan-in)
      p4_assemble_index → halt_llm_boundary
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
        ("gate_plan_ok", "p4_catalog_scan"),
        # HOM-123: captions are authored once after catalog scan, before the
        # beat-vs-skip fan-out decision. Captions only depend on DESIGN.md +
        # transcript (both available pre-catalog), so authoring once outside
        # the per-beat fan-out keeps the smart-tier dispatch single-shot.
        ("p4_catalog_scan", "p4_captions_layer"),
        ("p4_captions_layer", "p4_dispatch_beats"),
        ("p4_captions_layer", "p4_assemble_index"),
        # HOM-134: dispatcher fans out to p4_beat (Send) for the happy path,
        # or skips straight to assemble (or END if plan empty).
        ("p4_dispatch_beats", "p4_beat"),
        ("p4_dispatch_beats", "p4_assemble_index"),
        # Static fan-in: LangGraph waits for all Send-spawned p4_beat branches
        # before firing this edge into p4_assemble_index.
        ("p4_beat", "p4_assemble_index"),
        ("p4_assemble_index", "halt_llm_boundary"),
        # HOM-127: post-assemble success leg now enters the gate cluster
        # at gate_lint. Skip-side (no scenes assembled) still routes
        # straight to halt.
        ("p4_assemble_index", "gate_lint"),
        # Gate-cluster pass edges (each fail edge → halt_llm_boundary).
        ("gate_lint", "gate_validate"),
        ("gate_lint", "halt_llm_boundary"),
        ("gate_validate", "gate_inspect"),
        ("gate_validate", "halt_llm_boundary"),
        ("gate_inspect", "gate_design_adherence"),
        ("gate_inspect", "halt_llm_boundary"),
        ("gate_design_adherence", "gate_animation_map"),
        ("gate_design_adherence", "halt_llm_boundary"),
        ("gate_animation_map", "gate_snapshot"),
        ("gate_animation_map", "halt_llm_boundary"),
        ("gate_snapshot", "gate_captions_track"),
        ("gate_snapshot", "halt_llm_boundary"),
        ("gate_captions_track", "p4_persist_session"),
        ("gate_captions_track", "halt_llm_boundary"),
        ("p4_persist_session", "studio_launch"),
        ("studio_launch", "gate_static_guard"),
        ("gate_static_guard", "halt_llm_boundary"),
        # HOM-130: failure interrupts are resumable. After resume, routing
        # either re-runs the originating gate (retry) or halts with a notice
        # (abort). Replaces the previous unconditional add_edge to END.
        ("edl_failure_interrupt", "gate_edl_ok"),
        ("edl_failure_interrupt", "halt_llm_boundary"),
        ("eval_failure_interrupt", "gate_eval_ok"),
        ("eval_failure_interrupt", "halt_llm_boundary"),
        # HOM-146: Phase 3 → Phase 4 bridge via interrupt() checkpoint.
        # Replaces `p3_persist_session → halt_llm_boundary` terminus.
        # Approve resume continues into Phase 4; abort routes to halt.
        ("p3_persist_session", "p3_review_interrupt"),
        ("p3_review_interrupt", "glue_remap_transcript"),
        ("p3_review_interrupt", "halt_llm_boundary"),
        # HOM-147: gate:edl_ok adopts the generic retry helper. The pass
        # and exhaustion edges are already covered above (→p3_render_segments
        # and →edl_failure_interrupt); the new retry edge loops back to
        # the producer so prior violations can be injected into the brief.
        ("gate_edl_ok", "p3_edl_select"),
        # HOM-148: post-assemble cluster gates adopt the same retry helper.
        # Each gate now has THREE outgoing edges: pass→next, retry→
        # p4_redispatch_beat (fail+iter<3), halt (fail+iter≥3). Pass and
        # halt edges are already asserted above; the new retry edges are:
        ("gate_lint", "p4_redispatch_beat"),
        ("gate_validate", "p4_redispatch_beat"),
        ("gate_inspect", "p4_redispatch_beat"),
        ("gate_design_adherence", "p4_redispatch_beat"),
        ("gate_animation_map", "p4_redispatch_beat"),
        ("gate_snapshot", "p4_redispatch_beat"),
        ("gate_captions_track", "p4_redispatch_beat"),
        # The redispatch node static-edges back to assemble — closing the loop.
        ("p4_redispatch_beat", "p4_assemble_index"),
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
