from edit_episode_graph.brief.loaders import (
    load_brand,
    load_intent,
    load_profile,
)
from edit_episode_graph.brief.schemas import EpisodeIntent

PROFILE_YAML = """\
profile_id: talking-head-portrait
human_label: "Talking head — portrait short"
output: {width: 1080, height: 1920, fps: 60}
pacing: tight_conversational
structural_archetype: hook_problem_solution_cta
rhythm_template: "hook-build-PEAK-breathe-CTA"
captions: {enabled: true, mode: karaoke, safe_zone: lower_third_avoid_face}
animation_density: medium
music: {enabled: true, default_mix_db: -18}
cta: {enabled: true, placement: final_scene}
edit:
  remove: [false_starts, cross_range_semantic_duplicates]
  padding: {head_ms: 50, tail_ms: 80}
"""

PALETTE_YAML = """\
colors: {ink: "#0E0E0E", lime: "#C8FF3D"}
typography: {display: "Clash Display", body: "Inter"}
contrast_pairs:
  - {fg: ink, bg: paper}
"""

DEFAULTS_YAML = """\
motion_language: {easing_default: "power2.out"}
captions: {style: karaoke}
cta: {template: cta_scene.html}
grade: {warmth: 0}
transitions: {primary: "blur crossfade"}
"""


def test_load_profile_from_dir(tmp_path):
    pdir = tmp_path / "talking-head-portrait"
    pdir.mkdir()
    (pdir / "profile.yaml").write_text(PROFILE_YAML, encoding="utf-8")
    p = load_profile(pdir)
    assert p.profile_id == "talking-head-portrait"
    assert p.output.height == 1920


def test_load_brand_bundles_palette_and_defaults(tmp_path):
    bdir = tmp_path / "anticodeguy"
    bdir.mkdir()
    (bdir / "palette.yaml").write_text(PALETTE_YAML, encoding="utf-8")
    (bdir / "defaults.yaml").write_text(DEFAULTS_YAML, encoding="utf-8")
    kit = load_brand(bdir)
    assert kit.brand_id == "anticodeguy"
    assert kit.palette.colors["lime"] == "#C8FF3D"
    assert kit.defaults.cta["template"] == "cta_scene.html"


def test_load_intent_missing_file_returns_empty(tmp_path):
    intent = load_intent(tmp_path / "nope.yaml")
    assert intent == EpisodeIntent()


def test_load_intent_empty_file_falls_through(tmp_path):
    f = tmp_path / "intent.yaml"
    f.write_text("", encoding="utf-8")
    assert load_intent(f) == EpisodeIntent()


def test_load_intent_with_overrides(tmp_path):
    f = tmp_path / "intent.yaml"
    f.write_text("profile_id: explainer\nmusic: {track_id: tutorial-clean-2}\n", encoding="utf-8")
    intent = load_intent(f)
    assert intent.profile_id == "explainer"
    assert intent.music.track_id == "tutorial-clean-2"
