"""Empirical pin: parallel-Send fan-out into the top-level ``scenes`` channel
deterministically merges via the ``_scenes_merge`` reducer.

HOM-234 pre-check (2026-05-15) proved LangGraph reducers do NOT walk
nested ``Annotated`` channels: with ``scenes`` nested inside ``compose``
(``compose: Annotated[..., dict_merge]`` /
``scenes: Annotated[..., _scenes_merge]``), two parallel ``Send`` writers
each emitting ``{"compose": {"scenes": {<scene_id>: ...}}}`` produced a
final state where only the last Send's scene survived — the outer
``dict_merge`` ran shallow ``{**left, **right}`` over whole ``scenes``
dicts and last-write-wins clobbered the first Send.

Fix: ``scenes`` was promoted to a TOP-LEVEL channel on ``GraphState``
(state.py around line 472). This test pins the fixed behaviour as
regression coverage — every future state-first beat-style node depends
on this contract holding.

Spec amendment: ``docs/superpowers/specs/2026-05-10-state-first-artifacts.md``
§10 Step B.
"""

from __future__ import annotations

from langgraph.graph import START, END, StateGraph
from langgraph.types import Send

from edit_episode_graph.state import GraphState


def _writer(state: dict) -> dict:
    """Inline node: emit a scenes-dict update keyed on injected ``_beat_dispatch``."""
    bd = state.get("_beat_dispatch") or {}
    scene_id = bd["scene_id"]
    body = bd["html"]
    return {"scenes": {scene_id: {"html": body}}}


def _dispatch(state: dict) -> list[Send]:
    return [
        Send("writer", {**state, "_beat_dispatch": {"scene_id": "hook", "html": "<div>HOOK</div>"}}),
        Send("writer", {**state, "_beat_dispatch": {"scene_id": "thesis", "html": "<div>THESIS</div>"}}),
    ]


def _entry(state: dict) -> dict:
    return {}


def test_parallel_send_into_compose_scenes_preserves_both():
    g = StateGraph(GraphState)
    g.add_node("entry", _entry)
    g.add_node("writer", _writer)
    g.add_edge(START, "entry")
    g.add_conditional_edges("entry", _dispatch, ["writer"])
    g.add_edge("writer", END)
    compiled = g.compile()

    final = compiled.invoke({"slug": "test-fanout"})
    scenes = final.get("scenes") or {}

    assert "hook" in scenes, f"hook scene missing — got {sorted(scenes.keys())}"
    assert "thesis" in scenes, f"thesis scene missing — got {sorted(scenes.keys())}"
    assert scenes["hook"]["html"] == "<div>HOOK</div>"
    assert scenes["thesis"]["html"] == "<div>THESIS</div>"
    # _scenes_merge sorts keys deterministically.
    assert list(scenes.keys()) == sorted(scenes.keys())
