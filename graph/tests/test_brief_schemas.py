import pytest
from pydantic import ValidationError

from edit_episode_graph.brief.schemas import (
    BrandDefaults,
    BrandPalette,
    EpisodeIntent,
    ProfileConfig,
)


def test_canonical_profile_minimal_shape():
    p = ProfileConfig.model_validate(
        {
            "profile_id": "canonical",
            "human_label": "Canonical (regression)",
            "pacing": "skill_default",
            "structural_archetype": "skill_default",
            "rhythm_template": "skill_default",
            "captions": {"enabled": False},
            "animation_density": "skill_default",
            "music": {"enabled": False},
            "cta": {"enabled": False},
        }
    )
    assert p.output is None
    assert p.edit is None
    assert p.captions.enabled is False
    assert p.captions.mode is None
    assert p.music.enabled is False
    assert p.pacing == "skill_default"


def test_full_profile_shape():
    p = ProfileConfig.model_validate(
        {
            "profile_id": "talking-head-portrait",
            "human_label": "Talking head — portrait short",
            "output": {"width": 1080, "height": 1920, "fps": 60},
            "pacing": "tight_conversational",
            "structural_archetype": "hook_problem_solution_cta",
            "rhythm_template": "hook-build-PEAK-breathe-CTA",
            "captions": {"enabled": True, "mode": "karaoke", "safe_zone": "lower_third_avoid_face"},
            "animation_density": "medium",
            "music": {"enabled": True, "default_mix_db": -18},
            "cta": {"enabled": True, "placement": "final_scene"},
            "edit": {
                "remove": ["false_starts", "cross_range_semantic_duplicates"],
                "padding": {"head_ms": 50, "tail_ms": 80},
            },
        }
    )
    assert p.output.width == 1080 and p.output.fps == 60
    assert p.captions.mode == "karaoke"
    assert p.music.default_mix_db == -18
    assert p.edit.padding.head_ms == 50
    assert "cross_range_semantic_duplicates" in p.edit.remove


def test_profile_rejects_unknown_top_key():
    with pytest.raises(ValidationError):
        ProfileConfig.model_validate(
            {
                "profile_id": "x",
                "human_label": "x",
                "captions": {"enabled": False},
                "music": {"enabled": False},
                "cta": {"enabled": False},
                "typo_field": 1,
            }
        )


def test_brand_palette_and_defaults_shape():
    pal = BrandPalette.model_validate(
        {
            "colors": {"ink": "#0E0E0E", "lime": "#C8FF3D"},
            "typography": {"display": "Clash Display", "body": "Inter"},
            "contrast_pairs": [{"fg": "ink", "bg": "paper"}],
        }
    )
    assert pal.colors["lime"] == "#C8FF3D"
    assert pal.contrast_pairs[0].fg == "ink"

    d = BrandDefaults.model_validate(
        {
            "motion_language": {"easing_default": "power2.out"},
            "captions": {"style": "karaoke"},
            "cta": {"template": "cta_scene.html"},
            "grade": {"warmth": 0},
            "transitions": {"primary": "blur crossfade"},
        }
    )
    assert d.cta["template"] == "cta_scene.html"
    assert d.transitions["primary"] == "blur crossfade"


def test_empty_intent_is_all_optional():
    intent = EpisodeIntent.model_validate({})
    assert intent.profile_id is None
    assert intent.brand_id is None
    assert intent.must_cuts == []
    assert intent.grade_overrides == {}
