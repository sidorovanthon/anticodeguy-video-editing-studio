"""HOM-127 smoke: post-assemble gate-cluster wiring + real-CLI invocations.

Three layers (cost order):

  1. Topology check (free, deterministic) — every spec §4.3 v4 node + the
     seven post-assemble gates are present in the compiled graph; the
     assemble → gate_lint → … → gate_captions_track → p4_persist_session
     chain is fully wired.

  2. Real gate invocations against the existing fully-assembled fixture
     episode (`2026-05-05-desktop-software-licensing-it-turns-out-is`).
     Each gate runs over `episodes/<slug>/hyperframes/index.html` as it
     would in a live run; we assert the gate produced a `gate_results`
     record (pass or fail). Failures are non-fatal here — the smoke is
     proving the subprocess + state shape are correct, not that this
     particular fixture passes every check.

  3. halt_llm_boundary surfaces post-assemble cluster failures with the
     specific gate name. We craft a synthetic state with a failed
     `gate:lint` record and assert the notice mentions the gate.

Cost: zero LLM calls. The end-to-end Opus run on a real episode is the
operator-driven Studio invocation referenced in the PR's Test plan
(per HOM-127 DoD: "End-to-end run on a real episode in LangGraph
Studio"). This smoke covers the wiring + gate subprocess shape that
underpins it.

Run from the worktree's graph directory:
    PYTHONPATH=$(pwd -W)/src .venv/Scripts/python smoke_hom127.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from edit_episode_graph.gates.captions_track import captions_track_gate_node
from edit_episode_graph.gates.design_adherence import design_adherence_gate_node
from edit_episode_graph.gates.lint import lint_gate_node
from edit_episode_graph.graph import build_graph_uncompiled
from edit_episode_graph.nodes.halt_llm_boundary import halt_llm_boundary_node


REPO_ROOT = Path(__file__).resolve().parent.parent
SLUG = "2026-05-05-desktop-software-licensing-it-turns-out-is"
# `episodes/` is gitignored; in a worktree the dir is empty. Fall back to
# the primary worktree's episodes/ path so the smoke can run against the
# real fixture from any worktree.
_PRIMARY_EPISODES = Path(r"C:/Users/sidor/repos/anticodeguy-video-editing-studio/episodes")
EPISODE = REPO_ROOT / "episodes" / SLUG
if not (EPISODE / "hyperframes" / "index.html").is_file():
    fallback = _PRIMARY_EPISODES / SLUG
    if (fallback / "hyperframes" / "index.html").is_file():
        EPISODE = fallback


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


def case_topology() -> int:
    print("\n=== Case 1: gate-cluster topology ===")
    g = build_graph_uncompiled().compile().get_graph()
    nodes = set(g.nodes.keys())
    missing_nodes = set(GATE_CLUSTER) - nodes
    if missing_nodes:
        print(f"SMOKE FAIL: cluster nodes missing: {sorted(missing_nodes)}", file=sys.stderr)
        return 1
    edges = {(e.source, e.target) for e in g.edges}
    missing_edges = EXPECTED_CLUSTER_EDGES - edges
    if missing_edges:
        print(f"SMOKE FAIL: cluster edges missing: {sorted(missing_edges)}", file=sys.stderr)
        return 1
    print(f"  ✓ all {len(GATE_CLUSTER)} cluster nodes present")
    print(f"  ✓ all {len(EXPECTED_CLUSTER_EDGES)} cluster edges wired")
    return 0


def case_real_gate_invocations() -> int:
    """Run the deterministic gates that don't need a browser/CLI subprocess.

    `lint`, `validate`, `inspect`, `animation_map`, `snapshot` shell out to
    the hyperframes CLI / node helpers — those are smoke-tested by their
    individual node smokes and are slow + Windows-fragile. Here we run the
    pure-Python gates (`design_adherence`, `captions_track`) plus `lint` to
    prove the subprocess plumbing reaches the CLI, against the live fixture.
    """
    print("\n=== Case 2: gate invocations against fixture ===")
    if not (EPISODE / "hyperframes" / "index.html").is_file():
        print(f"SMOKE SKIP: fixture missing — {EPISODE}/hyperframes/index.html")
        return 0

    state = {
        "slug": SLUG,
        "episode_dir": str(EPISODE),
        "compose": {
            "hyperframes_dir": str(EPISODE / "hyperframes"),
            "design": {
                # Empty palette / typography → design_adherence skips its
                # set-membership checks (the upstream gate:design_ok owns
                # DESIGN.md presence). We're proving the gate runs and
                # records, not validating this fixture against a palette.
                "palette": [],
                "typography": [],
                "design_md_path": str(EPISODE / "hyperframes" / "DESIGN.md"),
            },
            "plan": {"beats": []},
        },
    }

    # Pure-Python gates always run.
    for label, node in (
        ("gate:design_adherence", design_adherence_gate_node),
        ("gate:captions_track", captions_track_gate_node),
    ):
        out = node(dict(state))
        records = out.get("gate_results") or []
        if not records:
            print(f"SMOKE FAIL: {label} produced no gate_results", file=sys.stderr)
            return 1
        rec = records[0]
        print(
            f"  {label}: passed={rec.get('passed')} "
            f"violations={len(rec.get('violations') or [])}"
        )

    # CLI-backed gate. Best-effort — if `npx` / bundled CLI isn't reachable
    # the gate still records a violation and we treat that as a pass for
    # the smoke (the wiring is what matters).
    out = lint_gate_node(dict(state))
    records = out.get("gate_results") or []
    if not records:
        print("SMOKE FAIL: gate:lint produced no gate_results", file=sys.stderr)
        return 1
    rec = records[0]
    print(
        f"  gate:lint: passed={rec.get('passed')} "
        f"violations={len(rec.get('violations') or [])}"
    )
    return 0


def case_halt_notice_surfaces_cluster_failure() -> int:
    print("\n=== Case 3: halt_llm_boundary surfaces gate-cluster failures ===")
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
    if not notices:
        print("SMOKE FAIL: no notices emitted", file=sys.stderr)
        return 1
    notice = notices[0]
    print(f"  notice: {notice}")
    if "gate:lint FAILED" not in notice:
        print(
            "SMOKE FAIL: notice does not mention gate:lint failure",
            file=sys.stderr,
        )
        return 1
    print("  ✓ halt notice names the failing gate")
    return 0


def main() -> int:
    rc = case_topology()
    if rc:
        return rc
    rc = case_real_gate_invocations()
    if rc:
        return rc
    rc = case_halt_notice_surfaces_cluster_failure()
    if rc:
        return rc
    print("\nSMOKE OK: gate-cluster wiring + invocation + halt notice")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
