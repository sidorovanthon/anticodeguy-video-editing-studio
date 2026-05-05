"""HOM-140 smoke: run gate:animation_map against the existing real episode.

Per the HOM-140 ticket DoD: invoke the gate on
`episodes/2026-05-05-desktop-software-licensing-it-turns-out-is/` and
document the outcome in the PR Test plan.

The real test of this gate is whether bundled-helper resolution and the
Windows bootstrap-failure triage produce a usable result on a real HF
project. Mocked unit tests prove the parser; only this smoke proves the
subprocess invocation and bootstrap-stderr parsing.

Run from the worktree's `graph/` directory:

    PYTHONPATH=$(pwd)/src \
      /c/Users/sidor/repos/anticodeguy-video-editing-studio/graph/.venv/Scripts/python.exe \
      smoke_hom140.py

Skip with SMOKE_SKIP=1.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from edit_episode_graph.gates.animation_map import animation_map_gate_node


DEFAULT_EPISODE = (
    Path(__file__).resolve().parents[1]
    / "episodes"
    / "2026-05-05-desktop-software-licensing-it-turns-out-is"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, default=DEFAULT_EPISODE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if os.environ.get("SMOKE_SKIP") == "1":
        print("SMOKE_SKIP=1 — skipping HOM-140 smoke")
        return 0

    episode_dir: Path = args.episode.resolve()
    hf_dir = episode_dir / "hyperframes"
    if not hf_dir.is_dir():
        print(f"ERROR: {hf_dir} does not exist")
        return 2

    print(f"HOM-140 smoke — episode: {episode_dir}")
    print(f"  hyperframes_dir: {hf_dir}")

    state = {"episode_dir": str(episode_dir), "compose": {"hyperframes_dir": str(hf_dir)}}
    update = animation_map_gate_node(state)
    record = update["gate_results"][0]

    status = "PASS" if record["passed"] else "FAIL"
    print(f"\n[{status}] {record['gate']}")
    print(f"  helper_path:        {record.get('helper_path')}")
    print(f"  fallback_used:      {record.get('fallback_helper_used')}")
    if record.get("violations"):
        for i, v in enumerate(record["violations"], 1):
            indent = "      "
            body = v.replace("\n", "\n" + indent)
            print(f"  {i:>2}. {body}")
    for n in update.get("notices", []):
        print(f"  notice: {n}")

    if args.json:
        print(json.dumps({"gate": record}, indent=2, default=str))

    return 0 if record["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
