from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from edit_episode_graph.backends._types import InvokeResult
from edit_episode_graph.nodes import p4_prompt_expansion as node_module
from edit_episode_graph.nodes.p4_prompt_expansion import p4_prompt_expansion_node
from edit_episode_graph.schemas.p4_prompt_expansion import ExpandedPrompt


def _good_payload(path: str) -> dict:
    # HOM-233 (state-first artifacts, Step B of HOM-230): the full
    # expanded-prompt body is returned in the structured output, not just its
    # path. The schema requires it (`min_length=1`); downstream the body lives
    # in `compose.expansion.expanded_prompt` and `p4_materialize_disk_node`
    # is the single writer.
    return {
        "expanded_prompt_path": path,
        "expanded_prompt": (
            "# Expanded prompt\n\n"
            "## Scene 1 — HOOK\nTight typographic close-up; stat enters.\n\n"
            "## Scene 2 — PAYOFF\nWide reveal with hairline rules.\n"
        ),
    }


def _seed_episode(tmp_path, monkeypatch, *, design=True):
    """HOM-224 helper: pin HOMESTUDIO_PROJECT_ROOT, seed slug-derived files."""
    slug = "demo"
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    hf_dir = tmp_path / "episodes" / slug / "hyperframes"
    transcripts_dir = tmp_path / "episodes" / slug / "edit" / "transcripts"
    hf_dir.mkdir(parents=True, exist_ok=True)
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    (transcripts_dir / "final.json").write_text("{}", encoding="utf-8")
    if design:
        (hf_dir / "DESIGN.md").write_text("# DESIGN", encoding="utf-8")
    return slug


