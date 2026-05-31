"""Unit tests for resolve_episode_brief (HOM-166, spec §6)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from edit_episode_graph.nodes.resolve_episode_brief import (
    BriefResolutionError,
    resolve_episode_brief_node,
    _resolve_selection,
)


def _seed_repo(tmp_path: Path) -> None:
    """Minimal profiles/ + brand/ tree under an HOMESTUDIO_REPO_ROOT override."""
    prof = tmp_path / "profiles" / "talking-head-portrait"
    prof.mkdir(parents=True)
    (prof / "profile.yaml").write_text(
        "profile_id: talking-head-portrait\n"
        "human_label: TH\n"
        "captions: {enabled: true}\n"
        "music: {enabled: true}\n"
        "cta: {enabled: true}\n",
        encoding="utf-8",
    )
    canon = tmp_path / "profiles" / "canonical"
    canon.mkdir(parents=True)
    (canon / "profile.yaml").write_text(
        "profile_id: canonical\nhuman_label: Canon\n"
        "captions: {enabled: false}\nmusic: {enabled: false}\ncta: {enabled: false}\n",
        encoding="utf-8",
    )
    brand = tmp_path / "brand" / "anticodeguy"
    brand.mkdir(parents=True)
    (brand / "palette.yaml").write_text("colors: {bg: '#000000', fg: '#ffffff'}\n", encoding="utf-8")
    (brand / "defaults.yaml").write_text("motion_language: {}\ncaptions: {}\n", encoding="utf-8")


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    _seed_repo(tmp_path)
    monkeypatch.setenv("HOMESTUDIO_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    (tmp_path / "episodes" / "ep1").mkdir(parents=True)
    return tmp_path


def test_default_selection(repo):
    pid, bid = _resolve_selection({"slug": "ep1"})
    assert pid == "talking-head-portrait"
    assert bid == "anticodeguy"


def test_intent_overrides_default(repo):
    (repo / "episodes" / "ep1" / "intent.yaml").write_text(
        "profile_id: canonical\n", encoding="utf-8"
    )
    pid, bid = _resolve_selection({"slug": "ep1"})
    assert pid == "canonical"
    assert bid is None  # canonical forces brand off


def test_state_override_beats_intent(repo):
    (repo / "episodes" / "ep1" / "intent.yaml").write_text(
        "profile_id: canonical\n", encoding="utf-8"
    )
    pid, _ = _resolve_selection({"slug": "ep1", "brief_overrides": {"profile_id": "talking-head-portrait"}})
    assert pid == "talking-head-portrait"


def test_node_writes_resolved_yaml_and_state(repo):
    out = resolve_episode_brief_node({"slug": "ep1"})
    brief = out["brief"]
    assert brief["profile_id"] == "talking-head-portrait"
    assert brief["brand_id"] == "anticodeguy"
    assert brief["music"] is None
    assert len(brief["fingerprint"]) == 64
    resolved_path = Path(brief["resolved_brief_path"])
    assert resolved_path.exists()
    doc = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))
    assert doc["profile_id"] == "talking-head-portrait"
    assert doc["fingerprint"] == brief["fingerprint"]


def test_fingerprint_changes_on_palette_edit(repo):
    fp1 = resolve_episode_brief_node({"slug": "ep1"})["brief"]["fingerprint"]
    (repo / "brand" / "anticodeguy" / "palette.yaml").write_text(
        "colors: {bg: '#111111', fg: '#ffffff'}\n", encoding="utf-8"
    )
    fp2 = resolve_episode_brief_node({"slug": "ep1"})["brief"]["fingerprint"]
    assert fp1 != fp2


def test_canonical_resolves_without_brand(repo):
    (repo / "episodes" / "ep1" / "intent.yaml").write_text("profile_id: canonical\n", encoding="utf-8")
    brief = resolve_episode_brief_node({"slug": "ep1"})["brief"]
    assert brief["brand_id"] is None


def test_missing_profile_dir_raises(repo):
    with pytest.raises(BriefResolutionError):
        resolve_episode_brief_node({"slug": "ep1", "brief_overrides": {"profile_id": "nonexistent"}})


def test_narrative_context_passthrough(repo):
    (repo / "episodes" / "ep1" / "intent.yaml").write_text(
        "narrative_context: |\n  Episode about X.\n", encoding="utf-8"
    )
    brief = resolve_episode_brief_node({"slug": "ep1"})["brief"]
    assert "Episode about X." in brief["narrative_context"]
