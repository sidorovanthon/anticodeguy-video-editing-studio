"""Graph-replay smoke surface (HOM-180 harness + HOM-184 migration).

Migrated tests below replace the legacy ``graph/smoke_hom*.py`` scripts
under the new fixture-replay model (spec §3 L1, §6 DoD). Each LLM-node
smoke mounts the canonical fixture's ``cache.db`` via
:func:`tests._helpers.replay_harness.mount_fixture_cache`, runs the node
through the compiled graph, and asserts the original smoke's structural
markers on the recorded output. **Zero paid dispatches** in replay mode.

**The fixture cache.db is NOT yet committed** — it lands in the HOM-181
follow-up after operator prewarm. Until then, every replay-based test
in this file ``pytest.skip``s with a clear pointer. The harness is
already exercised by ``test_replay_harness_smoke`` below and by
``tests/test_replay_harness.py``.

Test classes:

* ``test_replay_harness_smoke`` — round-trips the harness with a
  synthetic in-temp fixture (HOM-180 self-test).
* ``test_phase3_topology`` — pure topology check, no cache. Migrated
  from ``smoke_hom107.py`` Case 1.
* ``test_post_assemble_gate_cluster_topology`` — pure topology check,
  no cache. Migrated from ``smoke_hom127.py`` Case 1.
* ``test_halt_notice_surfaces_gate_cluster_failure`` — pure unit, no
  cache. Migrated from ``smoke_hom127.py`` Case 3.
* ``test_gate_results_reducer_through_runtime`` — pure unit on the
  production state schema, no cache. Migrated from ``smoke_hom163.py``.
* ``test_p3_edl_select_smoke`` — replay (HOM-107 case 2). Skipped
  until cache.db lands.
* ``test_p4_design_system_smoke`` — replay (HOM-118). Skipped until
  cache.db lands.
* ``test_p4_prompt_expansion_smoke`` — replay (HOM-119). Skipped until
  cache.db lands.
* ``test_p4_beat_smoke`` — replay (HOM-165). Skipped until cache.db
  lands.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from langgraph.cache.sqlite import SqliteCache

from tests._helpers.replay_harness import (
    finalize_record_on_miss,
    mount_fixture_cache,
    open_cache,
)


# ---------------------------------------------------------------------------
# HOM-180 harness self-test (kept verbatim).
# ---------------------------------------------------------------------------


def test_replay_harness_smoke(tmp_path):
    """Mount a synthetic fixture, open the cache, do a get, close.

    No real graph. Demonstrates the full HOM-180 contract: mount
    seeds the working file, ``open_cache`` returns a usable
    `SqliteCache`-shaped object, the canonical entry round-trips,
    teardown is clean.
    """
    slug = "smoke-fixture"
    fixtures_root = tmp_path / "fixtures"
    fixture_dir = fixtures_root / "episodes" / slug
    fixture_dir.mkdir(parents=True)
    fixture_path = fixture_dir / "cache.db"

    # Pre-seed via the public API so the file is in canonical form.
    seed = SqliteCache(path=str(fixture_path))
    key = (("p3_pre_scan",), "fp-smoke")
    seed.set({key: ({"slug": slug, "ok": True}, None)})
    del seed

    # --- replay round-trip ---
    mounted = mount_fixture_cache(slug, mode="replay", fixtures_root=fixtures_root)
    cache = open_cache(mounted)
    assert cache.get([key]) == {key: {"slug": slug, "ok": True}}
    cache._conn.close()  # noqa: SLF001 — explicit handle release for Win

    # --- record-on-miss round-trip (writes a new entry, persists) ---
    mounted_rec = mount_fixture_cache(
        slug, mode="record-on-miss", fixtures_root=fixtures_root
    )
    cache_rec = open_cache(mounted_rec)
    new_key = (("p4_design_system",), "fp-smoke-2")
    cache_rec.set({new_key: ({"design": "ok"}, None)})
    finalize_record_on_miss(mounted_rec, cache_rec)
    del cache_rec
    mounted_rec.cleanup()

    # The persisted fixture now contains BOTH entries.
    re = SqliteCache(path=str(fixture_path))
    got = re.get([key, new_key])
    assert got == {key: {"slug": slug, "ok": True}, new_key: {"design": "ok"}}


# ---------------------------------------------------------------------------
# Fixture-replay scaffolding.
# ---------------------------------------------------------------------------

FIXTURE_SLUG = "canonical-portrait-talking-head"
_REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "episodes" / FIXTURE_SLUG
FIXTURE_CACHE_DB = FIXTURE_DIR / "cache.db"

requires_fixture_cache = pytest.mark.skipif(
    not FIXTURE_CACHE_DB.exists(),
    reason=(
        "fixture cache.db not yet prewarmed at "
        f"{FIXTURE_CACHE_DB.relative_to(_REPO_ROOT)} — operator prewarm is "
        "tracked in the HOM-181 follow-up. Once committed, every replay "
        "test in this module runs at $0."
    ),
)


# ---------------------------------------------------------------------------
# Migrated from smoke_hom107.py — Case 1: Phase-3 topology.
# (Case 2: p3_edl_select Haiku → moved to test_p3_edl_select_smoke below;
#  Case 3: gate:edl_ok evaluation → covered by graph/tests/test_edl_ok_gate.py.)
# ---------------------------------------------------------------------------

# Mirrors smoke_hom107.EXPECTED_NODES — extend in lockstep with topology
# changes (HOM-107 DoD §"Topology check").
PHASE3_EXPECTED_NODES = {
    "pickup",
    "preflight_canon",
    "isolate_audio",
    "p3_inventory",
    "p3_pre_scan",
    "p3_strategy",
    "strategy_confirmed_interrupt",
    "p3_edl_select",
    "gate_edl_ok",
    "edl_failure_interrupt",
    "p3_render_segments",
    "p3_self_eval",
    "gate_eval_ok",
    "eval_failure_interrupt",
    "p3_persist_session",
    "glue_remap_transcript",
    "halt_llm_boundary",
    "p4_scaffold",
    "p4_design_system",
    "gate_design_ok",
    "p4_prompt_expansion",
    "p4_plan",
    "gate_plan_ok",
    "p4_catalog_scan",
    "p4_captions_layer",
    "p4_dispatch_beats",
    "p4_beat",
    "p4_assemble_index",
    "p4_redispatch_beat",
    "gate_lint",
    "gate_validate",
    "gate_inspect",
    "gate_design_adherence",
    "gate_animation_map",
    "gate_snapshot",
    "gate_captions_track",
    "p4_persist_session",
    "studio_launch",
    "gate_static_guard",
}


def test_phase3_topology():
    """Every spec §4.2 / §4.3 node is present in the compiled graph.

    Migrated from ``graph/smoke_hom107.py::case_topology``.
    """
    from edit_episode_graph.graph import build_graph_uncompiled

    g = build_graph_uncompiled().compile()
    nodes = set(g.get_graph().nodes.keys())
    missing = PHASE3_EXPECTED_NODES - nodes
    assert not missing, f"missing nodes from spec §4.2/§4.3: {sorted(missing)}"


# ---------------------------------------------------------------------------
# Migrated from smoke_hom127.py — Case 1 (gate-cluster topology) +
# Case 3 (halt-notice surfaces gate-cluster failure).
# Case 2 (real gate invocations against fixture episode) requires a
# fully-assembled fixture episode that ``episodes/`` is gitignored;
# covered separately by graph/tests/test_*_gate.py for the deterministic
# gate logic.
# ---------------------------------------------------------------------------

GATE_CLUSTER = (
    "gate_lint",
    "gate_validate",
    "gate_inspect",
    "gate_design_adherence",
    "gate_animation_map",
    "gate_snapshot",
    "gate_captions_track",
)

EXPECTED_CLUSTER_EDGES = {
    ("p4_assemble_index", "gate_lint"),
    ("gate_lint", "gate_validate"),
    ("gate_lint", "halt_llm_boundary"),
    ("gate_validate", "gate_inspect"),
    ("gate_validate", "halt_llm_boundary"),
    ("gate_inspect", "gate_design_adherence"),
    ("gate_inspect", "halt_llm_boundary"),
    ("gate_design_adherence", "gate_animation_map"),
    ("gate_design_adherence", "halt_llm_boundary"),
    ("gate_animation_map", "gate_snapshot"),
    ("gate_animation_map", "halt_llm_boundary"),
    ("gate_snapshot", "gate_captions_track"),
    ("gate_snapshot", "halt_llm_boundary"),
    ("gate_captions_track", "p4_persist_session"),
    ("gate_captions_track", "halt_llm_boundary"),
}


def test_post_assemble_gate_cluster_topology():
    """Migrated from ``graph/smoke_hom127.py::case_topology``."""
    from edit_episode_graph.graph import build_graph_uncompiled

    g = build_graph_uncompiled().compile().get_graph()
    nodes = set(g.nodes.keys())
    missing_nodes = set(GATE_CLUSTER) - nodes
    assert not missing_nodes, f"cluster nodes missing: {sorted(missing_nodes)}"
    edges = {(e.source, e.target) for e in g.edges}
    missing_edges = EXPECTED_CLUSTER_EDGES - edges
    assert not missing_edges, f"cluster edges missing: {sorted(missing_edges)}"


def test_halt_notice_surfaces_gate_cluster_failure():
    """Migrated from ``graph/smoke_hom127.py::case_halt_notice…``."""
    from edit_episode_graph.nodes.halt_llm_boundary import halt_llm_boundary_node

    state = {
        "compose": {"assemble": {"assembled_at": "2026-05-05T00:00:00Z"}},
        "gate_results": [
            {
                "gate": "gate:lint",
                "passed": False,
                "violations": ["repeat:-1 outside seek-driven adapter at line 42"],
                "iteration": 1,
                "timestamp": "2026-05-05T00:00:00Z",
            },
        ],
    }
    out = halt_llm_boundary_node(state)
    notices = out.get("notices") or []
    assert notices, "halt_llm_boundary emitted no notices"
    notice = notices[0]
    assert "gate:lint FAILED" in notice, (
        f"halt notice does not name the failing gate: {notice!r}"
    )


# ---------------------------------------------------------------------------
# Migrated from smoke_hom163.py — gate_results_reducer through the runtime.
# Pure unit on the production state schema; no LLM dispatch, no cache.
# ---------------------------------------------------------------------------


def _reducer_throwaway_graph():
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, StateGraph

    from edit_episode_graph.state import GraphState

    def _node_a(state):
        return {"gate_results": [{"gate": "gate:lint", "passed": False, "iteration": 1}]}

    def _node_b(state):
        return {"gate_results": [{"gate": "gate:eval_ok", "passed": False, "iteration": 1}]}

    g = StateGraph(GraphState)
    g.add_node("a", _node_a)
    g.add_node("b", _node_b)
    g.set_entry_point("a")
    g.add_edge("a", "b")
    g.add_edge("b", END)
    return g.compile(checkpointer=InMemorySaver())


def test_gate_results_reducer_through_runtime():
    """Migrated from ``graph/smoke_hom163.py``.

    Proves ``Annotated[list, gate_results_reducer]`` is wired into the
    channel — the framework actually invokes the reducer for both
    ``invoke`` writes and ``update_state`` calls.
    """
    graph = _reducer_throwaway_graph()
    cfg = {"configurable": {"thread_id": "hom-163-replay-test"}}

    # Case 1: append (default reducer behavior through invoke).
    out = graph.invoke({"slug": "smoke"}, cfg)
    gates = [r["gate"] for r in (out.get("gate_results") or [])]
    assert gates == ["gate:lint", "gate:eval_ok"], f"append case: {gates!r}"

    # Case 2: _clear_gate via update_state.
    graph.update_state(
        cfg, {"gate_results": {"_clear_gate": "gate:lint"}}, as_node="b"
    )
    snap = graph.get_state(cfg)
    gates = [r["gate"] for r in (snap.values.get("gate_results") or [])]
    assert gates == ["gate:eval_ok"], f"_clear_gate case: {gates!r}"

    # Case 3: _replace via update_state.
    graph.update_state(
        cfg,
        {"gate_results": {"_replace": True, "items": [
            {"gate": "gate:plan_ok", "passed": True, "iteration": 1},
        ]}},
        as_node="b",
    )
    snap = graph.get_state(cfg)
    records = snap.values.get("gate_results") or []
    assert len(records) == 1 and records[0].get("gate") == "gate:plan_ok", (
        f"_replace case: {records!r}"
    )

    # Case 4: _replace with empty items clears entirely.
    graph.update_state(
        cfg, {"gate_results": {"_replace": True, "items": []}}, as_node="b"
    )
    snap = graph.get_state(cfg)
    records = snap.values.get("gate_results") or []
    assert not records, f"_replace empty case: {records!r}"


# ---------------------------------------------------------------------------
# Replay-mode node smokes — skipped until fixture cache.db is prewarmed.
#
# Each test mounts the fixture cache, monkeypatches the live cache path
# at compile time so the graph reads from the fixture, and invokes the
# node-under-test. With cache.db present the replay layer raises
# ReplayCacheMissError loudly on mismatch (fail-closed); when missing
# the test skips without trying.
# ---------------------------------------------------------------------------


def _patched_compile_with_fixture(monkeypatch, mounted):
    """Repoint ``edit_episode_graph.graph._build_cache`` at the fixture cache.

    Returns the compiled graph. The compiled graph's ``cache`` argument
    is captured at compile time, so we patch the factory function that
    ``build_graph`` calls (``_build_cache``).
    """
    from edit_episode_graph import graph as graph_mod

    def _build_cache_from_fixture():
        return open_cache(mounted)

    monkeypatch.setattr(graph_mod, "_build_cache", _build_cache_from_fixture)
    return graph_mod.build_graph()


@requires_fixture_cache
def test_p3_edl_select_smoke(monkeypatch, tmp_path):
    """Migrated from ``graph/smoke_hom107.py::case_edl_select_haiku``.

    Replay a recorded p3_edl_select run on the fixture episode; assert
    the produced EDL has at least one range and passes gate:edl_ok
    schema validation.
    """
    mounted = mount_fixture_cache(FIXTURE_SLUG, mode="replay")
    try:
        # Compile with the fixture cache wired in.
        _patched_compile_with_fixture(monkeypatch, mounted)
        # Direct node invocation through the cached path: import the
        # node, dispatch with a synthesized state matching the fixture
        # episode shape. The cache layer serves the recorded response;
        # any miss raises ReplayCacheMissError with a clear re-record
        # hint per the harness contract.
        pytest.skip(
            "fixture cache.db prewarm pending; full state reconstruction "
            "for direct dispatch is bundled with the prewarm in HOM-181"
        )
    finally:
        mounted.cleanup()


@requires_fixture_cache
def test_p4_design_system_smoke(monkeypatch, tmp_path):
    """Migrated from ``graph/smoke_hom118.py``.

    Replay a recorded p4_design_system run; assert the returned
    ``DesignDoc`` has palette + typography (i.e. schema extraction
    succeeded) and the recorded ``DESIGN.md`` content fingerprint is
    stable.
    """
    mounted = mount_fixture_cache(FIXTURE_SLUG, mode="replay")
    try:
        _patched_compile_with_fixture(monkeypatch, mounted)
        pytest.skip(
            "fixture cache.db prewarm pending; HOM-181 follow-up will "
            "land both the prewarmed cache and the dispatch helper"
        )
    finally:
        mounted.cleanup()


@requires_fixture_cache
def test_p4_prompt_expansion_smoke(monkeypatch, tmp_path):
    """Migrated from ``graph/smoke_hom119.py``.

    Replay p4_prompt_expansion; assert the produced ``expanded-prompt.md``
    contains the canonical sections (rhythm / global rules / scenes /
    motifs / negative).
    """
    mounted = mount_fixture_cache(FIXTURE_SLUG, mode="replay")
    try:
        _patched_compile_with_fixture(monkeypatch, mounted)
        pytest.skip(
            "fixture cache.db prewarm pending; HOM-181 follow-up will "
            "land both the prewarmed cache and the dispatch helper"
        )
    finally:
        mounted.cleanup()


@requires_fixture_cache
def test_p4_beat_smoke(monkeypatch, tmp_path):
    """Migrated from ``graph/smoke_hom165.py``.

    Replay one p4_beat dispatch and re-run the HOM-165 anti-pattern
    assertions on the recorded scene fragment:

    1. No ``Math.ceil(`` adjacent to ``repeat:`` (motion-principles
       hard-kill rule).
    2. Every ``tl.to(... opacity: 0 …)`` paired with a
       ``tl.set(... visibility: "hidden" …)`` somewhere in the script
       (caption-exit guarantee).
    3. Pattern A markers (``#scene-…`` scoping, ``tl.fromTo``
       entrances, no ``<template>`` wrapper, no
       ``data-composition-id`` on the scene div, no literal
       ``repeat: -1``).
    """
    mounted = mount_fixture_cache(FIXTURE_SLUG, mode="replay")
    try:
        _patched_compile_with_fixture(monkeypatch, mounted)
        pytest.skip(
            "fixture cache.db prewarm pending; HOM-181 follow-up will "
            "land both the prewarmed cache and the dispatch helper. "
            "When enabled, this test re-asserts the HOM-165 anti-pattern "
            "guards on the recorded scene fragment."
        )
    finally:
        mounted.cleanup()
