"""HOM-141 smoke: run the post-assemble Quality Check cluster gates against
a real assembled episode and print a structured report.

This is the cluster-level smoke for HOM-124 / HOM-141 — proves that the
gates we've shipped work end-to-end on a real HF project, and documents
which fail / pass / annotate-as-artifact.

Target episode (per HOM-141 ticket):
    episodes/2026-05-05-desktop-software-licensing-it-turns-out-is/hyperframes/

Of the 7 gates planned for the HOM-124 cluster:

    1. gate:lint              (HOM-138, shipped)
    2. gate:validate          (HOM-138, shipped)
    3. gate:inspect           (HOM-139, shipped)
    4. gate:design_adherence  (HOM-139, shipped)
    5. gate:snapshot          (HOM-141, this PR)
    6. gate:captions_track    (HOM-141, this PR)
    7. gate:animation_map     (HOM-140, NOT YET SHIPPED — flagged as PENDING)

Run from the worktree's graph directory:
    .venv/Scripts/python smoke_hom141.py
or:
    .venv/Scripts/python smoke_hom141.py --episode <path/to/hyperframes>

Skip with SMOKE_SKIP=1. Exits 0 if every available gate passed (or
passed-with-annotation); exits 1 if any gate emitted real violations.
The exit code is informational — gate failures on the live episode are
expected to be either (a) genuine upstream bugs worth filing or (b)
documented limitations; the PR Test plan annotates each one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from edit_episode_graph.gates.animation_map import animation_map_gate_node
from edit_episode_graph.gates.captions_track import captions_track_gate_node
from edit_episode_graph.gates.design_adherence import design_adherence_gate_node
from edit_episode_graph.gates.inspect import inspect_gate_node
from edit_episode_graph.gates.lint import lint_gate_node
from edit_episode_graph.gates.snapshot import snapshot_gate_node
from edit_episode_graph.gates.validate import validate_gate_node


DEFAULT_EPISODE = (
    Path(__file__).resolve().parents[1]
    / "episodes"
    / "2026-05-05-desktop-software-licensing-it-turns-out-is"
)


GATES = [
    ("gate:lint", lint_gate_node),
    ("gate:validate", validate_gate_node),
    ("gate:inspect", inspect_gate_node),
    ("gate:design_adherence", design_adherence_gate_node),
    ("gate:snapshot", snapshot_gate_node),
    ("gate:captions_track", captions_track_gate_node),
    ("gate:animation_map", animation_map_gate_node),
]

PENDING_GATES: list[str] = []


def _build_state(episode_dir: Path) -> dict:
    """Assemble the minimum state the gates need from on-disk artifacts.

    The gates only ever read `compose.hyperframes_dir`,
    `compose.plan.beats[*].duration_s`, `compose.design.palette/typography`,
    and `compose.design.design_md_path`. Everything else they tolerate
    being absent. We populate from `<episode>/.hyperframes/` checkpoints
    if present, otherwise minimal scaffolding.
    """
    hf_dir = episode_dir / "hyperframes"
    state: dict = {
        "episode_dir": str(episode_dir),
        "compose": {"hyperframes_dir": str(hf_dir)},
    }

    # Best-effort: pull beats from a persisted plan if present so
    # gate:inspect / gate:snapshot get real per-beat timestamps.
    plan_candidates = [
        hf_dir / "plan.json",
        episode_dir / ".hyperframes" / "plan.json",
    ]
    for cand in plan_candidates:
        if cand.is_file():
            try:
                plan = json.loads(cand.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(plan, dict) and plan.get("beats"):
                state["compose"]["plan"] = {"beats": plan["beats"]}
                break

    # Best-effort: pull DESIGN.md path so gate:design_adherence can
    # check avoidance keywords.
    design_md = hf_dir / "DESIGN.md"
    if design_md.is_file():
        state["compose"].setdefault("design", {})["design_md_path"] = str(design_md)

    return state


def _print_record(name: str, record: dict) -> None:
    status = "PASS" if record.get("passed") else "FAIL"
    extras = ""
    if record.get("headless_artifact_suspected"):
        extras = " (headless_artifact_suspected — annotate, do not iterate palette)"
    print(f"\n[{status}] {name}{extras}")
    violations = record.get("violations") or []
    if violations:
        for i, v in enumerate(violations, 1):
            indent = "      "
            body = v.replace("\n", "\n" + indent)
            print(f"  {i:>2}. {body}")
    if record.get("annotation"):
        print(f"   ann: {record['annotation']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--episode",
        type=Path,
        default=DEFAULT_EPISODE,
        help="Path to an episode directory (containing hyperframes/).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON report on stdout in addition to the text.",
    )
    args = parser.parse_args()

    if os.environ.get("SMOKE_SKIP") == "1":
        print("SMOKE_SKIP=1 — skipping HOM-141 cluster smoke")
        return 0

    episode_dir: Path = args.episode.resolve()
    hf_dir = episode_dir / "hyperframes"
    if not hf_dir.is_dir():
        print(f"ERROR: {hf_dir} does not exist — pass a real episode via --episode")
        return 2

    print(f"HOM-141 cluster smoke — episode: {episode_dir}")
    print(f"  hyperframes_dir: {hf_dir}")
    print(f"  running {len(GATES)} of 7 cluster gates "
          f"({len(PENDING_GATES)} pending)")
    for name in PENDING_GATES:
        print(f"  - PENDING: {name}")

    state = _build_state(episode_dir)
    if "plan" in state.get("compose", {}):
        n = len(state["compose"]["plan"]["beats"])
        print(f"  loaded plan with {n} beat(s) from disk")
    else:
        print("  no plan.json found — gate:inspect / gate:snapshot will use CLI defaults")

    results: list[dict] = []
    for name, node in GATES:
        update = node(state)
        record = update["gate_results"][0]
        results.append({"gate": name, **record})
        _print_record(name, record)
        # Fold the new gate_record into state so subsequent gates see the
        # same shape as the real graph (`gate_results` is append-only).
        state.setdefault("gate_results", []).append(record)

    failed = [r for r in results if not r["passed"]]
    print("\n" + "=" * 70)
    print(f"Summary: {len(results) - len(failed)}/{len(results)} passed; "
          f"{len(failed)} failed; {len(PENDING_GATES)} pending")
    for r in failed:
        print(f"  - FAIL: {r['gate']}")
    if not failed:
        print("  All available cluster gates green.")

    if args.json:
        print("\n--- JSON report ---")
        print(json.dumps(
            {
                "episode_dir": str(episode_dir),
                "results": results,
                "pending": PENDING_GATES,
            },
            indent=2,
            default=str,
        ))

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
