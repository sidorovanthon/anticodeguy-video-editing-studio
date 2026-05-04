"""HOM-121 smoke: real-CLI invocation of p4_catalog_scan + assembly logic.

Two layers, in order of cost:

  1. Topology check (free, deterministic) — assert p4_catalog_scan and
     p4_assemble_index are present in the compiled graph and wired into
     the Phase 4 chain (matches tests/test_p4_topology.py — duplicating
     here so the smoke is self-contained for ad-hoc verification).

  2. Real-CLI `npx hyperframes catalog --json` invocation — proves
     subprocess shape, stdout JSON parsing, and CatalogReport extraction.
     Cost: zero (no LLM call). Requires `npx`/Node available; skips with
     a clear message otherwise.

  3. Assembly round-trip on a tmp scaffolded index.html with a fake beat
     fragment — exercises `assemble_html` through the node entry point
     (no subprocess). Catches the body-injection regression that would
     break the future fan-out wiring.

Run from the worktree's graph directory:
    .venv/Scripts/python smoke_hom121.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from edit_episode_graph.graph import build_graph_uncompiled
from edit_episode_graph.nodes.p4_assemble_index import p4_assemble_index_node
from edit_episode_graph.nodes.p4_catalog_scan import p4_catalog_scan_node


SCAFFOLD_HTML = """\
<!doctype html>
<html><head><meta name="viewport" content="width=1920, height=1080" /></head>
<body>
  <div data-composition-id="root" data-width="1920" data-height="1080" data-duration="20"></div>
</body></html>
"""


def case_topology() -> int:
    print("\n=== Case 1: topology check (offline) ===")
    g = build_graph_uncompiled().compile().get_graph()
    nodes = set(g.nodes.keys())
    edges = {(e.source, e.target) for e in g.edges}
    expected_nodes = {"p4_catalog_scan", "p4_assemble_index"}
    missing_n = expected_nodes - nodes
    if missing_n:
        print(f"SMOKE FAIL: missing nodes {sorted(missing_n)}", file=sys.stderr)
        return 1
    expected_edges = {
        ("gate_plan_ok", "p4_catalog_scan"),
        ("p4_catalog_scan", "p4_assemble_index"),
        ("p4_assemble_index", "halt_llm_boundary"),
    }
    missing_e = expected_edges - edges
    if missing_e:
        print(f"SMOKE FAIL: missing edges {sorted(missing_e)}", file=sys.stderr)
        return 1
    print("  ✓ p4_catalog_scan + p4_assemble_index present and wired into chain")
    return 0


def case_real_catalog_scan() -> int:
    print("\n=== Case 2: real-CLI `npx hyperframes catalog --json` ===")
    if shutil.which("npx") is None and shutil.which("npx.cmd") is None:
        print("SMOKE SKIP: npx not on PATH")
        return 0
    with tempfile.TemporaryDirectory() as td:
        episode_dir = Path(td)
        (episode_dir / "hyperframes").mkdir()
        update = p4_catalog_scan_node({"episode_dir": str(episode_dir)})
    if update.get("errors"):
        print(f"SMOKE FAIL: catalog scan errored: {update['errors'][0]}", file=sys.stderr)
        return 1
    catalog = update["compose"]["catalog"]
    n_b = len(catalog.get("blocks") or [])
    n_c = len(catalog.get("components") or [])
    if n_b + n_c == 0:
        print(
            "SMOKE FAIL: catalog returned 0 items — registry empty or CLI broken",
            file=sys.stderr,
        )
        return 1
    print(f"  ✓ catalog returned {n_b} block(s), {n_c} component(s)")
    if n_b:
        sample = catalog["blocks"][0]
        print(f"    sample block: name={sample.get('name')!r} title={sample.get('title')!r}")
    return 0


def case_assemble_round_trip() -> int:
    print("\n=== Case 3: assemble_index round-trip on tmp scaffold ===")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "index.html"
        root.write_text(SCAFFOLD_HTML, encoding="utf-8")
        beat = Path(td) / "hook.html"
        beat.write_text('<div data-composition-id="hook">HOOK</div>', encoding="utf-8")
        state = {
            "compose": {
                "index_html_path": str(root),
                "beats": [{"name": "HOOK", "html_path": str(beat)}],
            },
        }
        update = p4_assemble_index_node(state)
        if update.get("errors"):
            print(f"SMOKE FAIL: assembly errored: {update['errors'][0]}", file=sys.stderr)
            return 1
        on_disk = root.read_text(encoding="utf-8")
        if 'data-composition-id="hook"' not in on_disk:
            print("SMOKE FAIL: beat not injected into index.html", file=sys.stderr)
            return 1
        if "p4_assemble_index: end" not in on_disk:
            print("SMOKE FAIL: injection sentinel missing", file=sys.stderr)
            return 1
    print("  ✓ assembly injected beat fragment + sentinel before </body>")
    return 0


def main() -> int:
    rc = 0
    rc = case_topology() or rc
    rc = case_real_catalog_scan() or rc
    rc = case_assemble_round_trip() or rc
    if rc == 0:
        print("\n✓ smoke_hom121 PASS")
    else:
        print("\n✗ smoke_hom121 FAIL", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
