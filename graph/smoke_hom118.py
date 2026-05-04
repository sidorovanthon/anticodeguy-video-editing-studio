"""HOM-118 smoke: real-CLI Opus invocation of p4_design_system + gate:design_ok.

Visual identity is creative work; per memory `feedback_creative_nodes_flagship_tier`
the smoke must run against the flagship tier (Opus 4.7, resolved via
`tier=smart` in `backends/claude.py`) — Haiku gives false positives on
creative quality.

This smoke does NOT need a full episode fixture (audio, transcripts,
final.mp4): the design pass only consumes `strategy` + `edl.ranges[].beat`
from state and writes `DESIGN.md` to disk. We synthesise a minimal episode
dir under episodes/<smoke-slug>/ with a Phase-3-shaped strategy and EDL.

Cost: one Opus 4.7 call; a few cents at most. Skip with SMOKE_SKIP=1.

Run from the worktree's graph directory:
    .venv/Scripts/python smoke_hom118.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from edit_episode_graph.backends._concurrency import BackendSemaphores
from edit_episode_graph.backends._router import BackendRouter
from edit_episode_graph.backends.claude import ClaudeCodeBackend
from edit_episode_graph.gates.design_ok import design_ok_gate_node
from edit_episode_graph.nodes.p4_design_system import _build_node, _render_ctx

REPO_ROOT = Path(__file__).resolve().parent.parent
SLUG = "smoke-hom118-design-system"
EPISODE = REPO_ROOT / "episodes" / SLUG


def _state() -> dict:
    return {
        "slug": SLUG,
        "episode_dir": str(EPISODE),
        "edit": {
            "strategy": {
                "shape": (
                    "Hook on the licensing surprise, problem framed in two beats, "
                    "payoff with a stat. Tone is analytical / technical (Swiss Pulse fits)."
                ),
                "takes": ["[003.76-010.86] hook", "[013.78-024.24] problem", "[032.00-040.50] payoff"],
                "grade": "neutral",
                "pacing": "tight",
                "length_estimate_s": 22.0,
            },
            "edl": {
                "ranges": [
                    {"source": "raw", "start": 3.95, "end": 10.85,
                     "beat": "HOOK",    "quote": "desktop software licensing", "reason": "x"},
                    {"source": "raw", "start": 13.95, "end": 24.20,
                     "beat": "PROBLEM", "quote": "it turns out is", "reason": "x"},
                    {"source": "raw", "start": 32.05, "end": 40.45,
                     "beat": "PAYOFF",  "quote": "...", "reason": "x"},
                ],
            },
        },
    }


def main() -> int:
    if os.environ.get("SMOKE_SKIP") == "1":
        print("SMOKE SKIP: SMOKE_SKIP=1")
        return 0

    EPISODE.mkdir(parents=True, exist_ok=True)
    (EPISODE / "hyperframes").mkdir(parents=True, exist_ok=True)

    state = _state()
    backends = [ClaudeCodeBackend()]
    sems = BackendSemaphores({b.name: b.capabilities.max_concurrent for b in backends})
    router = BackendRouter(backends, sems)

    print("\n=== Case 1: real-CLI Opus invocation of p4_design_system ===")
    node = _build_node()
    update = node._invoke_with(
        router, state,
        render_ctx={
            "slug": SLUG, "episode_dir": str(EPISODE),
            **_render_ctx(state),
        },
        timeout_s=240,
    )
    runs = update.get("llm_runs") or []
    print(f"  attempts: {len(runs)}")
    for r in runs:
        wall = r.get("wall_time_s")
        wall_s = f"{wall:.1f}" if isinstance(wall, (int, float)) else "n/a"
        print(f"  - model={r.get('model')} success={r.get('success')} "
              f"wall_s={wall_s} tokens_in={r.get('tokens_in')} "
              f"tokens_out={r.get('tokens_out')} reason={r.get('reason')}")

    design = (update.get("compose") or {}).get("design") or {}
    if "raw_text" in design and "palette" not in design:
        print(f"SMOKE FAIL: schema extraction failed; raw_text head: "
              f"{(design.get('raw_text') or '')[:300]!r}", file=sys.stderr)
        return 1
    if not design or "palette" not in design:
        print(f"SMOKE FAIL: no DesignDoc in update: {update!r}", file=sys.stderr)
        return 1

    md_path = design.get("design_md_path")
    print(f"  ✓ DesignDoc returned: style_name={design.get('style_name')!r} "
          f"refs={len(design.get('refs') or [])} alts={len(design.get('alternatives') or [])} "
          f"anti={len(design.get('anti_patterns') or [])} "
          f"beat_map={len(design.get('beat_visual_mapping') or [])}")
    print(f"  design_md_path: {md_path}")
    if md_path and Path(md_path).is_file():
        size = Path(md_path).stat().st_size
        print(f"  DESIGN.md on disk: {size}B")
    else:
        print(f"SMOKE FAIL: DESIGN.md not on disk at {md_path}", file=sys.stderr)
        return 1

    print("\n=== Case 2: gate:design_ok evaluates produced DesignDoc ===")
    state_with_design = {**state}
    state_with_design["compose"] = {"design": design}
    out = design_ok_gate_node(state_with_design)
    record = (out.get("gate_results") or [{}])[0]
    print(f"  gate:design_ok passed={record.get('passed')} iter={record.get('iteration')}")
    for v in record.get("violations") or []:
        print(f"    * {v}")
    if not record.get("passed"):
        # Surface but don't fail — the gate's purpose is to report violations
        # for retry; the smoke validates the integration shape, not Opus's
        # taste. A fail surfaces what the retry loop would feed back in.
        print("SMOKE NOTE: gate did not pass — would re-dispatch in production")

    print("\nSMOKE OK: real Opus invocation + DESIGN.md written + gate evaluated")
    print("Output preview (first 600 chars of DESIGN.md):\n")
    print(Path(md_path).read_text(encoding="utf-8")[:600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
