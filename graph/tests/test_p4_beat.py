"""Unit tests for p4_beat — per-scene LLM authoring node (HOM-134).

Per spec `2026-05-04-hom-122-p4-beats-fan-out-design.md` §"`p4_beat` node":
  - AllBackendsExhausted handling (delegated to LLMNode base)
  - brief render context completeness (every Jinja variable resolves)
  - mocked happy path (router invoked with smart tier, has_tools, allowed_tools)

`p4_beat` runs as a Send-spawned branch — its state already includes the
`_beat_dispatch` namespace populated by `p4_dispatch_beats`. Tests construct
that namespace by hand; the dispatcher's payload shape is covered separately
in `test_p4_dispatch_beats.py`.

Note (HOM-150): the prior poor-man's FS-existence cached-skip stub was
deleted — caching is now native LangGraph (`CACHE_POLICY` + `SqliteCache`)
which bypasses the node body entirely on cache hits. The node body itself
no longer carries any skip-on-existence logic, so the corresponding test
`test_cached_skip_when_fragment_exists_nonempty` was retired with the stub.
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
# fragment-exists branch (HOM-150: no longer short-circuits — native cache
# wraps the whole node above this point)
# ---------------------------------------------------------------------------


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
    # HOM-193: p4_beat is canonically a creative node (Pattern A scene
    # composition); per memory `feedback_creative_nodes_flagship_tier` it
    # MUST resolve to `tier: expensive` (Opus 4.7). The prior `tier: cheap`
    # pin (HOM-115/-136 fixture-iteration cost saver) was the root cause of
    # HOM-154 gate-redispatch loops — see test_config_tier_routing.py for
    # the production audit.
    assert req.tier == "expensive"
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
    # The trio (prohibition + formula + canon citation) all need to survive any
    # future edit — single-keyword guards are too easy to step over.
    assert "infinite" in brief.lower(), "missing the prohibition language"
    assert "Math.ceil" in brief, "missing the canonical replacement formula"
    assert "Animation Guardrails" in brief, "missing the canon citation"
    # The brief must NOT lift canonical paragraphs verbatim.
    assert "Layout Before Animation" in brief  # section reference is OK
    # Sanity: the brief stays compact (path-references, ~70 lines target).
    # HOM-265 raised the bound from 160 to 200 — Step E partial inlines
    # DESIGN.md / expanded-prompt.md BODIES (state data, not canon) into
    # the brief context so the sub-agent no longer Reads them from disk.
    # The inlined-body wrappers add ~25 lines; the canon-references-not-
    # embeds contract still holds (canon is referenced by path).
    assert brief.count("\n") < 200, f"brief grew to {brief.count(chr(10))} lines — should reference canon, not embed"


# ---------------------------------------------------------------------------
# HOM-165: explicit anti-pattern guards must survive future brief edits
# ---------------------------------------------------------------------------


def test_brief_contains_hom165_anti_pattern_section():
    """HOM-165: the brief must explicitly call out the two recurring
    LLM-introduced patterns — GSAP repeat overshoot and caption exit
    without a kill-tween — so the lint gate doesn't pay redispatch tax
    on every M6 sub-issue smoke. Markers chosen so an accidental revert
    of the anti-patterns section trips this test.
    """
    brief = node_module._load_brief("p4_beat")

    # Section header marker.
    assert "Explicit anti-patterns (DO NOT DO)" in brief, (
        "missing the HOM-165 anti-patterns section header"
    )

    # Anti-pattern 1: GSAP repeat math — Math.floor mandate.
    assert "Math.floor(sceneDuration / cycleDuration)" in brief, (
        "missing the Math.floor canonical replacement formula"
    )
    # Anti-pattern 1: explicit prohibition of Math.ceil for repeat math.
    # Both bare ceil and the ceil-1 idiom are flagged.
    assert "Math.ceil(sceneDuration / cycleDuration) - 1" in brief, (
        "missing the Math.ceil-1 anti-example"
    )
    # The new repeat example in the existing infinite-repeats rule must
    # also be Math.floor (we replaced the previous Math.ceil-1 example).
    assert "Math.ceil(sceneDuration / cycleDuration) - 1," not in brief, (
        "the canonical replacement example still uses the ceil-1 anti-pattern"
    )

    # Anti-pattern 2: exit kill-tween example. HOM-213 rewrote this from a
    # captions-specific example to a scene-content example (headline) so the
    # LLM applies the rule to scene main text — not just captions. The exit
    # pair is `tl.to(opacity:0)` followed by `tl.set(visibility: "hidden")`
    # at fade-end timestamp.
    assert 'tl.to(headline,    { opacity: 0' in brief, (
        "missing the headline-exit fade tween example (HOM-213 generalisation)"
    )
    assert 'tl.set(headline,   { visibility: "hidden" }' in brief, (
        "missing the headline-exit kill-tween example (HOM-213 generalisation)"
    )
    assert "Caption Exit Guarantee" in brief, (
        "missing the captions.md canon section reference"
    )
    # Generalisation phrase — exits beyond captions also need kills.
    assert "Hard-kill every scene boundary" in brief, (
        "missing the motion-principles.md canon bullet reference"
    )


# ---------------------------------------------------------------------------
# HOM-213: positive-presence assertions for the Pattern A exit-pair.
# Existing HOM-165 tests above check the anti-pattern section header + the
# headline kill-tween example exist. These additional assertions verify the
# brief's strengthened framing — symptom citation, scene-IIFE ownership
# clarification, and the canonical fixture as positive control — survive
# any future edit. Triggered by HOM-211 finding (hook + thesis lacked the
# pair while payoff had it; brief had captions-only example so the LLM
# never applied it to scene main text).
# ---------------------------------------------------------------------------


def test_brief_exit_pair_applies_to_scene_main_content():
    """The exit-pair rule must explicitly cover scene main text/headlines,
    not just captions. Without this framing the LLM applies it captions-only
    and scene main text gets stuck on screen past its scene-slot (HOM-213
    canonical fixture symptom)."""
    brief = node_module._load_brief("p4_beat")

    # The rule's explicit generalisation: applies to headlines, attributions,
    # kickers, body copy — not just captions.
    assert "headlines" in brief.lower() or "headline" in brief, (
        "missing scene-main-content generalisation (HOM-213)"
    )
    # The symptom citation — keeps the why-do-this-rule-exist-at-all signal
    # in the brief so future edits don't quietly weaken it back to captions-only.
    assert "HOM-213" in brief or "stuck on screen" in brief.lower(), (
        "missing the HOM-213 symptom citation"
    )


def test_brief_exit_pair_lives_in_scene_iife_not_root():
    """The exit-pair MUST live in the scene's own IIFE timeline (the one
    registered on `window.__sceneTimelines["..."]`), not deferred to root-
    level transitions. Root transitions fade the scene CONTAINER; per-element
    visibility is scene-IIFE territory. Without this clarification the LLM
    sometimes punts on per-element exits, expecting root transitions to
    handle them — but root can't see scene-internal selectors."""
    brief = node_module._load_brief("p4_beat")

    # The clarification phrase must survive — it disambiguates which timeline
    # owns the exit-pair (scene IIFE, not root).
    assert "__sceneTimelines" in brief, (
        "missing scene-IIFE timeline reference"
    )
    # Explicit "not root" or "scene container" framing — proves the brief
    # distinguishes between scene-internal element fades and root-scope
    # scene-container fades.
    assert "scene container" in brief.lower() or "root-level transitions" in brief.lower(), (
        "missing scene-container vs scene-IIFE disambiguation"
    )


