"""Hot-path caching: load_default_config + brief template reads.

On a fan-out of N beats, both used to fire N times per node call. Verify
they now hit disk once.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from edit_episode_graph import config as config_module
from edit_episode_graph.config import load_default_config
from edit_episode_graph.nodes._llm import _load_brief


def test_load_default_config_caches_after_first_call():
    load_default_config.cache_clear()
    with patch.object(config_module, "load_config", wraps=config_module.load_config) as spy:
        for _ in range(20):
            load_default_config()
        # Path may or may not exist in test env; we only care that the inner
        # parse function runs at most once across 20 calls.
        assert spy.call_count <= 1
    assert load_default_config.cache_info().hits >= 19
    load_default_config.cache_clear()


def test_load_brief_caches_per_name(tmp_path, monkeypatch):
    _load_brief.cache_clear()
    fake_dir = tmp_path / "briefs"
    fake_dir.mkdir()
    (fake_dir / "demo.j2").write_text("hello {{ slug }}", encoding="utf-8")

    from edit_episode_graph.nodes import _llm as llm_module
    monkeypatch.setattr(llm_module, "_BRIEFS_DIR", fake_dir)

    real_read = Path.read_text
    reads: list[Path] = []
    def spy_read(self, *a, **kw):
        reads.append(self)
        return real_read(self, *a, **kw)
    monkeypatch.setattr(Path, "read_text", spy_read)

    for _ in range(10):
        assert _load_brief("demo") == "hello {{ slug }}"
    assert sum(1 for p in reads if p.name == "demo.j2") == 1
    _load_brief.cache_clear()


def test_p3_pre_scan_does_not_reread_brief_per_call(tmp_path, monkeypatch):
    """End-to-end: invoking p3_pre_scan_node 5x should not re-read the brief 5x."""
    from edit_episode_graph.nodes import p3_pre_scan as node_module
    from edit_episode_graph.nodes._llm import _load_brief
    _load_brief.cache_clear()

    state = {"slug": "demo", "episode_dir": str(tmp_path)}  # no takes_packed.md → skip path
    for _ in range(5):
        node_module.p3_pre_scan_node(state)
    # Skip path doesn't touch the brief; ensure the cache helper is still functional.
    # Now exercise the build path that DOES need the brief:
    edit_dir = tmp_path / "edit"
    edit_dir.mkdir()
    (edit_dir / "takes_packed.md").write_text("hi", encoding="utf-8")

    real_read = Path.read_text
    brief_reads = 0

    def counting_read(self, *a, **kw):
        nonlocal brief_reads
        if self.name == "p3_pre_scan.j2":
            brief_reads += 1
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", counting_read)

    # Trigger _build_node multiple times via direct call (router=MagicMock so no LLM).
    from unittest.mock import MagicMock
    from edit_episode_graph.backends._types import AllBackendsExhausted
    router = MagicMock()
    router.invoke.side_effect = AllBackendsExhausted([])
    for _ in range(5):
        node_module.p3_pre_scan_node(state, router=router)

    assert brief_reads <= 1, f"expected ≤1 brief read across 5 calls, got {brief_reads}"
    _load_brief.cache_clear()
