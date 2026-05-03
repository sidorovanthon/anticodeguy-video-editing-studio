from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from edit_episode_graph.backends._types import InvokeResult
from edit_episode_graph.nodes import p3_strategy as node_module
from edit_episode_graph.nodes.p3_strategy import p3_strategy_node
from edit_episode_graph.schemas.p3_strategy import Strategy


def test_strategy_schema_rejects_animation_and_subtitle_fields():
    base = {
        "shape": "Problem to payoff",
        "takes": ["Use take 1 opening"],
        "grade": "clean neutral",
        "pacing": "tight",
        "length_estimate_s": 30.0,
    }
    Strategy.model_validate(base)
    with pytest.raises(ValidationError):
        Strategy.model_validate({**base, "animations": []})
    with pytest.raises(ValidationError):
        Strategy.model_validate({**base, "subtitles": {"enabled": True}})


def test_skips_when_takes_packed_missing(tmp_path):
    state = {"slug": "demo", "episode_dir": str(tmp_path)}
    update = p3_strategy_node(state, router=MagicMock())
    assert update["edit"]["strategy"]["skipped"] is True
    assert "takes_packed.md" in (update["edit"]["strategy"].get("skip_reason") or "")


def test_runs_with_no_tools_and_embeds_inputs(tmp_path):
    edit_dir = tmp_path / "edit"
    edit_dir.mkdir()
    takes = edit_dir / "takes_packed.md"
    takes.write_text("# Packed transcripts\n[000.10-000.80] hello world\n", encoding="utf-8")

    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text='{"shape":"hook","takes":["take 1"],"grade":"neutral","pacing":"tight","length_estimate_s":12}',
            structured=Strategy(
                shape="hook",
                takes=["take 1"],
                grade="neutral",
                pacing="tight",
                length_estimate_s=12,
            ),
            tokens_in=120,
            tokens_out=40,
            wall_time_s=1.0,
            model_used="claude-haiku-4-5-20251001",
            backend_used="claude",
            tool_calls=[],
        ),
        [{"backend": "claude", "success": True, "model": "claude-haiku-4-5-20251001",
          "tokens_in": 120, "tokens_out": 40, "wall_time_s": 1.0, "ts": "now"}],
    )

    state = {
        "slug": "demo",
        "episode_dir": str(tmp_path),
        "edit": {"pre_scan": {"slips": [{"quote": "bad", "take_index": 1, "reason": "slip"}]}},
    }
    update = p3_strategy_node(state, router=router)

    assert update["edit"]["strategy"] == {
        "shape": "hook",
        "takes": ["take 1"],
        "grade": "neutral",
        "pacing": "tight",
        "length_estimate_s": 12.0,
        "source_path": str(takes),
    }
    assert update["llm_runs"][0]["node"] == "p3_strategy"
    req, task = router.invoke.call_args.args[:2]
    kwargs = router.invoke.call_args.kwargs
    assert req.tier == "smart"
    assert req.needs_tools is False
    assert req.backends == ["claude"]
    assert kwargs["allowed_tools"] == []
    assert "hello world" in task
    assert '"quote": "bad"' in task


def test_strategy_brief_mentions_canon_without_embedding_process():
    brief = node_module._load_brief("p3_strategy")
    assert "~/.claude/skills/video-use/SKILL.md" in brief
    assert '§"The process" Step 4' in brief
    assert "Return ONLY JSON" in brief
