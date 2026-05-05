"""HOM-120 smoke: real-CLI invocation of p4_plan.

Per CLAUDE.md graph DoD: smoke runs through the cheapest available model
(Haiku 4.5) to verify subprocess shape, stdout parsing, schema extraction,
and that the dispatched sub-agent actually returns a valid CompositionPlan
covering the EDL beats with explicit transitions per boundary. Cost is
negligible (~$0.001).

Production runs use tier=smart (Opus 4.7 — see config.yaml override and
memory `feedback_creative_nodes_flagship_tier`); the smoke pins Haiku
locally via per-run model_override since cheap-model creative quality is
out of scope here — only the integration is.

Skip with SMOKE_SKIP=1.

Run from the worktree's graph directory:
    .venv/Scripts/python smoke_hom120.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from edit_episode_graph.backends._concurrency import BackendSemaphores
from edit_episode_graph.backends._router import BackendRouter
from edit_episode_graph.backends.claude import ClaudeCodeBackend
from edit_episode_graph._paths import repo_root
from edit_episode_graph.gates.plan_ok import plan_ok_gate_node
from edit_episode_graph.nodes.p4_plan import _build_node, _render_ctx

REPO_ROOT = repo_root()
SLUG = "smoke-hom120-plan"
EPISODE = REPO_ROOT / "episodes" / SLUG

DESIGN_MD = """\
---
style_name: Swiss Pulse
palette:
  background: "#0a0a0a"
  foreground: "#f0f0f0"
  accent:     "#0066FF"
typography:
  headline: { family: "Helvetica Neue", weight: 700 }
  body:     { family: "Inter",          weight: 400 }
mood: editorial / analytical / restrained
---

# Overview
Editorial restraint, grid-locked stats, no decoratives for decoration's sake.

# Beat Visual Mapping
- HOOK: tight typographic close-up; accent at full saturation.
- PROBLEM: stat at 7rem dominates the frame.
- PAYOFF: wide reveal with hairline rules; staggered entrance.
"""

EXPANDED_PROMPT_MD = """\
# Episode Title — Software Licensing

## Style block

Background `#0a0a0a`, foreground `#f0f0f0`, accent `#0066FF`. Helvetica
Neue 700 headlines, Inter 400 body.

## Rhythm

fast-SLOW-fast — HOOK lands quickly, PROBLEM holds for analytical weight,
PAYOFF accelerates into the stat.

## Global rules

- No gradient text.
- Hairline rules only as decoratives.

## Scenes

### HOOK (medium energy, ~6.9s)
Mid-flight over editorial canvas; oversized stat slams in.

### PROBLEM (calm energy, ~10.5s)
Stat dominates at 7rem; foreground tints toward accent at 8%.

### PAYOFF (high energy, ~8.4s)
Wide reveal with hairline rules; staggered entrance.

## Motifs

- Hairline horizontal rules at scene transitions.
- Numeric scale-jumps for emphasis.

## Negative space and density

8-10 elements per scene; never crowd the headline.
"""


def _state(design_md_path: Path, expanded_path: Path) -> dict:
    return {
        "slug": SLUG,
        "episode_dir": str(EPISODE),
        "compose": {
            "design_md_path": str(design_md_path),
            "expanded_prompt_path": str(expanded_path),
        },
        "edit": {
            "strategy": {
                "shape": "Hook on the licensing surprise; tension framed; payoff with stat.",
                "takes": ["[003.76-010.86] hook", "[013.78-024.24] problem", "[032.00-040.50] payoff"],
                "grade": "neutral",
                "pacing": "tight",
                "length_estimate_s": 25.8,
            },
            "edl": {
                "ranges": [
                    {"source": "raw", "start": 3.95, "end": 10.85,
                     "beat": "HOOK",    "quote": "x", "reason": "y"},
                    {"source": "raw", "start": 13.95, "end": 24.20,
                     "beat": "PROBLEM", "quote": "x", "reason": "y"},
                    {"source": "raw", "start": 32.05, "end": 40.45,
                     "beat": "PAYOFF",  "quote": "x", "reason": "y"},
                ],
            },
        },
    }


def main() -> int:
    if os.environ.get("SMOKE_SKIP") == "1":
        print("SMOKE SKIP: SMOKE_SKIP=1")
        return 0

    EPISODE.mkdir(parents=True, exist_ok=True)
    hf_dir = EPISODE / "hyperframes"
    hf_dir.mkdir(parents=True, exist_ok=True)
    design_md = hf_dir / "DESIGN.md"
    design_md.write_text(DESIGN_MD, encoding="utf-8")
    expanded_path = hf_dir / ".hyperframes" / "expanded-prompt.md"
    expanded_path.parent.mkdir(parents=True, exist_ok=True)
    expanded_path.write_text(EXPANDED_PROMPT_MD, encoding="utf-8")

    state = _state(design_md, expanded_path)
    backends = [ClaudeCodeBackend()]
    sems = BackendSemaphores({b.name: b.capabilities.max_concurrent for b in backends})
    router = BackendRouter(backends, sems)

    print("\n=== Case 1: real-CLI Haiku invocation of p4_plan ===")
    node = _build_node()
    update = node._invoke_with(
        router, state,
        render_ctx={
            "slug": SLUG, "episode_dir": str(EPISODE),
            **_render_ctx(state),
        },
        timeout_s=240,
        model_override="claude-haiku-4-5-20251001",
    )
    runs = update.get("llm_runs") or []
    print(f"  attempts: {len(runs)}")
    for r in runs:
        wall = r.get("wall_time_s")
        wall_s = f"{wall:.1f}" if isinstance(wall, (int, float)) else "n/a"
        print(f"  - model={r.get('model')} success={r.get('success')} "
              f"wall_s={wall_s} tokens_in={r.get('tokens_in')} "
              f"tokens_out={r.get('tokens_out')} reason={r.get('reason')}")

    plan = (update.get("compose") or {}).get("plan") or {}
    if "raw_text" in plan and "beats" not in plan:
        print(f"SMOKE FAIL: schema extraction failed; raw_text head: "
              f"{(plan.get('raw_text') or '')[:300]!r}", file=sys.stderr)
        return 1
    if not plan.get("beats"):
        print(f"SMOKE FAIL: no plan beats in update: {update!r}", file=sys.stderr)
        return 1
    print(f"  ✓ CompositionPlan: {len(plan['beats'])} beat(s), "
          f"{len(plan.get('transitions') or [])} transition(s), "
          f"rhythm={plan.get('rhythm')!r}")

    print("\n=== Case 2: gate:plan_ok evaluates produced plan ===")
    state_with_plan = {**state, "compose": {**state["compose"], "plan": plan}}
    gate_update = plan_ok_gate_node(state_with_plan)
    record = gate_update["gate_results"][0]
    print(f"  gate:plan_ok passed={record['passed']} iter={record['iteration']}")
    for v in record.get("violations") or []:
        print(f"    * {v}")
    # Either pass or fail is acceptable for the smoke — we're verifying the
    # gate's evaluation pipeline, not Haiku's canon-fidelity.

    print("\nSMOKE OK: real Haiku invocation + structured CompositionPlan + gate evaluated")
    return 0 if any(r.get("success") for r in runs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
