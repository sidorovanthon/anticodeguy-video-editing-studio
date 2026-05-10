"""Routing tests for p4_persist_session and the assemble→persist→studio path."""

from __future__ import annotations

from langgraph.graph import END

from edit_episode_graph.nodes import _routing


def test_assemble_success_routes_to_p4_transitions():
    """HOM-137: assemble success leg routes to p4_transitions; the gate cluster
    starts after transitions are authored (p4_transitions → gate_lint)."""
    state = {"compose": {"assemble": {"assembled_at": "/tmp/index.html"}}}
    assert _routing.route_after_assemble_index(state) == "p4_transitions"


def test_assemble_skip_still_routes_to_halt():
    state = {"compose": {"assemble": {"skipped": True, "skip_reason": "no scenes"}}}
    assert _routing.route_after_assemble_index(state) == "halt_llm_boundary"


def test_assemble_error_routes_to_end():
    state = {"errors": [{"node": "p4_assemble_index", "message": "boom", "timestamp": "t"}]}
    assert _routing.route_after_assemble_index(state) == END


def test_persist_session_routes_to_studio_on_clean_run():
    state = {
        "compose": {
            "persist": {"persisted_at": "/tmp/project.md", "session_n": 1},
            "session_persisted": True,
        }
    }
    assert _routing.route_after_p4_persist_session(state) == "studio_launch"


def test_persist_session_routes_to_studio_on_skip():
    """A persist skip is non-fatal — preview still happens."""
    state = {"compose": {"persist": {"skipped": True, "skip_reason": "no episode_dir"}}}
    assert _routing.route_after_p4_persist_session(state) == "studio_launch"


def test_persist_session_router_ignores_historical_errors():
    """HOM-158: p4_persist_session is an LLM node — raises on terminal failure;
    routing proceeds to studio_launch regardless of historical errors.
    """
    state = {"errors": [{"node": "p4_persist_session", "message": "boom", "timestamp": "old"}]}
    assert _routing.route_after_p4_persist_session(state) == "studio_launch"
