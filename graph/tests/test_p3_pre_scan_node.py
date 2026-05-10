from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from edit_episode_graph.backends._types import InvokeResult
from edit_episode_graph.nodes.p3_pre_scan import p3_pre_scan_node
from edit_episode_graph.schemas.p3_pre_scan import PreScanReport, Slip


@pytest.fixture
def project_root_episode(tmp_path, monkeypatch):
    """HOM-223: tests build `<tmp_path>/episodes/<slug>/...` and pin the
    project root so `EpisodePaths(slug)` resolves under tmp_path.

    Returns (slug, episode_dir).
    """
    slug = "demo"
    episode_dir = tmp_path / "episodes" / slug
    episode_dir.mkdir(parents=True)
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    return slug, episode_dir


def test_skips_when_takes_packed_missing(project_root_episode):
    slug, episode_dir = project_root_episode
    state = {"slug": slug, "episode_dir": str(episode_dir)}
    update = p3_pre_scan_node(state, router=MagicMock())
    assert update["edit"]["pre_scan"]["skipped"] is True
    assert "takes_packed.md" in (update["edit"]["pre_scan"].get("skip_reason") or "")
    assert "llm_runs" not in update or update["llm_runs"] == []


def test_runs_when_takes_packed_present(project_root_episode):
    slug, episode_dir = project_root_episode
    edit_dir = episode_dir / "edit"
    edit_dir.mkdir()
    (edit_dir / "takes_packed.md").write_text("# Take 1\nHello.\n", encoding="utf-8")

    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text='{"slips":[{"quote":"hello","take_index":1,"reason":"placeholder"}]}',
            structured=PreScanReport(slips=[Slip(quote="hello", take_index=1, reason="placeholder")]),
            tokens_in=50, tokens_out=20, wall_time_s=1.0,
            model_used="claude-sonnet-4-6", backend_used="claude", tool_calls=[],
        ),
        [{"backend": "claude", "success": True, "model": "claude-sonnet-4-6",
          "tokens_in": 50, "tokens_out": 20, "wall_time_s": 1.0, "ts": "now"}],
    )

    state = {"slug": slug, "episode_dir": str(episode_dir)}
    update = p3_pre_scan_node(state, router=router)
    assert update["edit"]["pre_scan"]["slips"] == [
        {"quote": "hello", "take_index": 1, "reason": "placeholder"},
    ]
    # HOM-223: identity-only state — `source_path` no longer written.
    assert "source_path" not in update["edit"]["pre_scan"]
    assert update["llm_runs"][0]["node"] == "p3_pre_scan"
