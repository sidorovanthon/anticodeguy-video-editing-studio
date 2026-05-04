"""Graph assembly entry point.

`langgraph.json` points at the module-level `graph` object below. Re-importing
this module rebuilds it; `langgraph dev` does so on every code change.

v1 topology (spec §4.1, §8 — LLM-free coverage):

    pickup ─┬─ idle/error ──────────────────────────────────► END
            │
            └─ skip_phase2? ┬─ tagged ───────────────────────┐
                            │                                ▼
                            └─ untagged ─► isolate_audio ─► preflight_canon
                                                                ▼
                            skip_phase3? ┬─ final.mp4 ─► glue_remap_transcript
                                          │                     ▼
                                          │   skip_phase4? ┬─ idx.html ─► END
                                          │                 ▼
                                          │              p4_scaffold ─► END (notice)
                                          │
                                          ├─ takes_packed.md ─► p3_pre_scan ─► p3_strategy ─► p3_edl_select ─► gate_edl_ok ┬─ pass ─► p3_render_segments ─► p3_self_eval ─► gate_eval_ok ┬─ pass ─► p3_persist_session ─► halt_llm_boundary ─► END
                                          │                                                                                   │                                                              ├─ fail+iter<3 ─► p3_render_segments
                                          │                                                                                   │                                                              └─ fail+iter≥3 ─► eval_failure_interrupt (HITL) ─► END
                                          │                                                                                   └─ fail ─► edl_failure_interrupt (HITL suspend) ─► END
                                          └─ no inventory ─► p3_inventory ┬─ error ─► END
                                                                          └─ ok ─► p3_pre_scan ─► p3_strategy ─► p3_edl_select ─► gate_edl_ok ─► …
"""

from langgraph.graph import END, StateGraph

from .gates.design_ok import design_ok_gate_node
from .gates.edl_ok import edl_ok_gate_node
from .gates.eval_ok import eval_ok_gate_node
from .nodes._routing import (
    route_after_design_ok,
    route_after_design_system,
    route_after_edl_ok,
    route_after_edl_select,
    route_after_eval_ok,
    route_after_inventory,
    route_after_persist_session,
    route_after_pickup,
    route_after_preflight,
    route_after_pre_scan,
    route_after_prompt_expansion,
    route_after_remap,
    route_after_render_segments,
    route_after_scaffold,
    route_after_self_eval,
    route_after_strategy,
    route_after_strategy_confirmed,
)
from .nodes.edl_failure_interrupt import edl_failure_interrupt_node
from .nodes.eval_failure_interrupt import eval_failure_interrupt_node
from .nodes.glue_remap_transcript import glue_remap_transcript_node
from .nodes.halt_llm_boundary import halt_llm_boundary_node
from .nodes.isolate_audio import isolate_audio_node
from .nodes.p3_edl_select import p3_edl_select_node
from .nodes.p3_inventory import p3_inventory_node
from .nodes.p3_pre_scan import p3_pre_scan_node
from .nodes.p3_render_segments import p3_render_segments_node
from .nodes.p3_persist_session import p3_persist_session_node
from .nodes.p3_self_eval import p3_self_eval_node
from .nodes.p3_strategy import p3_strategy_node
from .nodes.p4_design_system import p4_design_system_node
from .nodes.p4_prompt_expansion import p4_prompt_expansion_node
from .nodes.p4_scaffold import p4_scaffold_node
from .nodes.pickup import pickup_node
from .nodes.preflight_canon import preflight_canon_node
from .nodes.strategy_confirmed_interrupt import strategy_confirmed_interrupt_node
from .state import GraphState


