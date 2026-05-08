"""HOM-165 smoke: verify p4_beat brief preventive guards land in produced HTML.

Runs the same real-CLI Haiku invocation shape as `smoke_hom134.py` but adds
two HOM-165-specific assertions on the produced fragment:

1. **No `Math.ceil(` used for repeat math.** The brief's "Explicit
   anti-patterns" section forbids `Math.ceil` for `repeat: …` calculation
   (canon: motion-principles.md "Hard-kill every scene boundary"). If the
   brief is doing its job, the LLM uses `Math.floor` or a literal int.

2. **Every fade-out has a paired `tl.set(... visibility: "hidden")` kill.**
   For each `tl.to(... { opacity: 0 ...` in the fragment, there must be a
   `tl.set(... visibility: "hidden"` somewhere in the same script (canon:
   captions.md "Caption Exit Guarantee" + motion-principles.md "Hard-kill").

Cost: ~$0.001 on Haiku. Skip with SMOKE_SKIP=1.

Run from worktree's graph directory:
    .venv/Scripts/python smoke_hom165.py
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

from edit_episode_graph.backends._concurrency import BackendSemaphores
from edit_episode_graph.backends._router import BackendRouter
from edit_episode_graph.backends.claude import ClaudeCodeBackend
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
  - {beat: "HOOK", treatment: "Tight typographic close-up, accent at full saturation, ambient grid lines breathing in BG, headline exits with a fade before the cut."}
---

# Overview

Editorial restraint, grid-locked compositions, hairline rules. Lead the eye
to one stat per beat. Captions and exit text fade hard at the cut.
"""

EXPANDED_PROMPT = """\
# Expanded prompt

## Scene 1 — HOOK

Hero stat: "$2.4M / year". Background: faint grid (12 cols, 1px lines, 8% opacity)
plus two slow-floating dots in the upper-right quadrant (gentle ambient yoyo).
Typography pulls hard on the headline; subhead in body weight enters from below.
Headline performs a brief fade-out at the end of the scene (caption-style exit
with hard kill).

- Energy: medium
- Motion: 3 distinct eases (power3.out for the stat, sine.inOut for ambient,
  expo.out for the subhead reveal)
- Density: 8+ elements at hero frame
- Ambient yoyo loops use a finite repeat count.
"""


_OPACITY_ZERO_RE = re.compile(r"tl\.to\s*\([^)]*opacity\s*:\s*0", re.DOTALL)


def _violates_math_ceil_for_repeat(body: str) -> list[str]:
    """Find any `Math.ceil(` that lands on a `repeat:` line within ~120 chars.

    The brief explicitly forbids Math.ceil for repeat math. We search for
    a `repeat:` token within a short window of any Math.ceil( occurrence.
    """
    problems: list[str] = []
    for m in re.finditer(r"Math\.ceil\s*\(", body):
        start = max(0, m.start() - 120)
        end = min(len(body), m.end() + 120)
        window = body[start:end]
        if "repeat:" in window or "repeat :" in window:
            problems.append(window.strip().replace("\n", " ⏎ ")[:200])
    return problems


def _check_caption_exit_kills(body: str) -> list[str]:
    """For each `tl.to(... opacity: 0 ...)` ensure there is a paired
    `tl.set(... visibility: "hidden" ...)` somewhere in the script.

    This is a coarse check (not per-element) — the goal is to catch
    fragments that have fade-out tweens but zero kill-tweens at all.
    """
    fade_outs = list(_OPACITY_ZERO_RE.finditer(body))
    if not fade_outs:
        return []  # no fade-outs to police
    has_kill = ('visibility: "hidden"' in body) or ("visibility: 'hidden'" in body)
    if not has_kill:
        return [
            f"{len(fade_outs)} `tl.to(... opacity: 0 ...)` fade-out(s) "
            f"present with NO `tl.set(... visibility: \"hidden\" ...)` kill anywhere"
        ]
    return []


def case_real_cli_haiku() -> int:
    print("\n=== HOM-165 smoke: real-CLI Haiku invocation of p4_beat ===")
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
            "slug": "smoke-hom165",
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
                    "intent": "land the headline stat hard, then fade",
                },
                "scene_html_path": str(scene_path),
            },
        }

        backends = [ClaudeCodeBackend()]
        sems = BackendSemaphores(
            {b.name: b.capabilities.max_concurrent for b in backends}
        )
        router = BackendRouter(backends, sems)

        node = _build_node()
        ctx = {
            "slug": state["slug"],
            "episode_dir": state["episode_dir"],
            **_render_ctx(state),
        }
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
            print(
                f"  - model={r.get('model')} success={r.get('success')} "
                f"wall_s={wall_s} tokens_in={r.get('tokens_in')} "
                f"tokens_out={r.get('tokens_out')} reason={r.get('reason')}"
            )

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

        problems: list[str] = []

        # HOM-165 Anti-pattern 1: Math.ceil( for repeat math.
        ceil_violations = _violates_math_ceil_for_repeat(body)
        if ceil_violations:
            problems.append(
                "Math.ceil( used for repeat math (anti-pattern 1):"
            )
            for v in ceil_violations:
                problems.append(f"    near: …{v}…")

        # HOM-165 Anti-pattern 2: opacity:0 fade without visibility:hidden kill.
        for v in _check_caption_exit_kills(body):
            problems.append(f"caption-exit kill missing (anti-pattern 2): {v}")

        # Carry over the load-bearing markers from smoke_hom134 so a
        # successful HOM-165 smoke also implies Pattern A health.
        if "#scene-hook" not in body:
            problems.append("no #scene-hook CSS scoping")
        if "tl.fromTo" not in body:
            problems.append("no tl.fromTo entrances (motion-principles.md)")
        if "<template" in body.lower():
            problems.append("contains <template> wrapper (Pattern B is broken upstream)")
        if "data-composition-id" in body:
            problems.append(
                "scene div carries data-composition-id (root-only per catalog.md L13)"
            )
        if "repeat: -1" in body:
            problems.append(
                "contains forbidden literal `repeat: -1` (HF lint regex false-positive)"
            )

        if problems:
            print("SMOKE FAIL: HOM-165 anti-pattern guards:", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            print("\nFragment head (1000 chars):\n", file=sys.stderr)
            print(body[:1000], file=sys.stderr)
            return 1

        print(
            "  ✓ HOM-165 anti-pattern guards present: no Math.ceil( for repeat math; "
            "fade-out tweens paired with visibility:hidden kill (or no fades at all); "
            "Pattern A markers intact."
        )
        print("\nFragment head (400 chars):\n")
        print(body[:400])
        return 0


def main() -> int:
    rc = case_real_cli_haiku()
    if rc == 0:
        print("\n✓ smoke_hom165 PASS")
    else:
        print("\n✗ smoke_hom165 FAIL", file=sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
