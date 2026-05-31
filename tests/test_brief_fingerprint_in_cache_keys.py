"""brief.fingerprint must change every creative node's cache key (HOM-166)."""
from __future__ import annotations

import importlib

import pytest

CREATIVE_NODES = [
    "p3_pre_scan", "p3_self_eval", "p3_strategy", "p3_edl_select",
    "p4_design_system", "p4_prompt_expansion", "p4_plan", "p4_beat",
    "p4_captions_layer",
]


@pytest.mark.parametrize("module", CREATIVE_NODES)
def test_brief_fingerprint_changes_cache_key(module, monkeypatch, tmp_path):
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("HOMESTUDIO_REPO_ROOT", str(tmp_path))
    mod = importlib.import_module(f"edit_episode_graph.nodes.{module}")
    base = {"slug": "ep1", "edit": {}, "compose": {}, "transcripts": {}, "scenes": {}}
    k1 = mod._cache_key({**base, "brief": {"fingerprint": "AAA"}})
    k2 = mod._cache_key({**base, "brief": {"fingerprint": "BBB"}})
    assert k1 != k2, f"{module} cache key ignores brief.fingerprint"
