"""HOM-134 smoke: real-CLI Haiku invocation of p4_beat (Pattern A scene authoring).

Per CLAUDE.md per-ticket DoD item 1: prove the subprocess shape, brief
render context, telemetry append, and `Write` tool side-effect actually
work end-to-end. Cost: ~$0.001 on Haiku.

Synthesises the minimal state p4_beat needs:
  - episode_dir + hyperframes/ scaffold dir
  - compose.design_md_path → fixture DESIGN.md (~minimal valid shape)
  - compose.expanded_prompt_path → fixture expanded-prompt.md
  - compose.catalog → empty (catalog is informational only)
  - _beat_dispatch → one beat at index 0 of 1, is_final=True

Then invokes the node through a real BackendRouter/Claude backend with
`model_override="claude-haiku-4-5-20251001"` and asserts:
  - llm_runs has one entry, success=True, backend=claude
  - the scene fragment file exists with non-trivial content
  - the fragment contains the required Pattern A markers
    (#scene-<id> CSS scoping, tl.fromTo, no <template>, no
    data-composition-id on the scene div, no `repeat: -1`)

Skip with SMOKE_SKIP=1.

Run from the worktree's graph directory:
    .venv/Scripts/python smoke_hom134.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from edit_episode_graph.backends._concurrency import BackendSemaphores
from edit_episode_graph.backends._router import BackendRouter
from edit_episode_graph.backends.claude import ClaudeCodeBackend
from edit_episode_graph.graph import build_graph_uncompiled
from edit_episode_graph.nodes.p4_beat import _build_node, _render_ctx


HAIKU_MODEL = "claude-haiku-4-5-20251001"

DESIGN_MD = """\
---
style_name: Swiss Pulse
palette:
  - {role: background, hex: "#0a0a0a"}
  - {role: foreground, hex: "#f0f0f0"}
  - {role: accent,     hex: "#0066FF"}
typography:
  - {role: headline, family: Helvetica Neue, weight: 700, size: 7rem}
  - {role: body,     family: Inter,          weight: 400, size: 1.25rem}
beat_visual_mapping:
  - {beat: "HOOK", treatment: "Tight typographic close-up; accent at full saturation; ambient grid lines breathing in BG."}
---

# Overview

Editorial restraint, grid-locked compositions, hairline rules. Lead the eye
to one stat per beat.
"""

EXPANDED_PROMPT = """\
# Expanded prompt

## Scene 1 — HOOK

Hero stat: "$2.4M / year". Background: faint grid (12 cols, 1px lines, 8% opacity)
plus two slow-floating dots in the upper-right quadrant. Typography pulls hard
on the headline; subhead in body weight enters from below.

- Energy: medium
- Motion: 3 distinct eases (power3.out for the stat, sine.inOut for ambient,
  expo.out for the subhead reveal)
