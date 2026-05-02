# graph/tests/test_llm_node.py
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from pydantic import BaseModel

from edit_episode_graph.backends._types import InvokeResult, NodeRequirements
from edit_episode_graph.nodes._llm import LLMNode


class _Out(BaseModel):
    n: int


def _fake_router(structured):
    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(raw_text='{"n":1}', structured=structured, tokens_in=10,
                     tokens_out=2, wall_time_s=0.5, model_used="m", backend_used="claude", tool_calls=[]),
        [{"backend": "claude", "success": True, "model": "m", "tokens_in": 10, "tokens_out": 2,
          "wall_time_s": 0.5, "ts": datetime.now(timezone.utc).isoformat()}],
    )
    return router


def test_llm_node_returns_state_update():
    node = LLMNode(
        name="demo",
        requirements=NodeRequirements("cheap", needs_tools=False, backends=["claude"]),
        brief_template="hello {{ slug }}",
        output_schema=_Out,
        result_namespace="edit",
        result_key="demo",
        timeout_s=10,
    )
    state = {"slug": "abc", "episode_dir": str(Path.cwd())}
    update = node._invoke_with(_fake_router(_Out(n=1)), state, render_ctx={"slug": "abc"})
    assert update["edit"]["demo"] == {"n": 1}
    assert update["llm_runs"][0]["node"] == "demo"
    assert update["llm_runs"][0]["success"] is True


def test_llm_node_records_failure(monkeypatch):
    from edit_episode_graph.backends._types import AllBackendsExhausted
    router = MagicMock()
    router.invoke.side_effect = AllBackendsExhausted([
        {"backend": "claude", "success": False, "reason": "auth", "ts": "t"},
    ])
    node = LLMNode(
        name="demo", requirements=NodeRequirements("cheap", False, ["claude"]),
        brief_template="hi", output_schema=_Out, result_namespace="edit",
        result_key="demo", timeout_s=5,
    )
    update = node._invoke_with(router, {"slug": "x", "episode_dir": str(Path.cwd())}, render_ctx={})
    assert "errors" in update
    assert update["llm_runs"][0]["success"] is False