def _state_with_inputs(tmp_path) -> dict:
    return {
        "slug": "demo",
        "compose": {
            "style_request": "Editorial calm — Stripe-press energy.",
            # HOM-265 (Step E partial of HOM-230): consumer gates check
            # state-body presence, not disk. Seed the DESIGN.md body so
            # the node body passes its precondition and dispatches.
            "design": {"design_md": "# DESIGN.md fixture body\n"},
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
    # Empty path must be rejected (min_length=1) — spread the otherwise-valid
    # payload so this asserts the path constraint specifically, not the
    # (separately required) body field.
    with pytest.raises(ValidationError):
        ExpandedPrompt.model_validate(
            {**_good_payload("/x/.hyperframes/expanded-prompt.md"), "expanded_prompt_path": ""},
        )


def test_expanded_prompt_schema_rejects_unknown_field():
    with pytest.raises(ValidationError):
        ExpandedPrompt.model_validate(
            {**_good_payload("/x/.hyperframes/expanded-prompt.md"), "extra": "no"},
        )


def test_skips_when_slug_missing():
    """HOM-224: identity is `slug`, not `episode_dir`."""
    update = p4_prompt_expansion_node({}, router=MagicMock())
    assert update["compose"]["expansion"]["skipped"] is True
    assert "slug" in update["compose"]["expansion"]["skip_reason"]


def test_skips_when_design_md_missing(tmp_path, monkeypatch):
    # HOM-265 (Step E partial of HOM-230): gate switched to state-body
    # presence. When `compose.design.design_md` is absent from state, the
    # node MUST skip without dispatching — `p4_design_system` is the
    # upstream producer of that body and must have run first.
    slug = _seed_episode(tmp_path, monkeypatch, design=False)
    state = {
        "slug": slug,
        "compose": {},  # NO design body
        "edit": {"edl": {"ranges": [{"beat": "HOOK"}]}},
    }
    update = p4_prompt_expansion_node(state, router=MagicMock())
    assert update["compose"]["expansion"]["skipped"] is True
    assert "DESIGN.md" in update["compose"]["expansion"]["skip_reason"]


def test_skips_when_edl_empty(tmp_path, monkeypatch):
    _seed_episode(tmp_path, monkeypatch)
    state = _state_with_inputs(tmp_path)
    state["edit"]["edl"] = {"ranges": []}
    update = p4_prompt_expansion_node(state, router=MagicMock())
    assert update["compose"]["expansion"]["skipped"] is True


def test_runs_with_tools_and_no_state_path_mirror(tmp_path, monkeypatch):
    slug = _seed_episode(tmp_path, monkeypatch)
    expanded = tmp_path / "episodes" / slug / "hyperframes" / ".hyperframes" / "expanded-prompt.md"
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

    # HOM-224: structured output still surfaces the path in `compose.expansion`
    # (the LLM still emits it per the schema), but the top-level mirror
    # `compose.expanded_prompt_path` is no longer written — downstream
    # consumers derive via `EpisodePaths(slug).expanded_prompt_path`.
    assert update["compose"]["expansion"]["expanded_prompt_path"] == str(expanded)
    assert "expanded_prompt_path" not in update["compose"]
    # HOM-239 (state-first artifacts, Step D2 of HOM-230): the node no longer
    # dual-writes the file or mkdirs `.hyperframes/` — the expanded-prompt body
    # is surfaced in state and `p4_materialize_disk_node` is the single writer.
    assert update["compose"]["expansion"]["expanded_prompt"] == payload["expanded_prompt"]

    req, task = router.invoke.call_args.args[:2]
    kwargs = router.invoke.call_args.kwargs
    assert req.tier == "expensive"
    assert req.needs_tools is True
    assert req.backends == ["claude"]
    # HOM-239: `Write` dropped from `allowed_tools` — the sub-agent reads
    # canon but no longer writes to disk (the orchestrator owns the write).
    assert kwargs["allowed_tools"] == ["Read"]
    # Brief renders inputs the agent needs for the expansion.
    assert "HOOK" in task and "PAYOFF" in task
    assert "DESIGN.md" in task
    assert "expanded-prompt.md" in task
    assert "Editorial calm" in task


def test_brief_inlines_transcript_body_after_hom279():
    """HOM-279: brief inlines `transcript_json_body` so the sub-agent
    no longer calls `Read` on the transcript file.
    """
    brief = node_module._load_brief("p4_prompt_expansion")
    assert "{{ transcript_json_body }}" in brief, (
        "brief did not inline the transcript body context variable — "
        "HOM-279 consumer migration regression"
    )
    assert "HOM-279" in brief, "missing HOM-279 cite for the inlined-body rule"
    assert "do NOT call `Read`" in brief or "Do NOT call `Read`" in brief, (
        "brief missing the do-NOT-Read-transcript imperative"
    )


def test_transcript_body_helper_prefers_final_then_raw(tmp_path, monkeypatch):
    """HOM-279: `_transcript_body` resolves
    state.transcripts.bodies.final first, then raw, then "".
    """
    final_only = {"transcripts": {"bodies": {"final": "FINAL"}}}
    assert node_module._transcript_body(final_only) == "FINAL"
    raw_only = {"transcripts": {"bodies": {"raw": "RAW"}}}
    assert node_module._transcript_body(raw_only) == "RAW"
    both = {"transcripts": {"bodies": {"raw": "RAW", "final": "FINAL"}}}
    assert node_module._transcript_body(both) == "FINAL"
    empty = {"transcripts": {"bodies": {}}}
    assert node_module._transcript_body(empty) == ""
    no_transcripts = {}
    assert node_module._transcript_body(no_transcripts) == ""


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


def test_design_md_path_resolves_via_slug(tmp_path, monkeypatch):
    """HOM-224: the design.md path is resolved via `EpisodePaths(slug).design_md_path`
    regardless of whether `compose.design_md_path` was ever echoed into state.
    The previous fallback-to-nested-design path is moot post-HOM-224.
    """
    slug = _seed_episode(tmp_path, monkeypatch)
    expanded = tmp_path / "episodes" / slug / "hyperframes" / ".hyperframes" / "expanded-prompt.md"
    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text="...",
            structured=ExpandedPrompt.model_validate(_good_payload(str(expanded))),
            tokens_in=10, tokens_out=10, wall_time_s=1.0,
            model_used="claude-opus-4-7", backend_used="claude", tool_calls=[],
        ),
        [{"backend": "claude", "success": True, "model": "claude-opus-4-7",
          "tokens_in": 10, "tokens_out": 10, "wall_time_s": 1.0, "ts": "now"}],
    )
    state = _state_with_inputs(tmp_path)
    update = p4_prompt_expansion_node(state, router=router)
    assert update["compose"]["expansion"]["expanded_prompt_path"] == str(expanded)
    task = router.invoke.call_args.args[1]
    assert "DESIGN.md" in task
