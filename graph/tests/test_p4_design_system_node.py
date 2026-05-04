from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from edit_episode_graph.backends._types import InvokeResult
from edit_episode_graph.nodes import p4_design_system as node_module
from edit_episode_graph.nodes.p4_design_system import p4_design_system_node
from edit_episode_graph.schemas.p4_design_system import DesignDoc


def _good_design_payload(design_md_path: str) -> dict:
    return {
        "style_name": "Swiss Pulse",
        "palette": [
            {"role": "background", "hex": "#0a0a0a"},
            {"role": "foreground", "hex": "#f0f0f0"},
            {"role": "accent",     "hex": "#0066FF"},
        ],
        "typography": [
            {"role": "headline", "family": "Helvetica Neue", "weight": 700, "size": "5rem"},
            {"role": "body",     "family": "Inter",          "weight": 400, "size": "1rem"},
        ],
        "refs": [
            {"label": "Müller-Brockmann", "description": "Grid-locked stats."},
            {"label": "Stripe Press",     "description": "Editorial restraint."},
        ],
        "alternatives": [
            {"name": "Folk Frequency", "rejected_because": "Too festive for analytical tone."},
        ],
        "anti_patterns": [
            "No gradient text.",
            "No cyan-on-dark.",
            "No equal-weight centered layouts.",
        ],
        "beat_visual_mapping": [
            {"beat": "HOOK",    "treatment": "Tight typographic close-up."},
            {"beat": "PROBLEM", "treatment": "Stat at 7rem dominates."},
            {"beat": "PAYOFF",  "treatment": "Wide reveal with hairline rules."},
        ],
        "design_md_path": design_md_path,
    }


def test_design_doc_schema_rejects_bad_hex():
    with pytest.raises(ValidationError):
        DesignDoc.model_validate(
            {**_good_design_payload("/x/DESIGN.md"),
             "palette": [
                 {"role": "background", "hex": "not-a-hex"},
                 {"role": "foreground", "hex": "#fff"},
             ]}
        )


def test_design_doc_schema_enforces_substance_bounds():
    base = _good_design_payload("/x/DESIGN.md")
    DesignDoc.model_validate(base)
    with pytest.raises(ValidationError):
        DesignDoc.model_validate({**base, "refs": base["refs"][:1]})
    with pytest.raises(ValidationError):
        DesignDoc.model_validate({**base, "alternatives": []})
    with pytest.raises(ValidationError):
        DesignDoc.model_validate({**base, "anti_patterns": ["just one", "two"]})
    with pytest.raises(ValidationError):
        DesignDoc.model_validate({**base, "beat_visual_mapping": []})


def test_design_doc_schema_rejects_unknown_field():
    base = _good_design_payload("/x/DESIGN.md")
    with pytest.raises(ValidationError):
        DesignDoc.model_validate({**base, "subtitles": "no thanks"})


def test_skips_when_episode_dir_missing():
    update = p4_design_system_node({}, router=MagicMock())
    assert update["compose"]["design"]["skipped"] is True


def test_skips_when_edl_empty(tmp_path):
    state = {
        "slug": "demo",
        "episode_dir": str(tmp_path),
        "edit": {"edl": {"ranges": []}},
    }
    update = p4_design_system_node(state, router=MagicMock())
    assert update["compose"]["design"]["skipped"] is True


def test_runs_with_tools_and_writes_design_md_path(tmp_path):
    design_md = tmp_path / "hyperframes" / "DESIGN.md"
    payload = _good_design_payload(str(design_md))

    router = MagicMock()
    router.invoke.return_value = (
        InvokeResult(
            raw_text="...",
            structured=DesignDoc.model_validate(payload),
            tokens_in=500,
            tokens_out=300,
            wall_time_s=12.0,
            model_used="claude-opus-4-7",
            backend_used="claude",
            tool_calls=[],
        ),
        [{"backend": "claude", "success": True, "model": "claude-opus-4-7",
          "tokens_in": 500, "tokens_out": 300, "wall_time_s": 12.0, "ts": "now"}],
    )

    state = {
        "slug": "demo",
        "episode_dir": str(tmp_path),
        "edit": {
            "edl": {
                "ranges": [
                    {"source": "raw", "start": 0.0, "end": 1.0,
                     "beat": "HOOK", "quote": "x", "reason": "y"},
                    {"source": "raw", "start": 1.0, "end": 2.0,
                     "beat": "PAYOFF", "quote": "x", "reason": "y"},
                ],
            },
        },
    }
    update = p4_design_system_node(state, router=router)

    assert update["compose"]["design"]["style_name"] == "Swiss Pulse"
    assert update["compose"]["design_md_path"] == str(design_md)
    assert design_md.parent.is_dir(), "node must mkdir the destination dir"

    req, task = router.invoke.call_args.args[:2]
    kwargs = router.invoke.call_args.kwargs
    assert req.tier == "smart"
    assert req.needs_tools is True
    assert req.backends == ["claude"]
    assert kwargs["allowed_tools"] == ["Read", "Write"]
    assert "HOOK" in task and "PAYOFF" in task


def test_brief_references_canon_paths_without_embedding():
    brief = node_module._load_brief("p4_design_system")
    assert "~/.agents/skills/hyperframes/SKILL.md" in brief
    assert '§"Step 1: Design system"' in brief
    assert "visual-styles.md" in brief
    assert "design-picker.md" in brief
    assert "Return ONLY JSON" in brief
    # Spot-check the brief did NOT lift the canonical "build what was asked"
    # paragraph or the canonical HARD-GATE wording verbatim — those are
    # canon's, not ours.
    assert "Build what was asked" not in brief
