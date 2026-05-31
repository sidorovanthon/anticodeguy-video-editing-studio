"""Loads the REAL committed profiles/ + brand/ skeleton and asserts shape.

Resolution PRECEDENCE (CLI>intent>profile>brand>canon) + brief.resolved.yaml
serialization is HOM-166's `resolve_episode_brief` node — this test proves the
committed skeleton is loadable, shape-stable, and has no broken asset refs.
"""
from pathlib import Path

from edit_episode_graph._paths import repo_root
from edit_episode_graph.brief.loaders import load_brand, load_intent, load_profile

PROFILES = repo_root() / "profiles"
BRAND = repo_root() / "brand"


def test_canonical_profile_committed():
    p = load_profile(PROFILES / "canonical")
    assert p.profile_id == "canonical"
    assert p.captions.enabled is False
    assert p.music.enabled is False
    assert p.cta.enabled is False
    assert p.output is None


def test_talking_head_profile_committed():
    p = load_profile(PROFILES / "talking-head-portrait")
    assert p.profile_id == "talking-head-portrait"
    assert (p.output.width, p.output.height, p.output.fps) == (1080, 1920, 60)
    assert p.captions.mode == "karaoke"
    assert p.music.default_mix_db == -18
    assert "cross_range_semantic_duplicates" in p.edit.remove
    assert (p.edit.padding.head_ms, p.edit.padding.tail_ms) == (50, 80)


def test_talking_head_house_style_anchors_present():
    text = (PROFILES / "talking-head-portrait" / "house-style.md").read_text(encoding="utf-8")
    for anchor in ("## Pacing", "## Structural archetype", "## Rhythm template", "## Edit rules"):
        assert anchor in text


def test_anticodeguy_brand_committed():
    kit = load_brand(BRAND / "anticodeguy")
    assert kit.brand_id == "anticodeguy"
    assert kit.palette.colors["lime"] == "#C8FF3D"
    assert kit.palette.typography["display"] == "Clash Display"
    assert kit.defaults.transitions["primary"] == "blur crossfade"


def test_anticodeguy_brand_md_anchors_present():
    text = (BRAND / "anticodeguy" / "brand.md").read_text(encoding="utf-8")
    for anchor in ("## Voice", "## Visual identity", "## Layer composition"):
        assert anchor in text


def test_cta_template_ref_resolves_on_disk():
    kit = load_brand(BRAND / "anticodeguy")
    template_name = kit.defaults.cta["template"]
    assert (BRAND / "anticodeguy" / "templates" / template_name).is_file()


def test_brand_assets_exist():
    assets = BRAND / "anticodeguy" / "assets"
    assert (assets / "logo.svg").is_file()
    assert (assets / "symbol-lime.svg").is_file()


def test_music_dir_scaffolded_empty():
    music = BRAND / "anticodeguy" / "music"
    assert music.is_dir()
    # No track files yet — populated by §15.9. Only the keep-file is present.
    assert [p.name for p in music.iterdir()] == [".gitkeep"]


def test_four_layer_shape_snapshot():
    profile = load_profile(PROFILES / "talking-head-portrait")
    brand = load_brand(BRAND / "anticodeguy")
    intent = load_intent(Path("does-not-exist.yaml"))  # empty intent layer

    composed = {
        "profile_id": profile.profile_id,
        "brand_id": brand.brand_id,
        "captions_enabled": profile.captions.enabled,
        "music_enabled": profile.music.enabled,
        "palette_colors": sorted(brand.palette.colors.keys()),
        "intent_has_overrides": intent != type(intent)(),
    }
    assert composed == {
        "profile_id": "talking-head-portrait",
        "brand_id": "anticodeguy",
        "captions_enabled": True,
        "music_enabled": True,
        "palette_colors": ["ink", "lime", "paper", "slate"],
        "intent_has_overrides": False,
    }
