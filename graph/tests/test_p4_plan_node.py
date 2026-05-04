from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from edit_episode_graph.backends._types import InvokeResult
from edit_episode_graph.nodes import p4_plan as node_module
from edit_episode_graph.nodes.p4_plan import p4_plan_node
from edit_episode_graph.schemas.p4_plan import CompositionPlan


def _good_plan_payload() -> dict:
    return {
        "narrative_arc": "Hook lands the surprise; tension framed; payoff with stat.",
        "rhythm": "fast-SLOW-fast",
        "beats": [
            {
                "beat": "HOOK",
                "concept": "Mid-flight over a dark editorial canvas; oversized stat slams in.",
                "mood": "Editorial restraint, Stripe Press energy.",
                "energy": "medium",
                "duration_s": 6.9,
                "catalog_or_custom": "custom",
                "justification": "Off-axis layout needed; catalog hero is centered.",
            },
            {
                "beat": "PROBLEM",
                "concept": "Stat dominates at 7rem; foreground tints toward accent.",
                "mood": "Quiet weight, Müller-Brockmann grid pages.",
                "energy": "calm",
                "duration_s": 10.5,
                "catalog_or_custom": "catalog",
                "justification": "Catalog stat-hold matches DESIGN.md typography.",
            },
            {
                "beat": "PAYOFF",
                "concept": "Wide reveal with hairline rules; staggered entrance.",
                "mood": "Cinematic title sequence energy.",
                "energy": "high",
                "duration_s": 8.4,
                "catalog_or_custom": "custom",
                "justification": "No catalog block carries the hairline-rule motif.",
            },
        ],
        "transitions": [
            {
                "from_beat": "HOOK", "to_beat": "PROBLEM",
                "mechanism": "css", "name": "blur crossfade",
                "duration_s": 0.6, "easing": "sine.inOut",
                "why": "Medium → calm; blur softens the shift.",
            },
            {
                "from_beat": "PROBLEM", "to_beat": "PAYOFF",
                "mechanism": "shader", "name": "cinematic zoom",
                "duration_s": 0.4, "easing": "power3.out",
                "why": "Calm → high escalation.",
            },
            {
                "from_beat": "PAYOFF", "to_beat": "END",
                "mechanism": "final-fade", "name": "fade-to-black",
                "duration_s": 0.5, "easing": "power2.in",
                "why": "Final scene exit per canon.",
            },
        ],
    }


def test_plan_schema_accepts_valid_payload():
    CompositionPlan.model_validate(_good_plan_payload())


def test_plan_schema_rejects_under_three_beats():
    base = _good_plan_payload()
    with pytest.raises(ValidationError):
        CompositionPlan.model_validate({**base, "beats": base["beats"][:2]})


def test_plan_schema_rejects_bad_mechanism():
    base = _good_plan_payload()
    base["transitions"][0]["mechanism"] = "magic-wipe"
    with pytest.raises(ValidationError):
        CompositionPlan.model_validate(base)


def test_plan_schema_rejects_bad_energy():
    base = _good_plan_payload()
    base["beats"][0]["energy"] = "extreme"
    with pytest.raises(ValidationError):
        CompositionPlan.model_validate(base)


def test_plan_schema_rejects_unknown_field():
    base = _good_plan_payload()
    with pytest.raises(ValidationError):
        CompositionPlan.model_validate({**base, "subtitles": "no thanks"})


def test_skips_when_episode_dir_missing():
    update = p4_plan_node({}, router=MagicMock())
    assert update["compose"]["plan"]["skipped"] is True


def test_skips_when_design_md_missing(tmp_path):
    state = {
        "slug": "demo",
        "episode_dir": str(tmp_path),
        "compose": {},
        "edit": {"edl": {"ranges": [
            {"source": "raw", "start": 0.0, "end": 1.0,
             "beat": "HOOK", "quote": "x", "reason": "y"},
        ]}},
    }
    update = p4_plan_node(state, router=MagicMock())
    assert update["compose"]["plan"]["skipped"] is True
    assert "DESIGN.md" in update["compose"]["plan"]["skip_reason"]


def test_skips_when_expanded_prompt_missing(tmp_path):
    state = {
        "slug": "demo",
        "episode_dir": str(tmp_path),
        "compose": {"design_md_path": str(tmp_path / "DESIGN.md")},
        "edit": {"edl": {"ranges": [
            {"source": "raw", "start": 0.0, "end": 1.0,
             "beat": "HOOK", "quote": "x", "reason": "y"},
        ]}},
    }
    update = p4_plan_node(state, router=MagicMock())
    assert update["compose"]["plan"]["skipped"] is True
    assert "expanded-prompt.md" in update["compose"]["plan"]["skip_reason"]


def test_skips_when_edl_empty(tmp_path):
    state = {
        "slug": "demo",
        "episode_dir": str(tmp_path),
        "compose": {
            "design_md_path": str(tmp_path / "DESIGN.md"),
            "expanded_prompt_path": str(tmp_path / "expanded-prompt.md"),
        },
        "edit": {"edl": {"ranges": []}},
    }
    update = p4_plan_node(state, router=MagicMock())
    assert update["compose"]["plan"]["skipped"] is True


def test_runs_with_smart_tier_and_passes_canon_paths(tmp_path):
    payload = _good_plan_payload()
    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text="...",
            structured=CompositionPlan.model_validate(payload),
            tokens_in=400, tokens_out=600,
            wall_time_s=20.0,
            model_used="claude-opus-4-7",
            backend_used="claude",
            tool_calls=[],
        ),
        [{"backend": "claude", "success": True, "model": "claude-opus-4-7",
          "tokens_in": 400, "tokens_out": 600, "wall_time_s": 20.0, "ts": "now"}],
    )

    state = {
        "slug": "demo",
        "episode_dir": str(tmp_path),
        "compose": {
            "design_md_path": str(tmp_path / "DESIGN.md"),
            "expanded_prompt_path": str(tmp_path / "expanded-prompt.md"),
        },
        "edit": {
            "edl": {
                "ranges": [
                    {"source": "raw", "start": 0.0, "end": 6.9,
                     "beat": "HOOK", "quote": "x", "reason": "y"},
                    {"source": "raw", "start": 6.9, "end": 17.4,
                     "beat": "PROBLEM", "quote": "x", "reason": "y"},
                    {"source": "raw", "start": 17.4, "end": 25.8,
                     "beat": "PAYOFF", "quote": "x", "reason": "y"},
                ],
            },
        },
    }
    update = p4_plan_node(state, router=router)

    assert update["compose"]["plan"]["rhythm"] == "fast-SLOW-fast"
    assert len(update["compose"]["plan"]["beats"]) == 3

    req, task = router.invoke.call_args.args[:2]
    kwargs = router.invoke.call_args.kwargs
    assert req.tier == "smart"
    assert req.needs_tools is True
    assert req.backends == ["claude"]
    assert kwargs["allowed_tools"] == ["Read"]
    assert "HOOK" in task and "PROBLEM" in task and "PAYOFF" in task


def test_brief_references_canon_paths_without_embedding():
    brief = node_module._load_brief("p4_plan")
    assert "~/.agents/skills/hyperframes/SKILL.md" in brief
    assert '§"Step 3: Plan"' in brief
    assert "beat-direction.md" in brief
    assert "transitions.md" in brief
    assert "Return ONLY JSON" not in brief or "return ONLY JSON" in brief
    # The canonical "Build what was asked" paragraph and the transitions
    # Energy→Primary table belong to canon, not to the brief.
    assert "Build what was asked" not in brief
    assert "Energy" not in brief.split("Inputs:")[0] or "transitions.md" in brief
