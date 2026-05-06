from pathlib import Path

from langgraph.graph import END

from edit_episode_graph.nodes._routing import (
    route_after_inventory,
    route_after_pre_scan,
    route_after_preflight,
    route_after_strategy,
    route_after_strategy_confirmed,
)


def test_routes_to_pre_scan_when_takes_packed_exists(tmp_path):
    edit = tmp_path / "edit"
    edit.mkdir()
    (edit / "takes_packed.md").write_text("# t\n", encoding="utf-8")
    state = {"episode_dir": str(tmp_path)}
    assert route_after_preflight(state) == "p3_pre_scan"


def test_routes_to_glue_when_final_exists(tmp_path):
    edit = tmp_path / "edit"
    edit.mkdir()
    (edit / "final.mp4").write_bytes(b"x")
    (edit / "takes_packed.md").write_text("# t\n", encoding="utf-8")
    state = {"episode_dir": str(tmp_path)}
    assert route_after_preflight(state) == "glue_remap_transcript"


def test_routes_to_inventory_when_neither_exists(tmp_path):
    state = {"episode_dir": str(tmp_path)}
    assert route_after_preflight(state) == "p3_inventory"


def test_routes_to_end_after_inventory_error():
    state = {"errors": [{"node": "p3_inventory", "message": "boom", "timestamp": "now"}]}
    assert route_after_inventory(state) == END


def test_routes_to_pre_scan_after_inventory_success():
    assert route_after_inventory({}) == "p3_pre_scan"


def test_pre_scan_router_ignores_historical_errors():
    """HOM-158: p3_pre_scan is an LLM node and raises on terminal failure;
    pregel never commits an LLM-origin entry to `state["errors"]`. So an
    `errors` entry on the thread is by definition stale (deterministic-origin
    or pre-HOM-158 state) — routing must NOT END on it.
    """
    state = {"errors": [{"node": "p3_pre_scan", "message": "boom", "timestamp": "old"}]}
    assert route_after_pre_scan(state) == "p3_strategy"


def test_routes_to_strategy_after_pre_scan_success():
    assert route_after_pre_scan({}) == "p3_strategy"


def test_strategy_router_ignores_historical_errors():
    """HOM-158: same as `test_pre_scan_router_ignores_historical_errors` —
    p3_strategy is an LLM node, so any errors entry is historical.
    """
    state = {"errors": [{"node": "p3_strategy", "message": "boom", "timestamp": "old"}]}
    assert route_after_strategy(state) == "strategy_confirmed_interrupt"


def test_routes_to_strategy_confirmed_after_strategy_success():
    """HR 11 — strategy approval comes between p3_strategy and p3_edl_select."""
    assert route_after_strategy({}) == "strategy_confirmed_interrupt"


def test_routes_to_edl_select_when_strategy_approved():
    state = {"edit": {"strategy": {"approved": True}}}
    assert route_after_strategy_confirmed(state) == "p3_edl_select"


def test_routes_to_strategy_when_revision_pending():
    """Revision intent — loop back to p3_strategy; the brief reads revisions."""
    state = {
        "edit": {"strategy": {"shape": "x"}},
        "strategy_revisions": ["Target loudness = -14 LUFS"],
    }
    assert route_after_strategy_confirmed(state) == "p3_strategy"


def test_routes_to_halt_when_revision_cap_exceeded():
    state = {
        "edit": {"strategy": {"shape": "x"}},
        "strategy_revisions": ["a", "b", "c"],
    }
    assert route_after_strategy_confirmed(state) == "halt_llm_boundary"


def test_strategy_confirmed_router_ignores_historical_errors():
    """HOM-158: strategy_confirmed_interrupt is an interrupt node — never writes
    state["errors"]; any entry there is historical. Defensive fallback (no
    approval, no revisions) re-runs strategy.
    """
    state = {"errors": [{"node": "x", "message": "boom", "timestamp": "old"}]}
    assert route_after_strategy_confirmed(state) == "p3_strategy"


def test_routes_to_end_when_strategy_skipped():
    state = {"edit": {"strategy": {"skipped": True, "skip_reason": "missing input"}}}
    assert route_after_strategy_confirmed(state) == END


def test_initial_entry_no_revisions_routes_to_strategy():
    """Edge: empty state (no approved, no revisions yet) → loop to strategy.

    This branch is the defensive fallback — in practice the interrupt() raise
    suspends the graph and resume always comes with either approval or a
    revision payload. Still, exercise the path so future refactors don't
    accidentally route initial entries to END.
    """
    assert route_after_strategy_confirmed({}) == "p3_strategy"
