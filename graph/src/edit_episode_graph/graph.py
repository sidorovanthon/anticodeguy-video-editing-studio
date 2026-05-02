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


def build_graph_uncompiled() -> StateGraph:
    """Assemble the v0 graph topology without compiling.

    Exposed so direct-invocation callers (smoke tests, ad-hoc scripts)
    can attach their own checkpointer at compile time:

        from langgraph.checkpoint.memory import InMemorySaver
        compiled = build_graph_uncompiled().compile(checkpointer=InMemorySaver())
    """
    g = StateGraph(GraphState)
    g.add_node("pickup", pickup_node)
    g.set_entry_point("pickup")
    g.add_conditional_edges("pickup", _route_after_pickup)
    return g


def build_graph():
    """Compile the v0 graph WITHOUT a checkpointer.

    Spec §9.6 originally bound a `SqliteSaver` here, but the langgraph-api
    runtime (used by `langgraph dev` and `langgraph up`) manages persistence
    itself and rejects user-supplied checkpointers with a hard ValueError.

    Switching the dev runtime to a real DB is configured via env vars
    (`POSTGRES_URI`) — out of scope for v0.
    """
    return build_graph_uncompiled().compile()


graph = build_graph()
