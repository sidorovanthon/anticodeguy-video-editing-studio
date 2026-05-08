"""HOM-160: rehydrate_skip_phase3 + p3_strategy persistence + routing.

Regression guard for the M5/§17 acceptance: a fresh-thread re-run on a
slug whose ``final.mp4`` exists must restore ``state.edit.strategy`` from
disk so Phase 4 cache keys match the values they had on the original
thread. Without rehydration, ``strategy_fingerprint(strategy)`` in
``p4_design_system._cache_key`` (and downstream) is the empty-dict hash on
fresh threads vs the real-strategy hash on the original — every Phase 4
LLM node misses cache.

These tests assert the structural invariants. Cross-thread cache-hit
proof is left to a manual smoke (cheap once the cache is warm) because the
production cache.db has poison from HOM-157 that confounds end-to-end
checks; that is an orthogonal ticket.
"""

from __future__ import annotations

import json
from pathlib import Path

from edit_episode_graph._caching import strategy_fingerprint
from edit_episode_graph.nodes._routing import route_after_preflight
from edit_episode_graph.nodes.rehydrate_skip_phase3 import rehydrate_skip_phase3_node


def _make_episode(tmp_path: Path, *, with_final: bool, with_strategy_json: bool) -> Path:
    ep = tmp_path / "ep"
    edit = ep / "edit"
    edit.mkdir(parents=True)
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
    return ep


def test_route_after_preflight_skips_to_rehydrate_when_final_exists(tmp_path):
    ep = _make_episode(tmp_path, with_final=True, with_strategy_json=False)
    state = {"slug": "x", "episode_dir": str(ep)}
    assert route_after_preflight(state) == "rehydrate_skip_phase3"


def test_route_after_preflight_runs_phase3_when_no_final(tmp_path):
    ep = _make_episode(tmp_path, with_final=False, with_strategy_json=False)
    (ep / "edit" / "takes_packed.md").write_text("hi", encoding="utf-8")
    state = {"slug": "x", "episode_dir": str(ep)}
    assert route_after_preflight(state) == "p3_pre_scan"


def test_rehydrate_loads_strategy_from_disk(tmp_path):
    ep = _make_episode(tmp_path, with_final=True, with_strategy_json=True)
    state = {"slug": "x", "episode_dir": str(ep)}
    update = rehydrate_skip_phase3_node(state)
    assert update["edit"]["strategy"]["shape"] == "hook → pivot → CTA"
    assert update["edit"]["strategy"]["source_path"].endswith("strategy.json")
    assert any("restored strategy" in n for n in update["notices"])


def test_rehydrate_emits_notice_when_strategy_json_missing(tmp_path):
    ep = _make_episode(tmp_path, with_final=True, with_strategy_json=False)
    state = {"slug": "x", "episode_dir": str(ep)}
    update = rehydrate_skip_phase3_node(state)
    assert "edit" not in update or "strategy" not in (update.get("edit") or {})
    assert any("no strategy.json" in n for n in update["notices"])


def test_rehydrate_no_episode_dir_is_no_op():
    assert rehydrate_skip_phase3_node({"slug": "x"}) == {}


def test_rehydrate_corrupted_json_emits_notice(tmp_path):
    ep = _make_episode(tmp_path, with_final=True, with_strategy_json=False)
    (ep / "edit" / "strategy.json").write_text("not json", encoding="utf-8")
    state = {"slug": "x", "episode_dir": str(ep)}
    update = rehydrate_skip_phase3_node(state)
    assert any("unreadable" in n for n in update["notices"])
    assert "strategy" not in (update.get("edit") or {})


def test_rehydrated_strategy_fingerprint_matches_original(tmp_path):
    """Round-trip: persist a strategy via the same logic p3_strategy uses, then
    rehydrate it; the fingerprint that drives downstream cache keys must be
    identical. If this drifts, Phase 4 cache keys diverge across threads —
    the exact symptom HOM-160 fixes.
    """
    original = {
        "shape": "x", "takes": ["[001-005]"], "grade": "warm",
        "pacing": "tight", "length_estimate_s": 60.0,
        "source_path": "/tmp/takes_packed.md",  # excluded from fp
        # HOM-160: in production, strategy_confirmed_interrupt sets these
        # AFTER p3_strategy persists strategy.json but BEFORE p4_design_system
        # computes its cache key. The original-thread fingerprint thus
        # includes them; the rehydrated-thread fingerprint must match — so
        # both must be in `strategy_fingerprint`'s exclusion set.
        "approved": True,
        "approval_payload": {"approved": True},
    }
    # Mirror p3_strategy's persist filter.
    persisted = {k: v for k, v in original.items()
                 if k not in {"skipped", "skip_reason", "approved", "approval_payload"}}
    ep = tmp_path / "ep"
    (ep / "edit").mkdir(parents=True)
    (ep / "edit" / "strategy.json").write_text(json.dumps(persisted), encoding="utf-8")
    (ep / "edit" / "final.mp4").write_bytes(b"x")

    update = rehydrate_skip_phase3_node({"slug": "x", "episode_dir": str(ep)})
    rehydrated = update["edit"]["strategy"]
    assert strategy_fingerprint(rehydrated) == strategy_fingerprint(original)


def test_p3_strategy_persists_strategy_json_after_success(tmp_path, monkeypatch):
    """p3_strategy_node writes <edit>/strategy.json when the LLM call succeeds."""
    from edit_episode_graph.nodes import p3_strategy as mod

    ep = tmp_path / "ep"
    edit = ep / "edit"
    edit.mkdir(parents=True)
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

    state = {"slug": "x", "episode_dir": str(ep)}
    update = mod.p3_strategy_node(state)
    assert captured.get("called") is True
    out = edit / "strategy.json"
    assert out.exists()
    persisted = json.loads(out.read_text(encoding="utf-8"))
    # Persisted snapshot excludes transient/operator-decision keys.
    for forbidden in ("skipped", "skip_reason", "approved", "approval_payload"):
        assert forbidden not in persisted
    assert persisted["shape"] == "S"
    # Returned update keeps source_path on the in-memory dict for downstream
    # nodes that key off the strategy origin.
    assert update["edit"]["strategy"]["source_path"].endswith("takes_packed.md")


def test_p3_strategy_does_not_persist_on_skip(tmp_path):
    from edit_episode_graph.nodes import p3_strategy as mod

    ep = tmp_path / "ep"
    (ep / "edit").mkdir(parents=True)
    # No takes_packed.md — node short-circuits with skipped.
    update = mod.p3_strategy_node({"slug": "x", "episode_dir": str(ep)})
    assert update["edit"]["strategy"].get("skipped") is True
    assert not (ep / "edit" / "strategy.json").exists()
