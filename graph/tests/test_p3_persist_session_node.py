"""Unit tests for p3_persist_session node and brief contract."""

from __future__ import annotations

from unittest.mock import MagicMock

from edit_episode_graph.backends._types import InvokeResult
from edit_episode_graph.nodes import p3_persist_session as node_module
from edit_episode_graph.nodes.p3_persist_session import (
    _iteration_count,
    p3_persist_session_node,
)
from edit_episode_graph.schemas.p3_persist_session import PersistSessionResult


def test_skips_when_no_episode_dir():
    update = p3_persist_session_node({}, router=MagicMock())
    assert update["edit"]["persist"]["skipped"] is True
    assert "episode_dir" in update["edit"]["persist"]["skip_reason"]


def test_skips_when_edl_missing(tmp_path):
    state = {"slug": "demo", "episode_dir": str(tmp_path), "edit": {}}
    update = p3_persist_session_node(state, router=MagicMock())
    assert update["edit"]["persist"]["skipped"] is True
    assert "EDL" in update["edit"]["persist"]["skip_reason"]


def test_skips_when_edl_explicitly_skipped(tmp_path):
    state = {
        "slug": "demo",
        "episode_dir": str(tmp_path),
        "edit": {"edl": {"skipped": True, "skip_reason": "no takes"}},
    }
    update = p3_persist_session_node(state, router=MagicMock())
    assert update["edit"]["persist"]["skipped"] is True


def test_skips_when_eval_skipped(tmp_path):
    state = {
        "slug": "demo",
        "episode_dir": str(tmp_path),
        "edit": {
            "edl": {"ranges": [{"source": "C0", "start": 0, "end": 1}]},
            "eval": {"skipped": True, "skip_reason": "render skipped"},
        },
    }
    update = p3_persist_session_node(state, router=MagicMock())
    assert update["edit"]["persist"]["skipped"] is True
    assert "eval" in update["edit"]["persist"]["skip_reason"]


def test_iteration_count_from_gate_results():
    state = {
        "gate_results": [
            {"gate": "gate:edl_ok", "passed": True},
            {"gate": "gate:eval_ok", "passed": False},
            {"gate": "gate:eval_ok", "passed": True},
        ]
    }
    assert _iteration_count(state) == 2


def test_iteration_count_floor_is_one():
    assert _iteration_count({}) == 1


def test_runs_with_tools_and_embeds_inputs(tmp_path):
    edit_dir = tmp_path / "edit"
    edit_dir.mkdir()

    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text='{"persisted_at":"x","session_n":1}',
            structured=PersistSessionResult(persisted_at=str(edit_dir / "project.md"), session_n=1),
            tokens_in=200,
            tokens_out=30,
            wall_time_s=1.2,
            model_used="claude-haiku-4-5-20251001",
            backend_used="claude",
            tool_calls=[],
        ),
        [{"backend": "claude", "success": True, "model": "claude-haiku-4-5-20251001",
          "tokens_in": 200, "tokens_out": 30, "wall_time_s": 1.2, "ts": "now"}],
    )

    state = {
        "slug": "demo",
        "episode_dir": str(tmp_path),
        "edit": {
            "strategy": {"shape": "hook", "pacing": "tight", "length_estimate_s": 30.0},
            "edl": {
                "ranges": [{"source": "C0", "start": 0, "end": 5, "reason": "clean delivery"}],
                "grade": "neutral",
            },
            "eval": {"issues": [], "passed": True},
        },
        "gate_results": [{"gate": "gate:eval_ok", "passed": True}],
    }
    update = p3_persist_session_node(state, router=router)

    assert update["edit"]["persist"]["session_n"] == 1
    assert update["edit"]["persist"]["persisted_at"].endswith("project.md")
    assert update["llm_runs"][0]["node"] == "p3_persist_session"

    req, task = router.invoke.call_args.args[:2]
    kwargs = router.invoke.call_args.kwargs
    assert req.tier == "cheap"
    assert req.needs_tools is True
    assert kwargs["allowed_tools"] == ["Read", "Edit", "Write"]
    assert '"shape": "hook"' in task
    assert '"grade": "neutral"' in task
    assert '"passed": true' in task


def test_brief_references_canon_memory_section():
    brief = node_module._load_brief("p3_persist_session")
    assert "~/.claude/skills/video-use/SKILL.md" in brief
    assert '§"Memory' in brief
    assert "Return JSON only" in brief or '"persisted_at"' in brief


def test_brief_does_not_embed_canon_field_names():
    """Per HOM-105 ticket + feedback_graph_decomposition_brief_references_canon,
    the brief must reference canon, not embed the §Memory bullet field names
    (`Strategy:`, `Decisions:`, `Reasoning log:`, `Outstanding:`). The agent
    reads canon at call time — we forked nothing into the brief."""
    brief = node_module._load_brief("p3_persist_session")
    forbidden = ["Decisions:", "Reasoning log:", "Outstanding:"]
    for marker in forbidden:
        assert marker not in brief, f"brief embeds canonical field marker: {marker}"
