"""Unit tests for p4_redispatch_beat — beat-owner attribution paths (HOM-266).

The node dispatches an LLM sub-agent to re-author one scene fragment after
a cluster-gate fail, then attributes the returned body to a scene_id by
scanning for the `id="scene-<sid>"` marker. These tests cover the
attribution branches added in the HOM-266 review:

  - happy path: single-marker body → attributed to that scene_id
  - multi-marker body → attributed to first plan-order match + notice
  - marker-miss → hard error, no silent overwrite (BLOCKER fix)
  - empty body → hard error (parity with marker-miss)
  - sibling preservation on shallow `_scenes_merge` reducer (CONCERN 2)
"""

from __future__ import annotations

from unittest.mock import MagicMock

from edit_episode_graph.backends._types import InvokeResult
from edit_episode_graph.nodes.p4_redispatch_beat import p4_redispatch_beat_node
from edit_episode_graph.schemas.p4_beat import BeatOutput


_ATTEMPTS = [{
    "backend": "claude", "success": True, "model": "claude-opus-4-7",
    "tokens_in": 100, "tokens_out": 50, "wall_time_s": 1.0, "ts": "now",
}]


def _state(scenes: dict | None = None) -> dict:
    return {
        "slug": "demo",
        "episode_dir": ".",
        "scenes": scenes or {},
        "index_html": "<html><body>assembled</body></html>",
        "compose": {
            "index_html": "<html><body>assembled</body></html>",
            "plan": {
                "beats": [
                    {"beat": "Hook", "duration_s": 4.5},
                    {"beat": "Payoff", "duration_s": 5.0},
                ],
            },
            "design": {"design_md": "# Design"},
            "expansion": {"expanded_prompt": "expanded"},
            "assemble": {"data_width": 1080, "data_height": 1920},
        },
        "gate_results": [{
            "gate": "gate:design_adherence",
            "passed": False,
            "iteration": 1,
            "violations": [{"selector": "#scene-hook", "message": "x"}],
        }],
    }


def _router_returning(html: str) -> MagicMock:
    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text="ok",
            structured=BeatOutput(html=html),
            tokens_in=100, tokens_out=50, wall_time_s=1.0,
            model_used="claude-opus-4-7", backend_used="claude",
            tool_calls=[],
        ),
        _ATTEMPTS,
    )
    return router


def test_happy_path_single_marker_attributed():
    body = '<div id="scene-hook"><p>fixed</p></div>'
    update = p4_redispatch_beat_node(_state(), router=_router_returning(body))
    assert "scenes" in update
    assert "hook" in update["scenes"]
    assert update["scenes"]["hook"]["html"] == body
    assert not update.get("errors")


def test_multi_marker_attributes_first_match_with_notice():
    # Body references both scene-hook and scene-payoff. First plan-order match wins.
    body = (
        '<div id="scene-hook"><p>fixed</p></div>'
        '<!-- ref: <div id="scene-payoff"> -->'
    )
    update = p4_redispatch_beat_node(_state(), router=_router_returning(body))
    assert "hook" in update.get("scenes", {})
    notices = update.get("notices") or []
    assert any("multiple plan-order scene_ids" in n for n in notices), notices
    assert not update.get("errors")


def test_marker_miss_emits_error_no_silent_overwrite():
    # No id="scene-<sid>" matching any plan-order scene_id.
    body = '<div id="scene-unknown"><p>orphan</p></div>'
    state = _state(scenes={"hook": {"html": "<prior/>"}})
    update = p4_redispatch_beat_node(state, router=_router_returning(body))
    # BLOCKER fix: no silent overwrite — no scenes update.
    assert "scenes" not in update
    errors = update.get("errors") or []
    assert errors, "expected errors[] entry"
    assert any("un-attributable" in e.get("message", "") for e in errors), errors


def test_empty_body_emits_error():
    # Pydantic BeatOutput enforces min_length=1, so simulate empty by
    # returning a non-BeatOutput-shaped result that yields empty html.
    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text="",
            structured=None,  # no parsed schema → raw_text branch in LLMNode
            tokens_in=10, tokens_out=0, wall_time_s=0.1,
            model_used="m", backend_used="claude", tool_calls=[],
        ),
        _ATTEMPTS,
    )
    update = p4_redispatch_beat_node(_state(), router=router)
    assert "scenes" not in update
    errors = update.get("errors") or []
    assert any("empty BeatOutput.html" in e.get("message", "") for e in errors), errors


def test_sibling_preservation_under_shallow_merge():
    # Prior per-scene entry carries metadata. Redispatch must preserve it.
    body = '<div id="scene-hook"><p>fixed</p></div>'
    state = _state(scenes={
        "hook": {"html": "<old/>", "attempt": 2, "model": "claude-opus-4-7"},
        "payoff": {"html": "<other/>"},
    })
    update = p4_redispatch_beat_node(state, router=_router_returning(body))
    picked = update["scenes"]["hook"]
    assert picked["html"] == body
    assert picked.get("attempt") == 2
    assert picked.get("model") == "claude-opus-4-7"
