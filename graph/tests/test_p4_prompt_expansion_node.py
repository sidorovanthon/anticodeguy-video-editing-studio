from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from edit_episode_graph.backends._types import InvokeResult
from edit_episode_graph.nodes import p4_prompt_expansion as node_module
from edit_episode_graph.nodes.p4_prompt_expansion import p4_prompt_expansion_node
from edit_episode_graph.schemas.p4_prompt_expansion import ExpandedPrompt


def _good_payload(path: str) -> dict:
    return {"expanded_prompt_path": path}


def _state_with_inputs(tmp_path) -> dict:
    return {
        "slug": "demo",
        "episode_dir": str(tmp_path),
        "transcripts": {"final_json_path": str(tmp_path / "edit" / "transcripts" / "final.json")},
        "compose": {
            "design_md_path": str(tmp_path / "hyperframes" / "DESIGN.md"),
            "style_request": "Editorial calm — Stripe-press energy.",
        },
        "edit": {
            "edl": {
                "ranges": [
                    {"source": "raw", "start": 0.0, "end": 1.0,
                     "beat": "HOOK", "quote": "x", "reason": "y"},
                    {"source": "raw", "start": 1.0, "end": 2.0,
                     "beat": "PAYOFF", "quote": "x", "reason": "y"},
                ],
            },
            "strategy": {
                "shape": "hook-problem-payoff",
                "takes": ["raw"],
                "grade": "neutral",
                "pacing": "medium",
                "length_estimate_s": 35.0,
            },
        },
    }


def test_expanded_prompt_schema_requires_path():
    ExpandedPrompt.model_validate(_good_payload("/x/.hyperframes/expanded-prompt.md"))
    with pytest.raises(ValidationError):
        ExpandedPrompt.model_validate({"expanded_prompt_path": ""})


def test_expanded_prompt_schema_rejects_unknown_field():
    with pytest.raises(ValidationError):
        ExpandedPrompt.model_validate(
            {**_good_payload("/x/.hyperframes/expanded-prompt.md"), "extra": "no"},
        )


def test_skips_when_episode_dir_missing():
    update = p4_prompt_expansion_node({}, router=MagicMock())
    assert update["compose"]["expansion"]["skipped"] is True


def test_skips_when_design_md_missing(tmp_path):
    state = {
        "slug": "demo",
        "episode_dir": str(tmp_path),
        "edit": {"edl": {"ranges": [{"beat": "HOOK"}]}},
    }
    update = p4_prompt_expansion_node(state, router=MagicMock())
    assert update["compose"]["expansion"]["skipped"] is True
    assert "DESIGN.md" in update["compose"]["expansion"]["skip_reason"]


def test_skips_when_edl_empty(tmp_path):
    state = _state_with_inputs(tmp_path)
    state["edit"]["edl"] = {"ranges": []}
    update = p4_prompt_expansion_node(state, router=MagicMock())
    assert update["compose"]["expansion"]["skipped"] is True


def test_runs_with_tools_and_mirrors_path(tmp_path):
    expanded = tmp_path / "hyperframes" / ".hyperframes" / "expanded-prompt.md"
    payload = _good_payload(str(expanded))

    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text="...",
            structured=ExpandedPrompt.model_validate(payload),
            tokens_in=600,
            tokens_out=2400,
            wall_time_s=22.0,
            model_used="claude-opus-4-7",
            backend_used="claude",
            tool_calls=[],
        ),
        [{"backend": "claude", "success": True, "model": "claude-opus-4-7",
          "tokens_in": 600, "tokens_out": 2400, "wall_time_s": 22.0, "ts": "now"}],
    )

    state = _state_with_inputs(tmp_path)
    update = p4_prompt_expansion_node(state, router=router)

    assert update["compose"]["expansion"]["expanded_prompt_path"] == str(expanded)
    assert update["compose"]["expanded_prompt_path"] == str(expanded)
    assert expanded.parent.is_dir(), "node must mkdir the .hyperframes dir"

    req, task = router.invoke.call_args.args[:2]
    kwargs = router.invoke.call_args.kwargs
    assert req.tier == "smart"
    assert req.needs_tools is True
    assert req.backends == ["claude"]
    assert kwargs["allowed_tools"] == ["Read", "Write"]
    # Brief renders inputs the agent needs for the expansion.
    assert "HOOK" in task and "PAYOFF" in task
    assert "DESIGN.md" in task
    assert "expanded-prompt.md" in task
    assert "Editorial calm" in task


def test_brief_references_canon_paths_without_embedding():
    brief = node_module._load_brief("p4_prompt_expansion")
    assert "~/.agents/skills/hyperframes/SKILL.md" in brief
    assert '§"Step 2: Prompt expansion"' in brief
    assert "references/prompt-expansion.md" in brief
    assert "references/beat-direction.md" in brief
    assert "references/video-composition.md" in brief
    assert "house-style.md" in brief
    assert "Return ONLY JSON" in brief
    # Spot-check the brief did NOT lift canon's load-bearing prose verbatim —
    # those are canon's, not ours.
    assert "The quality gap between" not in brief
    assert "Do not skip. Do not pass through." not in brief
    # The brief must NOT enumerate canon's six output sections — that would
    # fork canon into our brief and rot the moment upstream renames or
    # reorders. Defer entirely to the canon file (per the sibling
    # `p4_design_system.j2` pattern, and per CLAUDE.md
    # "Decomposition via brief-references-canon").
    assert "Title + style block" not in brief
    assert "Recurring motifs" not in brief
    assert "Negative prompt" not in brief


def test_design_md_path_falls_back_to_nested_design(tmp_path):
    """When a fresh run sets compose.design but the top-level mirror hasn't
    been promoted yet, the node still resolves the design path."""
    expanded = tmp_path / "hyperframes" / ".hyperframes" / "expanded-prompt.md"
    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text="...",
            structured=ExpandedPrompt.model_validate({"expanded_prompt_path": str(expanded)}),
            tokens_in=10, tokens_out=10, wall_time_s=1.0,
            model_used="claude-opus-4-7", backend_used="claude", tool_calls=[],
        ),
        [{"backend": "claude", "success": True, "model": "claude-opus-4-7",
          "tokens_in": 10, "tokens_out": 10, "wall_time_s": 1.0, "ts": "now"}],
    )
    state = _state_with_inputs(tmp_path)
    state["compose"].pop("design_md_path")
    state["compose"]["design"] = {"design_md_path": str(tmp_path / "hyperframes" / "DESIGN.md")}
    update = p4_prompt_expansion_node(state, router=router)
    assert update["compose"]["expanded_prompt_path"] == str(expanded)
    task = router.invoke.call_args.args[1]
    assert "DESIGN.md" in task
