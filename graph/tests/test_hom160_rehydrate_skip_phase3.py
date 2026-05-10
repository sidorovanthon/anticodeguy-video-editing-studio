"""HOM-160: rehydrate_skip_phase3 + p3_strategy persistence + routing.

Regression guard for the M5/§17 acceptance: a fresh-thread re-run on a
slug whose ``final.mp4`` exists must restore ``state.edit.strategy`` from
disk so Phase 4 cache keys match the values they had on the original
thread.

HOM-223 update: tests pin ``HOMESTUDIO_PROJECT_ROOT`` so
``EpisodePaths(slug)`` resolves under tmp_path. State carries `slug` only;
identity-only writes mean `strategy.source_path` is no longer echoed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from edit_episode_graph._caching import strategy_fingerprint
from edit_episode_graph.nodes._routing import route_after_preflight
from edit_episode_graph.nodes.rehydrate_skip_phase3 import rehydrate_skip_phase3_node


@pytest.fixture
def project_root_episode(tmp_path, monkeypatch):
    slug = "x"
    episode_dir = tmp_path / "episodes" / slug
    episode_dir.mkdir(parents=True)
    monkeypatch.setenv("HOMESTUDIO_PROJECT_ROOT", str(tmp_path))
    return slug, episode_dir


def _make_episode(episode_dir: Path, *, with_final: bool, with_strategy_json: bool) -> Path:
    edit = episode_dir / "edit"
    edit.mkdir(parents=True, exist_ok=True)
    if with_final:
        (edit / "final.mp4").write_bytes(b"fake")
    if with_strategy_json:
        (edit / "strategy.json").write_text(
            json.dumps({
                "shape": "hook → pivot → CTA",
                "takes": ["[001-005]"],
                "grade": "warm",
                "pacing": "tight",
                "length_estimate_s": 60.0,
            }, indent=2),
            encoding="utf-8",
        )
    return episode_dir


def test_route_after_preflight_skips_to_rehydrate_when_final_exists(project_root_episode):
    slug, episode_dir = project_root_episode
    _make_episode(episode_dir, with_final=True, with_strategy_json=False)
    state = {"slug": slug, "episode_dir": str(episode_dir)}
    assert route_after_preflight(state) == "rehydrate_skip_phase3"


def test_route_after_preflight_runs_phase3_when_no_final(project_root_episode):
    slug, episode_dir = project_root_episode
    _make_episode(episode_dir, with_final=False, with_strategy_json=False)
    (episode_dir / "edit" / "takes_packed.md").write_text("hi", encoding="utf-8")
    state = {"slug": slug, "episode_dir": str(episode_dir)}
    assert route_after_preflight(state) == "p3_pre_scan"


def test_rehydrate_loads_strategy_from_disk(project_root_episode):
    slug, episode_dir = project_root_episode
    _make_episode(episode_dir, with_final=True, with_strategy_json=True)
    state = {"slug": slug, "episode_dir": str(episode_dir)}
    update = rehydrate_skip_phase3_node(state)
    assert update["edit"]["strategy"]["shape"] == "hook → pivot → CTA"
    # HOM-223: identity-only state — `source_path` no longer echoed.
    assert "source_path" not in update["edit"]["strategy"]
    assert any("restored strategy" in n for n in update["notices"])


def test_rehydrate_emits_notice_when_strategy_json_missing(project_root_episode):
    slug, episode_dir = project_root_episode
    _make_episode(episode_dir, with_final=True, with_strategy_json=False)
    state = {"slug": slug, "episode_dir": str(episode_dir)}
    update = rehydrate_skip_phase3_node(state)
    assert "edit" not in update or "strategy" not in (update.get("edit") or {})
    assert any("no strategy.json" in n for n in update["notices"])


def test_rehydrate_no_slug_is_no_op():
    assert rehydrate_skip_phase3_node({}) == {}


def test_rehydrate_corrupted_json_emits_notice(project_root_episode):
    slug, episode_dir = project_root_episode
    _make_episode(episode_dir, with_final=True, with_strategy_json=False)
    (episode_dir / "edit" / "strategy.json").write_text("not json", encoding="utf-8")
    state = {"slug": slug, "episode_dir": str(episode_dir)}
    update = rehydrate_skip_phase3_node(state)
    assert any("unreadable" in n for n in update["notices"])
    assert "strategy" not in (update.get("edit") or {})


def test_rehydrated_strategy_fingerprint_matches_original(project_root_episode):
    """Round-trip: persist a strategy via the same logic p3_strategy uses, then
    rehydrate it; the fingerprint that drives downstream cache keys must be
    identical.
    """
    slug, episode_dir = project_root_episode
    original = {
        "shape": "x", "takes": ["[001-005]"], "grade": "warm",
        "pacing": "tight", "length_estimate_s": 60.0,
        "source_path": "/tmp/takes_packed.md",
        "approved": True,
        "approval_payload": {"approved": True},
    }
    persisted = {k: v for k, v in original.items()
                 if k not in {"skipped", "skip_reason", "approved", "approval_payload"}}
    edit = episode_dir / "edit"
    edit.mkdir(parents=True, exist_ok=True)
    (edit / "strategy.json").write_text(json.dumps(persisted), encoding="utf-8")
    (edit / "final.mp4").write_bytes(b"x")

    update = rehydrate_skip_phase3_node({"slug": slug, "episode_dir": str(episode_dir)})
    rehydrated = update["edit"]["strategy"]
    assert strategy_fingerprint(rehydrated) == strategy_fingerprint(original)


def test_p3_strategy_persists_strategy_json_after_success(project_root_episode, monkeypatch):
    """p3_strategy_node writes <edit>/strategy.json when the LLM call succeeds."""
    from edit_episode_graph.nodes import p3_strategy as mod

    slug, episode_dir = project_root_episode
    edit = episode_dir / "edit"
    edit.mkdir(parents=True, exist_ok=True)
    (edit / "takes_packed.md").write_text("body", encoding="utf-8")

    captured: dict = {}

    def fake_build():
        class FakeNode:
            def __call__(self, state, *, router=None):
                captured["called"] = True
                return {
                    "edit": {"strategy": {
                        "shape": "S", "takes": ["[a-b]"], "grade": "G",
                        "pacing": "P", "length_estimate_s": 30.0,
                    }},
                    "llm_runs": [],
                }
        return FakeNode()

    monkeypatch.setattr(mod, "_build_node", fake_build)

    state = {"slug": slug, "episode_dir": str(episode_dir)}
    update = mod.p3_strategy_node(state)
    assert captured.get("called") is True
    out = edit / "strategy.json"
    assert out.exists()
    persisted = json.loads(out.read_text(encoding="utf-8"))
    for forbidden in ("skipped", "skip_reason", "approved", "approval_payload"):
        assert forbidden not in persisted
    assert persisted["shape"] == "S"
    # HOM-223: identity-only state — `source_path` no longer echoed.
    assert "source_path" not in update["edit"]["strategy"]


def test_p3_strategy_does_not_persist_on_skip(project_root_episode):
    from edit_episode_graph.nodes import p3_strategy as mod

    slug, episode_dir = project_root_episode
    (episode_dir / "edit").mkdir(parents=True, exist_ok=True)
    update = mod.p3_strategy_node({"slug": slug, "episode_dir": str(episode_dir)})
    assert update["edit"]["strategy"].get("skipped") is True
    assert not (episode_dir / "edit" / "strategy.json").exists()