def test_brief_exit_pair_cites_canonical_fixture_payoff():
    """The brief should point at the canonical fixture's payoff scene as
    positive control. Concrete examples beat abstract rules — the LLM has
    a working sample to mirror. If a future edit removes the citation, the
    LLM loses the grounding example."""
    brief = node_module._load_brief("p4_beat")
    assert "payoff" in brief.lower(), (
        "missing canonical fixture's payoff scene as positive control"
    )


# ---------------------------------------------------------------------------
# AllBackendsExhausted — HOM-158 contract: LLMNode raises so pregel's
# RetryPolicy (graph.py) actually engages.
# ---------------------------------------------------------------------------


def test_all_backends_exhausted_raises(tmp_path):
    """HOM-158: p4_beat (via LLMNode base) re-raises on terminal failure
    instead of returning an `errors[]` delta. Required for `RetryPolicy` to
    fire — see `_llm.py` and `graph.py` notes.
    """
    import pytest
    from edit_episode_graph.backends._types import AllBackendsExhausted

    fragment = tmp_path / "hyperframes" / "compositions" / "hook.html"
    router = MagicMock()
    router.invoke.side_effect = AllBackendsExhausted(
        [{"backend": "claude", "success": False, "model": "claude-opus-4-7",
          "reason": "timeout", "wall_time_s": 300.0, "ts": "now"}],
    )

    with pytest.raises(AllBackendsExhausted):
        p4_beat_node(_state(tmp_path, str(fragment)), router=router)
    # The fragment was NOT created — pregel discards writes on raise; the
    # next attempt (if RetryPolicy fires) starts from an unchanged state.
    assert not fragment.exists()
