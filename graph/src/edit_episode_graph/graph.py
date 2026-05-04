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
                                          ├─ takes_packed.md ─► p3_pre_scan ─► p3_strategy ─► p3_edl_select ─► gate:edl_ok ┬─ pass ─► halt_llm_boundary ─► END
                                          │                                                                                   └─ fail ─► END (notice)
                                          └─ no inventory ─► p3_inventory ┬─ error ─► END
                                                                          └─ ok ─► p3_pre_scan ─► p3_strategy ─► p3_edl_select ─► gate:edl_ok ─► …
"""

from langgraph.graph import END, StateGraph

from .gates.edl_ok import edl_ok_gate_node
from .nodes._routing import (
    route_after_edl_ok,
    route_after_edl_select,
    route_after_inventory,
    route_after_pickup,
    route_after_preflight,
    route_after_pre_scan,
    route_after_remap,
    route_after_strategy,
)
from .nodes.glue_remap_transcript import glue_remap_transcript_node
from .nodes.halt_llm_boundary import halt_llm_boundary_node
from .nodes.isolate_audio import isolate_audio_node
from .nodes.p3_edl_select import p3_edl_select_node
from .nodes.p3_inventory import p3_inventory_node
from .nodes.p3_pre_scan import p3_pre_scan_node
from .nodes.p3_strategy import p3_strategy_node
from .nodes.p4_scaffold import p4_scaffold_node
from .nodes.pickup import pickup_node
from .nodes.preflight_canon import preflight_canon_node
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
    g.add_node("p3_inventory", p3_inventory_node)
    g.add_node("p3_pre_scan", p3_pre_scan_node)
    g.add_node("p3_strategy", p3_strategy_node)
    g.add_node("p3_edl_select", p3_edl_select_node)
    g.add_node("gate_edl_ok", edl_ok_gate_node)
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
            "p3_edl_select": "p3_edl_select",
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
            END: END,
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )

    # skip_phase4? lives inside route_after_remap.
    g.add_conditional_edges(
        "glue_remap_transcript",
        route_after_remap,
        {
            END: END,
            "p4_scaffold": "p4_scaffold",
        },
    )
    g.add_edge("p4_scaffold", END)
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
