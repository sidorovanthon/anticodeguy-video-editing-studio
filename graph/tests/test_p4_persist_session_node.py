"""Unit tests for p4_persist_session node and brief contract."""

from __future__ import annotations

from unittest.mock import MagicMock

from edit_episode_graph.backends._types import InvokeResult
from edit_episode_graph.nodes import p4_persist_session as node_module
from edit_episode_graph.nodes.p4_persist_session import (
    _phase4_gate_records,
    p4_persist_session_node,
)
from edit_episode_graph.schemas.p4_persist_session import PersistSessionResult


def _ok_state(tmp_path, **overrides):
    base = {
        "slug": "demo",
        "episode_dir": str(tmp_path),
        "compose": {
            "design": {"design_md_path": str(tmp_path / "hyperframes" / "DESIGN.md")},
            "expansion": {"expanded_prompt_path": str(tmp_path / "hyperframes" / ".hyperframes" / "expanded-prompt.md")},
            "plan": {
                "beats": [
                    {"id": "b1", "title": "Hook", "duration_s": 3.0},
                    {"id": "b2", "title": "Reveal", "duration_s": 4.5},
                ],
            },
            "captions_block_path": str(tmp_path / "hyperframes" / ".hyperframes" / "captions.html"),
            "assemble": {
                "assembled_at": str(tmp_path / "hyperframes" / "index.html"),
                "index_html_path": str(tmp_path / "hyperframes" / "index.html"),
            },
            "beats": [
                {"beat_id": "b1", "scene_path": "compositions/b1.html", "status": "rendered"},
            ],
        },
        "gate_results": [
            {"gate": "gate:design_ok", "passed": True},
            {"gate": "gate:plan_ok", "passed": True},
            {"gate": "gate:eval_ok", "passed": True},  # phase 3 — must NOT leak into phase 4 brief
        ],
    }
    base.update(overrides)
    return base


def _stub_router_returning(persisted_at: str, session_n: int) -> MagicMock:
    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text=f'{{"persisted_at":"{persisted_at}","session_n":{session_n}}}',
            structured=PersistSessionResult(persisted_at=persisted_at, session_n=session_n),
            tokens_in=180,
            tokens_out=24,
            wall_time_s=1.1,
            model_used="claude-haiku-4-5-20251001",
            backend_used="claude",
            tool_calls=[],
        ),
        [{"backend": "claude", "success": True, "model": "claude-haiku-4-5-20251001",
          "tokens_in": 180, "tokens_out": 24, "wall_time_s": 1.1, "ts": "now"}],
    )
    return router


def test_skips_when_no_episode_dir():
    update = p4_persist_session_node({}, router=MagicMock())
    assert update["compose"]["persist"]["skipped"] is True
    assert "episode_dir" in update["compose"]["persist"]["skip_reason"]


def test_skips_when_assemble_skipped(tmp_path):
    state = {
        "slug": "demo",
        "episode_dir": str(tmp_path),
        "compose": {"assemble": {"skipped": True, "skip_reason": "no scenes"}},
    }
    update = p4_persist_session_node(state, router=MagicMock())
    assert update["compose"]["persist"]["skipped"] is True
    assert "assemble skipped" in update["compose"]["persist"]["skip_reason"]


def test_skips_when_no_assembled_index(tmp_path):
    state = {
        "slug": "demo",
        "episode_dir": str(tmp_path),
        "compose": {"assemble": {}},
    }
    update = p4_persist_session_node(state, router=MagicMock())
    assert update["compose"]["persist"]["skipped"] is True
    assert "assembled" in update["compose"]["persist"]["skip_reason"]


def test_phase4_gate_filter_excludes_phase3_records():
    state = {
        "gate_results": [
            {"gate": "gate:edl_ok", "passed": True},
            {"gate": "gate:eval_ok", "passed": True},
            {"gate": "gate:plan_ok", "passed": True},
            {"gate": "gate:static_guard", "passed": True},
        ]
    }
    gates = _phase4_gate_records(state)
    names = {g["gate"] for g in gates}
    assert names == {"gate:plan_ok", "gate:static_guard"}


def test_runs_with_tools_and_embeds_phase4_inputs(tmp_path):
    target = str(tmp_path / "edit" / "project.md")
    router = _stub_router_returning(target, 2)
    state = _ok_state(tmp_path)

    update = p4_persist_session_node(state, router=router)

    assert update["compose"]["persist"]["session_n"] == 2
    assert update["compose"]["persist"]["persisted_at"].endswith("project.md")
    assert update["compose"]["session_persisted"] is True
    assert update["llm_runs"][0]["node"] == "p4_persist_session"

    req, task = router.invoke.call_args.args[:2]
    kwargs = router.invoke.call_args.kwargs
    assert req.tier == "cheap"
    assert req.needs_tools is True
    assert kwargs["allowed_tools"] == ["Read", "Write"]
    # Phase 4 inputs must appear in the rendered brief.
    assert "DESIGN.md" in task
    assert "expanded-prompt.md" in task
    assert "Hook" in task and "Reveal" in task
    assert "captions.html" in task
    assert "index.html" in task
    # Phase 3 gate must NOT leak into the rendered task.
    assert "gate:eval_ok" not in task
    # Phase 4 gates that exist in state must appear.
    assert "gate:design_ok" in task
    assert "gate:plan_ok" in task


def test_idempotent_increments_session_n_on_re_run(tmp_path):
    """Re-running with a higher session_n response simulates the agent
    finding existing blocks in project.md and incrementing N. The node
    itself never overwrites — it just records what the agent reported."""
    target = str(tmp_path / "edit" / "project.md")
    state = _ok_state(tmp_path)

    update1 = p4_persist_session_node(state, router=_stub_router_returning(target, 1))
    assert update1["compose"]["persist"]["session_n"] == 1

    update2 = p4_persist_session_node(state, router=_stub_router_returning(target, 2))
    assert update2["compose"]["persist"]["session_n"] == 2
    # Same persisted_at — both runs target the same file.
    assert update1["compose"]["persist"]["persisted_at"] == update2["compose"]["persist"]["persisted_at"]


def test_brief_references_canon_memory_section():
    brief = node_module._load_brief("p4_persist_session")
    assert "~/.claude/skills/video-use/SKILL.md" in brief
    assert '§"Memory' in brief
    assert "Return JSON only" in brief or '"persisted_at"' in brief


def test_brief_does_not_embed_canon_field_names():
    """Brief references canon, does not embed canonical bullet field names
    (`Strategy:`, `Decisions:`, `Reasoning log:`, `Outstanding:`). The
    sub-agent reads canon at call time."""
    brief = node_module._load_brief("p4_persist_session")
    forbidden = ["Decisions:", "Reasoning log:", "Outstanding:"]
    for marker in forbidden:
        assert marker not in brief, f"brief embeds canonical field marker: {marker}"


def test_brief_marks_phase4_distinct_from_phase3():
    """Both phases share project.md; the block must self-identify as Phase 4
    so a future reader (and the next session-numbering scan) can tell them
    apart even though the heading shape is identical."""
    brief = node_module._load_brief("p4_persist_session")
    assert "Phase 4" in brief