- Density: 8+ elements at hero frame
"""


def case_topology() -> int:
    print("\n=== Case 1: topology check (offline) ===")
    g = build_graph_uncompiled().compile().get_graph()
    nodes = set(g.nodes.keys())
    edges = {(e.source, e.target) for e in g.edges}
    if "p4_beat" not in nodes:
        print("SMOKE FAIL: p4_beat not in compiled graph", file=sys.stderr)
        return 1
    expected = {
        ("p4_dispatch_beats", "p4_beat"),
        ("p4_beat", "p4_assemble_index"),
    }
    missing = expected - edges
    if missing:
        print(f"SMOKE FAIL: missing edges {sorted(missing)}", file=sys.stderr)
        return 1
    print("  ✓ p4_beat present and wired (dispatch_beats → p4_beat → assemble_index)")
    return 0


def case_real_cli_haiku() -> int:
    print("\n=== Case 2: real-CLI Haiku invocation of p4_beat ===")
    if os.environ.get("SMOKE_SKIP") == "1":
        print("SMOKE SKIP: SMOKE_SKIP=1")
        return 0

    with tempfile.TemporaryDirectory() as td:
        episode_dir = Path(td)
        hf = episode_dir / "hyperframes"
        (hf / ".hyperframes").mkdir(parents=True)
        (hf / "compositions").mkdir(parents=True)
        design_md = hf / "DESIGN.md"
        expanded = hf / ".hyperframes" / "expanded-prompt.md"
        design_md.write_text(DESIGN_MD, encoding="utf-8")
        expanded.write_text(EXPANDED_PROMPT, encoding="utf-8")
        scene_path = hf / "compositions" / "hook.html"

        state = {
            "slug": "smoke-hom134",
            "episode_dir": str(episode_dir),
            "compose": {
                "design_md_path": str(design_md),
                "expanded_prompt_path": str(expanded),
                "catalog": {"blocks": [], "components": []},
            },
            "_beat_dispatch": {
                "scene_id": "hook",
                "beat_index": 0,
                "total_beats": 1,
                "is_final": True,
                "data_start_s": 0.0,
                "data_duration_s": 4.5,
                "data_track_index": 1,
                "data_width": 1920,
                "data_height": 1080,
                "plan_beat": {
                    "beat": "HOOK",
                    "duration_s": 4.5,
                    "energy": "medium",
                    "intent": "land the licensing-surprise stat hard",
                },
                "scene_html_path": str(scene_path),
            },
        }

        backends = [ClaudeCodeBackend()]
        sems = BackendSemaphores({b.name: b.capabilities.max_concurrent for b in backends})
        router = BackendRouter(backends, sems)

        node = _build_node()
        ctx = {"slug": state["slug"], "episode_dir": state["episode_dir"], **_render_ctx(state)}
        update = node._invoke_with(
            router, state, render_ctx=ctx,
            timeout_s=300,
            model_override=HAIKU_MODEL,
        )

        runs = update.get("llm_runs") or []
        print(f"  attempts: {len(runs)}")
        for r in runs:
            wall = r.get("wall_time_s")
            wall_s = f"{wall:.1f}" if isinstance(wall, (int, float)) else "n/a"
            print(f"  - model={r.get('model')} success={r.get('success')} "
                  f"wall_s={wall_s} tokens_in={r.get('tokens_in')} "
                  f"tokens_out={r.get('tokens_out')} reason={r.get('reason')}")

        if update.get("errors"):
            print(f"SMOKE FAIL: errors={update['errors']!r}", file=sys.stderr)
            return 1
        if not scene_path.is_file():
            print(f"SMOKE FAIL: fragment not written at {scene_path}", file=sys.stderr)
            return 1
        body = scene_path.read_text(encoding="utf-8")
        size = len(body)
        print(f"  fragment on disk: {size}B")
        if size < 500:
            print("SMOKE FAIL: fragment suspiciously short", file=sys.stderr)
            return 1

        # Pattern A markers — these are load-bearing per spec.
        problems: list[str] = []
        if "#scene-hook" not in body:
            problems.append("no #scene-hook CSS scoping")
        if "tl.fromTo" not in body:
            problems.append("no tl.fromTo entrances (Hard Rule per motion-principles.md)")
        if "<template" in body.lower():
            problems.append("contains <template> wrapper (Pattern B is broken upstream)")
        if 'data-composition-id' in body:
            problems.append("scene div carries data-composition-id (root-only per catalog.md L13)")
        if "repeat: -1" in body:
            problems.append("contains forbidden literal `repeat: -1` (HF lint regex false-positive)")
        if problems:
            print("SMOKE FAIL: Pattern A markers missing:", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            print("\nFragment head (800 chars):\n", file=sys.stderr)
            print(body[:800], file=sys.stderr)
            return 1
        print(f"  ✓ Pattern A markers present: #scene-hook, tl.fromTo, no <template>, "
              "no scene-div data-composition-id, no `repeat: -1`")
        print("\nFragment head (400 chars):\n")
        print(body[:400])
        return 0


def main() -> int:
    rc = 0
    rc = case_topology() or rc
    rc = case_real_cli_haiku() or rc
    if rc == 0:
        print("\n✓ smoke_hom134 PASS")
    else:
        print("\n✗ smoke_hom134 FAIL", file=sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
