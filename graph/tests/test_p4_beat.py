"""Unit tests for p4_beat — per-scene LLM authoring node (HOM-134).

Per spec `2026-05-04-hom-122-p4-beats-fan-out-design.md` §"`p4_beat` node":
  - cached skip when fragment already exists with non-zero size
  - AllBackendsExhausted handling (delegated to LLMNode base)
  - brief render context completeness (every Jinja variable resolves)
  - mocked happy path (router invoked with smart tier, has_tools, allowed_tools)

`p4_beat` runs as a Send-spawned branch — its state already includes the
`_beat_dispatch` namespace populated by `p4_dispatch_beats`. Tests construct
that namespace by hand; the dispatcher's payload shape is covered separately
in `test_p4_dispatch_beats.py`.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from edit_episode_graph.backends._types import InvokeResult
from edit_episode_graph.nodes import p4_beat as node_module
from edit_episode_graph.nodes.p4_beat import p4_beat_node


def _beat_dispatch(scene_html_path: str, **overrides) -> dict:
    base = {
        "scene_id": "hook",
        "beat_index": 0,
        "total_beats": 3,
        "is_final": False,
        "data_start_s": 0.0,
        "data_duration_s": 4.5,
        "data_track_index": 1,
        "data_width": 1920,
        "data_height": 1080,
        "plan_beat": {
            "beat": "Hook",
            "duration_s": 4.5,
            "energy": "medium",
            "intent": "set the stakes",
        },
        "scene_html_path": scene_html_path,
    }
    base.update(overrides)
    return base


def _state(tmp_path: Path, scene_html_path: str, **bd_overrides) -> dict:
    return {
        "slug": "demo",
        "episode_dir": str(tmp_path),
        "compose": {
            "design_md_path": str(tmp_path / "hyperframes" / "DESIGN.md"),
            "expanded_prompt_path": str(
                tmp_path / "hyperframes" / ".hyperframes" / "expanded-prompt.md"
            ),
            "catalog": {
                "blocks": [{"name": "stat-card", "path": "blocks/stat-card.html"}],
                "components": [{"name": "marker-sweep", "path": "components/marker-sweep.html"}],
            },
        },
        "_beat_dispatch": _beat_dispatch(scene_html_path, **bd_overrides),
    }


# ---------------------------------------------------------------------------
# cached skip
# ---------------------------------------------------------------------------


def test_cached_skip_when_fragment_exists_nonempty(tmp_path):
    fragment = tmp_path / "hyperframes" / "compositions" / "hook.html"
    fragment.parent.mkdir(parents=True)
    fragment.write_text("<div id='scene-hook'></div>", encoding="utf-8")

    router = MagicMock()
    update = p4_beat_node(_state(tmp_path, str(fragment)), router=router)

    assert router.invoke.call_count == 0
    notices = update.get("notices") or []
    assert any("cached" in n and "hook" in n for n in notices), notices


def test_no_cached_skip_when_fragment_zero_bytes(tmp_path):
    fragment = tmp_path / "hyperframes" / "compositions" / "hook.html"
    fragment.parent.mkdir(parents=True)
    fragment.write_text("", encoding="utf-8")  # 0 bytes — must NOT short-circuit

    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text="Wrote .../hook.html (10 elements, 6 tweens).",
            structured=None,
            tokens_in=400, tokens_out=200, wall_time_s=8.0,
            model_used="claude-haiku-4-5-20251001", backend_used="claude",
            tool_calls=[],
        ),
        [{"backend": "claude", "success": True, "model": "claude-haiku-4-5-20251001",
          "tokens_in": 400, "tokens_out": 200, "wall_time_s": 8.0, "ts": "now"}],
    )
    p4_beat_node(_state(tmp_path, str(fragment)), router=router)
    assert router.invoke.call_count == 1


def test_no_cached_skip_when_fragment_missing(tmp_path):
    fragment = tmp_path / "hyperframes" / "compositions" / "hook.html"
    # parent dir does not even exist yet

    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text="ok", structured=None,
            tokens_in=400, tokens_out=200, wall_time_s=8.0,
            model_used="claude-haiku-4-5-20251001", backend_used="claude",
            tool_calls=[],
        ),
        [{"backend": "claude", "success": True, "model": "claude-haiku-4-5-20251001",
          "tokens_in": 400, "tokens_out": 200, "wall_time_s": 8.0, "ts": "now"}],
    )
    p4_beat_node(_state(tmp_path, str(fragment)), router=router)
    assert router.invoke.call_count == 1


# ---------------------------------------------------------------------------
# happy path — mocked router
# ---------------------------------------------------------------------------


def test_happy_path_dispatches_with_correct_requirements(tmp_path):
    fragment = tmp_path / "hyperframes" / "compositions" / "hook.html"

    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text="Wrote ... (10 elements, 6 tweens).", structured=None,
            tokens_in=600, tokens_out=400, wall_time_s=15.0,
            model_used="claude-opus-4-7", backend_used="claude",
            tool_calls=[],
        ),
        [{"backend": "claude", "success": True, "model": "claude-opus-4-7",
          "tokens_in": 600, "tokens_out": 400, "wall_time_s": 15.0, "ts": "now"}],
    )

    update = p4_beat_node(_state(tmp_path, str(fragment)), router=router)

    req, task = router.invoke.call_args.args[:2]
    kwargs = router.invoke.call_args.kwargs
    assert req.tier == "smart"
    assert req.needs_tools is True
    assert req.backends == ["claude"]
    assert kwargs["allowed_tools"] == ["Read", "Write"]
    # no output_schema — sub-agent writes a file, returns prose summary.
    assert kwargs.get("output_schema") is None
    # llm_runs telemetry surfaces from LLMNode base.
    assert update.get("llm_runs") and update["llm_runs"][0]["backend"] == "claude"


def test_brief_renders_all_required_variables(tmp_path):
    fragment = tmp_path / "hyperframes" / "compositions" / "hook.html"

    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text="ok", structured=None,
            tokens_in=1, tokens_out=1, wall_time_s=0.1,
            model_used="m", backend_used="claude", tool_calls=[],
        ),
        [{"backend": "claude", "success": True, "model": "m",
          "tokens_in": 1, "tokens_out": 1, "wall_time_s": 0.1, "ts": "now"}],
    )

    p4_beat_node(_state(tmp_path, str(fragment)), router=router)
    task = router.invoke.call_args.args[1]
    # Render context must be non-empty for every Jinja variable in the brief.
    assert "hook" in task                              # scene_id
    assert "1920" in task and "1080" in task           # data_width / data_height
    assert "4.5" in task                               # data_duration_s
    assert "DESIGN.md" in task                         # design_md_path
    assert "expanded-prompt.md" in task                # expanded_prompt_path
    assert "stat-card" in task                         # catalog summary block
    assert "marker-sweep" in task                      # catalog summary component
    assert str(fragment) in task                       # scene_html_path output target
    assert "Hook" in task                              # plan_beat


def test_final_scene_brief_surfaces_is_final(tmp_path):
    fragment = tmp_path / "hyperframes" / "compositions" / "payoff.html"

    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text="ok", structured=None,
            tokens_in=1, tokens_out=1, wall_time_s=0.1,
            model_used="m", backend_used="claude", tool_calls=[],
        ),
        [{"backend": "claude", "success": True, "model": "m",
          "tokens_in": 1, "tokens_out": 1, "wall_time_s": 0.1, "ts": "now"}],
    )

    state = _state(
        tmp_path, str(fragment),
        scene_id="payoff", beat_index=2, total_beats=3, is_final=True,
        plan_beat={"beat": "Payoff", "duration_s": 3.0, "energy": "high", "intent": "land it"},
    )
    p4_beat_node(state, router=router)
    task = router.invoke.call_args.args[1]
    # Brief surfaces is_final so the sub-agent knows HR 4 final-fade is permitted.
    assert "is_final" in task or "final scene" in task.lower()


# ---------------------------------------------------------------------------
# brief shape: references canon, does not embed
# ---------------------------------------------------------------------------


def test_brief_references_canon_paths_without_embedding():
    brief = node_module._load_brief("p4_beat")
    # Mandatory canon read-list per spec §"Brief — `briefs/p4_beat.j2`"
    assert "~/.agents/skills/hyperframes/SKILL.md" in brief
    assert "transitions/catalog.md" in brief
    assert "motion-principles.md" in brief
    assert "video-composition.md" in brief
    assert "typography.md" in brief
    assert "beat-direction.md" in brief
    assert "transitions.md" in brief
    assert "house-style.md" in brief
    # Brief-level imperatives that materialise canon-derived guarantees.
    assert "tl.fromTo" in brief
    assert "#scene-" in brief                       # CSS scoping discipline
    # Avoid the literal substring `repeat: -1` even in our brief —
    # HF lint regex false-positive (memory `feedback_lint_regex_repeat_minus_one_in_comments`).
    assert "repeat: -1" not in brief
    # HOM-145: brief MUST forbid infinite repeats with the canonical replacement
    # formula, citing canon (SKILL.md §Animation Guardrails). Without this rule
    # smart agents emit `repeat: -1` and gate:lint blocks Phase 4 (HOM-76 verify).
    assert "infinite repeats" in brief.lower() or "infinite-repeat" in brief.lower()
    assert "Math.ceil" in brief
    assert "Animation Guardrails" in brief
    # The brief must NOT lift canonical paragraphs verbatim.
    assert "Layout Before Animation" in brief  # section reference is OK
    # Sanity: the brief stays compact (path-references, ~70 lines target).
    assert brief.count("\n") < 130, f"brief grew to {brief.count(chr(10))} lines — should reference canon, not embed"


# ---------------------------------------------------------------------------
# AllBackendsExhausted — delegated to LLMNode base, but assert routing-friendly shape
# ---------------------------------------------------------------------------


def test_all_backends_exhausted_records_error_and_notice(tmp_path):
    from edit_episode_graph.backends._types import AllBackendsExhausted

    fragment = tmp_path / "hyperframes" / "compositions" / "hook.html"
    router = MagicMock()
    router.invoke.side_effect = AllBackendsExhausted(
        [{"backend": "claude", "success": False, "model": "claude-opus-4-7",
          "reason": "timeout", "wall_time_s": 300.0, "ts": "now"}],
    )

    update = p4_beat_node(_state(tmp_path, str(fragment)), router=router)
    assert update.get("errors") and update["errors"][0]["node"] == "p4_beat"
    assert any("p4_beat" in n for n in (update.get("notices") or []))
    # The fragment was NOT created — assemble_index will collect it as missing.
    assert not fragment.exists()
