"""Wave-1 acceptance (spec §16): palette edit invalidates the brief fingerprint
(→ p4_design_system cache miss); editing brand.md PROSE (a markdown layer,
fingerprinted per-node via canon_fingerprint, NOT part of brief.fingerprint)
leaves brief.fingerprint stable. Canonical-mode resolves with brand_id=None."""
from __future__ import annotations

from pathlib import Path

import pytest


def _seed(tmp_path: Path) -> None:
    prof = tmp_path / "profiles" / "talking-head-portrait"; prof.mkdir(parents=True)
    (prof / "profile.yaml").write_text(
        "profile_id: talking-head-portrait\nhuman_label: TH\n"
        "captions: {enabled: true}\nmusic: {enabled: true}\ncta: {enabled: true}\n", encoding="utf-8")
    (prof / "house-style.md").write_text(
        "## Pacing\nTight.\n## Structural archetype\nHook.\n"
        "## Rhythm template\nCut on beat.\n## Edit rules\nNo jump cuts.\n",
        encoding="utf-8")
    canon = tmp_path / "profiles" / "canonical"; canon.mkdir(parents=True)
    (canon / "profile.yaml").write_text(
        "profile_id: canonical\nhuman_label: C\n"
        "captions: {enabled: false}\nmusic: {enabled: false}\ncta: {enabled: false}\n", encoding="utf-8")
    brand = tmp_path / "brand" / "anticodeguy"; brand.mkdir(parents=True)
    (brand / "palette.yaml").write_text("colors: {bg: '#000000', fg: '#ffffff'}\n", encoding="utf-8")
    (brand / "defaults.yaml").write_text("motion_language: {}\ncaptions: {}\n", encoding="utf-8")
    (brand / "brand.md").write_text("## Voice\nCalm.\n## Visual identity\nLime.\n", encoding="utf-8")
    (tmp_path / "episodes" / "ep1").mkdir(parents=True)


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("HOMESTUDIO_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    return tmp_path


def _resolve(slug="ep1", overrides=None):
    from edit_episode_graph.nodes.resolve_episode_brief import resolve_episode_brief_node
    st = {"slug": slug}
    if overrides:
        st["brief_overrides"] = overrides
    return resolve_episode_brief_node(st)["brief"]


def test_palette_edit_changes_brief_fingerprint(repo):
    fp1 = _resolve()["fingerprint"]
    (repo / "brand" / "anticodeguy" / "palette.yaml").write_text(
        "colors: {bg: '#111111', fg: '#ffffff'}\n", encoding="utf-8")
    assert _resolve()["fingerprint"] != fp1


def test_brand_md_prose_edit_keeps_brief_fingerprint_stable(repo):
    fp1 = _resolve()["fingerprint"]
    (repo / "brand" / "anticodeguy" / "brand.md").write_text(
        "## Voice\nENERGETIC.\n## Visual identity\nLime.\n", encoding="utf-8")
    assert _resolve()["fingerprint"] == fp1  # markdown is per-node canon_fingerprint, not brief.fingerprint


def test_design_system_cache_key_misses_on_palette_change(repo):
    from edit_episode_graph.nodes.p4_design_system import _cache_key
    b1 = _resolve()
    st = {"slug": "ep1", "brief": b1, "edit": {"edl": {"ranges": [{"beat": "HOOK"}]}, "strategy": {}}}
    k1 = _cache_key(st)
    (repo / "brand" / "anticodeguy" / "palette.yaml").write_text(
        "colors: {bg: '#222222', fg: '#ffffff'}\n", encoding="utf-8")
    b2 = _resolve()
    k2 = _cache_key({**st, "brief": b2})
    assert k1 != k2


def test_canonical_mode_no_brand(repo):
    b = _resolve(overrides={"profile_id": "canonical"})
    assert b["brand_id"] is None
    assert b["profile_id"] == "canonical"
