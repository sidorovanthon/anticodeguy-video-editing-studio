"""Graph assembly entry point.

`langgraph.json` points at the module-level `graph` object below. Re-importing this
module rebuilds it; `langgraph dev` does so on every code change.
"""

from langgraph.graph import END, StateGraph

from .nodes.pickup import pickup_node
from .state import GraphState


def _route_after_pickup(state) -> str:
    if state.get("errors"):
        return END
    if state.get("pickup", {}).get("idle"):
        return END
    # v0: pickup is the only node; v1 will replace this with "isolate_audio".
    return END


def build_graph():
    """Compile the v0 graph WITHOUT a checkpointer.

    Spec §9.6 originally bound a `SqliteSaver` here, but the langgraph-api
    runtime (used by `langgraph dev` and `langgraph up`) manages persistence
    itself and rejects user-supplied checkpointers with a hard ValueError.

    Direct invocation contexts (smoke tests, ad-hoc `graph.invoke()`) that
    need persistence should pass a checkpointer at compile time:

        from langgraph.checkpoint.memory import InMemorySaver
        g = build_graph_uncompiled()
        compiled = g.compile(checkpointer=InMemorySaver())

    Switching the dev runtime to a real DB is configured via env vars
    (`POSTGRES_URI`) — out of scope for v0.
    """
    g = StateGraph(GraphState)
    g.add_node("pickup", pickup_node)
    g.set_entry_point("pickup")
    g.add_conditional_edges("pickup", _route_after_pickup)
    return g.compile()


graph = build_graph()
