from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from edit_episode_graph.backends._types import InvokeResult
from edit_episode_graph.nodes.p3_pre_scan import p3_pre_scan_node
from edit_episode_graph.schemas.p3_pre_scan import PreScanReport, Slip


def test_skips_when_takes_packed_missing(tmp_path):
    state = {"slug": "demo", "episode_dir": str(tmp_path)}
    update = p3_pre_scan_node(state, router=MagicMock())
    assert update["edit"]["pre_scan"]["skipped"] is True
    assert "takes_packed.md" in (update["edit"]["pre_scan"].get("skip_reason") or "")
    assert "llm_runs" not in update or update["llm_runs"] == []


def test_runs_when_takes_packed_present(tmp_path):
    edit_dir = tmp_path / "edit"
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

    state = {"slug": "demo", "episode_dir": str(tmp_path)}
    update = p3_pre_scan_node(state, router=router)
    assert update["edit"]["pre_scan"]["slips"] == [
        {"quote": "hello", "take_index": 1, "reason": "placeholder"},
    ]
    assert update["edit"]["pre_scan"]["source_path"].endswith("takes_packed.md")
    assert update["llm_runs"][0]["node"] == "p3_pre_scan"
