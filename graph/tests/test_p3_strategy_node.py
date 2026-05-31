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


@pytest.fixture
def project_root_episode(tmp_path, monkeypatch):
    slug = "demo"
    episode_dir = tmp_path / "episodes" / slug
    episode_dir.mkdir(parents=True)
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    return slug, episode_dir


def test_skips_when_takes_packed_missing(project_root_episode):
    slug, episode_dir = project_root_episode
    state = {"slug": slug, "episode_dir": str(episode_dir)}
    update = p3_strategy_node(state, router=MagicMock())
    assert update["edit"]["strategy"]["skipped"] is True
    assert "takes_packed.md" in (update["edit"]["strategy"].get("skip_reason") or "")


def test_runs_with_no_tools_and_embeds_inputs(project_root_episode):
    slug, episode_dir = project_root_episode
    edit_dir = episode_dir / "edit"
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
        "slug": slug,
        "episode_dir": str(episode_dir),
        "edit": {"pre_scan": {"slips": [{"quote": "bad", "take_index": 1, "reason": "slip"}]}},
    }
    update = p3_strategy_node(state, router=router)

    # HOM-223: identity-only state — `source_path` no longer written.
    assert update["edit"]["strategy"] == {
        "shape": "hook",
        "takes": ["take 1"],
        "grade": "neutral",
        "pacing": "tight",
        "length_estimate_s": 12.0,
    }
    assert update["llm_runs"][0]["node"] == "p3_strategy"
    req, task = router.invoke.call_args.args[:2]
    kwargs = router.invoke.call_args.kwargs
    assert req.tier == "expensive"
    assert req.needs_tools is False
    assert req.backends == ["claude"]
    assert kwargs["allowed_tools"] == []
    assert "hello world" in task
    assert '"quote": "bad"' in task


def test_strategy_brief_pulls_canon_verbatim():
    """HOM-377: the brief no longer cites canon by path — it pulls the
    load-bearing sections VERBATIM from the live skill at run time via the
    `canon.*` render-ctx (the `canon_section` macro labels each block). This
    test asserts the wiring is present in the raw template (the verbatim text
    is injected at render time; resolution is covered by
    graph/tests/test_canon_loader.py)."""
    brief = node_module._load_brief("p3_strategy")
    # canon_section titles name the pulled sections (video-use §The process
    # Step 4, §Cut craft, §Color grade).
    assert "VERBATIM" in brief
    assert "Step 4 (Propose strategy)" in brief
    assert "Cut craft" in brief
    assert "Color grade" in brief
    # the canon blocks are injected from the render context, not embedded
    assert "canon.process_propose_strategy" in brief
    # orchestrator-house clarification on `grade` is retained
    assert "render.py" in brief
    assert "Return ONLY JSON" in brief
