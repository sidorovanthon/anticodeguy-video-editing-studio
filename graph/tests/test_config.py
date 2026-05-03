from pathlib import Path

from edit_episode_graph.config import load_config


def test_loads_yaml(tmp_path):
    cfg_text = """
backend_preference: ["claude", "codex"]
concurrency: {claude: 2, codex: 2, gemini: 3}
defaults: {timeout_s: 120}
node_overrides:
  p3_pre_scan: {tier: cheap, backend_preference: [claude], timeout_s: 90}
  "p4_beat_*": {tier: smart, backend_preference: [claude]}
"""
    p = tmp_path / "c.yaml"
    p.write_text(cfg_text, encoding="utf-8")
    cfg = load_config(p)
    assert cfg.backend_preference == ["claude", "codex"]
    assert cfg.concurrency == {"claude": 2, "codex": 2, "gemini": 3}


def test_node_resolve_explicit():
    from edit_episode_graph.config import RouterConfig
    cfg = RouterConfig(
        backend_preference=["claude"],
        concurrency={"claude": 2},
        defaults={"timeout_s": 100},
        node_overrides={"p3_pre_scan": {"tier": "cheap", "backend_preference": ["codex"], "timeout_s": 30}},
    )
    n = cfg.resolve_node("p3_pre_scan")
    assert n.tier == "cheap"
    assert n.backend_preference == ["codex"]
    assert n.timeout_s == 30


def test_node_resolve_glob_match():
    from edit_episode_graph.config import RouterConfig
    cfg = RouterConfig(
        backend_preference=["claude"],
        concurrency={},
        defaults={"timeout_s": 100},
        node_overrides={"p4_beat_*": {"tier": "smart", "backend_preference": ["claude"]}},
    )
    n = cfg.resolve_node("p4_beat_one")
    assert n.tier == "smart"


def test_node_resolve_falls_back_to_defaults():
    from edit_episode_graph.config import RouterConfig
    cfg = RouterConfig(
        backend_preference=["claude", "codex"],
        concurrency={},
        defaults={"timeout_s": 99},
        node_overrides={},
    )
    n = cfg.resolve_node("anything")
    assert n.tier == "cheap"
    assert n.backend_preference == ["claude", "codex"]
    assert n.timeout_s == 99
    assert n.model is None


def test_node_resolve_model_override():
    from edit_episode_graph.config import RouterConfig
    cfg = RouterConfig(
        backend_preference=["claude"], concurrency={}, defaults={"timeout_s": 60},
        node_overrides={"p3_pre_scan": {"model": "claude-haiku-4-5-20251001"}},
    )
    assert cfg.resolve_node("p3_pre_scan").model == "claude-haiku-4-5-20251001"


def test_node_resolve_p3_strategy_smart_override():
    from edit_episode_graph.config import load_default_config
    load_default_config.cache_clear()
    try:
        n = load_default_config().resolve_node("p3_strategy")
        assert n.tier == "smart"
        assert n.backend_preference == ["claude"]
        assert n.timeout_s == 120
    finally:
        load_default_config.cache_clear()