def build_graph_uncompiled() -> StateGraph:
    """Assemble the v1 graph topology without compiling.

    Exposed so direct-invocation callers (smoke tests, ad-hoc scripts) can
    attach their own checkpointer at compile time:

        from langgraph.checkpoint.memory import InMemorySaver
        compiled = build_graph_uncompiled().compile(checkpointer=InMemorySaver())
    """
    g = StateGraph(GraphState)

    g.add_node("pickup", pickup_node)
    g.add_node("isolate_audio", isolate_audio_node)
    g.add_node("preflight_canon", preflight_canon_node)
    g.add_node("glue_remap_transcript", glue_remap_transcript_node)
    g.add_node("p4_scaffold", p4_scaffold_node)
    g.add_node("p4_design_system", p4_design_system_node)
    g.add_node("gate_design_ok", design_ok_gate_node)
    g.add_node("p4_prompt_expansion", p4_prompt_expansion_node)
    g.add_node("p3_inventory", p3_inventory_node)
    g.add_node("p3_pre_scan", p3_pre_scan_node)
    g.add_node("p3_strategy", p3_strategy_node)
    g.add_node("strategy_confirmed_interrupt", strategy_confirmed_interrupt_node)
    g.add_node("p3_edl_select", p3_edl_select_node)
    g.add_node("gate_edl_ok", edl_ok_gate_node)
    g.add_node("p3_render_segments", p3_render_segments_node)
    g.add_node("p3_self_eval", p3_self_eval_node)
    g.add_node("gate_eval_ok", eval_ok_gate_node)
    g.add_node("p3_persist_session", p3_persist_session_node)
    g.add_node("edl_failure_interrupt", edl_failure_interrupt_node)
    g.add_node("eval_failure_interrupt", eval_failure_interrupt_node)
    g.add_node("halt_llm_boundary", halt_llm_boundary_node)

    g.set_entry_point("pickup")

    # The explicit path mappings below are not strictly required by LangGraph
    # (it can infer destinations from the function's possible return values),
    # but listing them keeps Studio's static graph rendering honest about
    # which conditional edges exist — without it, skip-edges only appear
    # after a run actually traverses them.

    # skip_phase2? lives inside route_after_pickup.
    g.add_conditional_edges(
        "pickup",
        route_after_pickup,
        {
            END: END,
            "isolate_audio": "isolate_audio",
            "preflight_canon": "preflight_canon",
        },
    )
    g.add_edge("isolate_audio", "preflight_canon")

    # skip_phase3? lives inside route_after_preflight.
    g.add_conditional_edges(
        "preflight_canon",
        route_after_preflight,
        {
            END: END,
            "glue_remap_transcript": "glue_remap_transcript",
            "p3_inventory": "p3_inventory",
            "p3_pre_scan": "p3_pre_scan",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    g.add_conditional_edges(
        "p3_inventory",
        route_after_inventory,
        {
            END: END,
            "p3_pre_scan": "p3_pre_scan",
        },
    )
    g.add_conditional_edges(
        "p3_pre_scan",
        route_after_pre_scan,
        {
            END: END,
            "p3_strategy": "p3_strategy",
        },
    )
    g.add_conditional_edges(
        "p3_strategy",
        route_after_strategy,
        {
            END: END,
            "strategy_confirmed_interrupt": "strategy_confirmed_interrupt",
        },
    )
    g.add_conditional_edges(
        "strategy_confirmed_interrupt",
        route_after_strategy_confirmed,
        {
            END: END,
            "p3_edl_select": "p3_edl_select",
            "p3_strategy": "p3_strategy",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    g.add_conditional_edges(
        "p3_edl_select",
        route_after_edl_select,
        {
            END: END,
            "gate_edl_ok": "gate_edl_ok",
        },
    )
    g.add_conditional_edges(
        "gate_edl_ok",
        route_after_edl_ok,
        {
            "p3_render_segments": "p3_render_segments",
            "edl_failure_interrupt": "edl_failure_interrupt",
        },
    )
    g.add_conditional_edges(
        "p3_render_segments",
        route_after_render_segments,
        {
            END: END,
            "halt_llm_boundary": "halt_llm_boundary",
            "p3_self_eval": "p3_self_eval",
        },
    )
    g.add_conditional_edges(
        "p3_self_eval",
        route_after_self_eval,
        {
            END: END,
            "halt_llm_boundary": "halt_llm_boundary",
            "gate_eval_ok": "gate_eval_ok",
        },
    )
    g.add_conditional_edges(
        "gate_eval_ok",
        route_after_eval_ok,
        {
            "p3_persist_session": "p3_persist_session",
            "p3_render_segments": "p3_render_segments",
            "eval_failure_interrupt": "eval_failure_interrupt",
        },
    )
    g.add_conditional_edges(
        "p3_persist_session",
        route_after_persist_session,
        {
            END: END,
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    g.add_edge("edl_failure_interrupt", END)
    g.add_edge("eval_failure_interrupt", END)

    # skip_phase4? lives inside route_after_remap.
    g.add_conditional_edges(
        "glue_remap_transcript",
        route_after_remap,
        {
            END: END,
            "p4_scaffold": "p4_scaffold",
        },
    )
    # Phase 4 LLM chain. New P4 LLM-node tickets MUST extend this chain in
    # their own PR (per CLAUDE.md "Topology wiring is part of node DoD") —
    # do NOT defer wiring to HOM-127. The compiled-graph topology smoke
    # (smoke_hom107.py Case 1 + tests/test_p4_topology.py) catches "node
    # added but edges not wired" regressions for free.
    g.add_conditional_edges(
        "p4_scaffold",
        route_after_scaffold,
        {
            END: END,
            "p4_design_system": "p4_design_system",
        },
    )
    g.add_conditional_edges(
        "p4_design_system",
        route_after_design_system,
        {
            END: END,
            "gate_design_ok": "gate_design_ok",
        },
    )
    g.add_conditional_edges(
        "gate_design_ok",
        route_after_design_ok,
        {
            "p4_prompt_expansion": "p4_prompt_expansion",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    g.add_conditional_edges(
        "p4_prompt_expansion",
        route_after_prompt_expansion,
        {
            END: END,
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    g.add_edge("halt_llm_boundary", END)

    return g


def build_graph():
    """Compile the graph WITHOUT a checkpointer.

    Spec §9.6 originally bound a `SqliteSaver` here, but the langgraph-api
    runtime (used by `langgraph dev` and `langgraph up`) manages persistence
    itself and rejects user-supplied checkpointers with a hard ValueError.

    Switching the dev runtime to a real DB is configured via env vars
    (`POSTGRES_URI`) — out of scope for v1.
    """
    return build_graph_uncompiled().compile()


graph = build_graph()
