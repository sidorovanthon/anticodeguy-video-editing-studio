"""Graph assembly entry point.

`langgraph.json` points at the module-level `graph` object below. Re-importing this
module rebuilds it; `langgraph dev` does so on every code change.
"""

from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from .nodes.pickup import pickup_node
from .state import GraphState

_CHECKPOINT_DIR = Path(__file__).resolve().parent.parent.parent / ".langgraph_api"
_CHECKPOINT_PATH = _CHECKPOINT_DIR / "checkpoints.sqlite"


def _route_after_pickup(state) -> str:
    if state.get("errors"):
        return END
    if state.get("pickup", {}).get("idle"):
        return END
    # v0: pickup is the only node; v1 will replace this with "isolate_audio".
    return END


def build_graph():
    _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    g = StateGraph(GraphState)
    g.add_node("pickup", pickup_node)
    g.set_entry_point("pickup")
    g.add_conditional_edges("pickup", _route_after_pickup)
    return g.compile(
        checkpointer=SqliteSaver.from_conn_string(str(_CHECKPOINT_PATH)),
    )


graph = build_graph()
