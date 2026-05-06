"""HOM-148 smoke — cluster-gate retry (p4_redispatch_beat + 7 cluster gates).

Three cases:

  1. **Routing.** Synthesize state with a failed `gate:lint` record at iter=1,
     run `route_after_lint(state)`, assert it returns `"p4_redispatch_beat"`.
     Then bump the iteration to 3 and assert it returns `"halt_llm_boundary"`.
     Free; deterministic; proves the helper is wired correctly across all 7
     cluster gates.

  2. **Render-only.** Build the same state with a `gsap_infinite_repeat` lint
     violation, run the producer's `_render_ctx` + brief through the Jinja
     env, and assert the rendered string carries the prior violation, the
     macro header, the `<!-- beat: <scene_id> -->` marker instruction, and
     the canonical scene-id list. Deterministic, no API spend.

  3. **Real-CLI dispatch (Haiku).** Synthesize a fixture HF project on disk
     (root index.html with two `<!-- beat: hook --> ... <!-- beat: payoff -->`
     markers and offending `compositions/hook.html` that lints `repeat: -1`).
     Invoke `_build_node()._invoke_with(...)` with a Haiku override and
     verify ≥1 backend attempt was recorded. We do NOT require the model to
     produce lint-clean output — the integration shape (subprocess + parser
     + telemetry) is what we're proving.

Run from the worktree's graph directory:

    PYTHONPATH=$(pwd)/src .venv/Scripts/python smoke_hom148.py

Skip Case 3 with SMOKE_SKIP_CLI=1 (Cases 1 + 2 always run — they're free).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from edit_episode_graph.backends._concurrency import BackendSemaphores
from edit_episode_graph.backends._router import BackendRouter
from edit_episode_graph.backends._types import NodeRequirements
from edit_episode_graph.backends.claude import ClaudeCodeBackend
from edit_episode_graph.backends.codex import CodexBackend
from edit_episode_graph.nodes._llm import _BRIEF_ENV, _load_brief
from edit_episode_graph.nodes._routing import (
    route_after_animation_map,
    route_after_captions_track,
    route_after_design_adherence,
    route_after_inspect,
    route_after_lint,
    route_after_snapshot,
    route_after_validate,
)
from edit_episode_graph.nodes.p4_redispatch_beat import _build_node, _render_ctx


SLUG = "redispatch-smoke"


PRIOR_VIOLATIONS = [
    "hyperframes lint exit=1:\n"
    "compositions/hook.html:21:23 [gsap_infinite_repeat] "
    "infinite repeat is forbidden — use a finite count derived from data-duration",
]


def _state(*, gate: str, iteration: int, hf_dir: Path | None = None) -> dict:
    """State as if `gate` failed at the given iteration."""
    compose: dict = {
        "plan": {
            "beats": [
                {"beat": "hook", "duration_s": 5.0},
                {"beat": "payoff", "duration_s": 4.0},
            ],
        },
        "design_md_path": "(unused in smoke)",
        "expanded_prompt_path": "(unused in smoke)",
        "catalog": {"blocks": [], "components": []},
    }
    if hf_dir is not None:
        compose["index_html_path"] = str(hf_dir / "index.html")
        compose["hyperframes_dir"] = str(hf_dir)
    return {
        "slug": SLUG,
        "episode_dir": str(hf_dir.parent if hf_dir else Path.cwd()),
        "compose": compose,
        "gate_results": [
            {
                "gate": gate,
                "passed": False,
                "violations": list(PRIOR_VIOLATIONS),
                "iteration": iteration,
                "timestamp": "2026-05-06T00:00:00Z",
            },
        ],
    }


def case_routing() -> None:
    print("\n=== Case 1: routing — every cluster gate retries on iter<3, halts on iter>=3 ===")
    cases = [
        ("gate:lint", route_after_lint),
        ("gate:validate", route_after_validate),
        ("gate:inspect", route_after_inspect),
        ("gate:design_adherence", route_after_design_adherence),
        ("gate:animation_map", route_after_animation_map),
        ("gate:snapshot", route_after_snapshot),
        ("gate:captions_track", route_after_captions_track),
    ]
    for gate_name, router in cases:
        s_retry = _state(gate=gate_name, iteration=1)
        s_halt = _state(gate=gate_name, iteration=3)
        retry_target = router(s_retry)
        halt_target = router(s_halt)
        assert retry_target == "p4_redispatch_beat", (
            f"{gate_name}: expected p4_redispatch_beat at iter=1, got {retry_target!r}"
        )
        assert halt_target == "halt_llm_boundary", (
            f"{gate_name}: expected halt_llm_boundary at iter=3, got {halt_target!r}"
        )
        print(f"  ✓ {gate_name}: iter=1 → {retry_target}; iter=3 → {halt_target}")


def case_render_only() -> str:
    print("\n=== Case 2: render-only — verify violations + macro + scene-ids in brief ===")
    state = _state(gate="gate:lint", iteration=1, hf_dir=Path.cwd())
    ctx = {"slug": state["slug"], "episode_dir": state["episode_dir"]}
    ctx.update(_render_ctx(state))
    print(f"  ctx.failed_gate: {ctx['failed_gate']}")
    print(f"  ctx.prior_iteration: {ctx['prior_iteration']}")
    print(f"  ctx.prior_violations: {len(ctx['prior_violations'])} item(s)")
    print(f"  ctx.scene_ids_json: {ctx['scene_ids_json']}")
    rendered = _BRIEF_ENV.from_string(_load_brief("p4_redispatch_beat")).render(**ctx)

    expectations = [
        ("Previous attempt (iteration 1) failed these checks", "macro header"),
        ("gsap_infinite_repeat", "violation token verbatim"),
        ("address them on this attempt", "macro instruction"),
        ('["hook", "payoff"]', "scene-ids list (canonical plan order)"),
        ("<!-- beat: <scene_id> -->", "marker convention surfaced"),
        ("gate:lint", "failed_gate name"),
        ("class=\"scene clip\"", "Pattern A hard rule"),
        ("tl.fromTo()", "motion-principles citation"),
    ]
    for needle, label in expectations:
        present = needle in rendered
        marker = "✓" if present else "✗"
        print(f"  {marker} {label}: {needle!r}")
        assert present, f"missing in rendered brief: {needle!r}"

    print("  ✓ all expectations present in brief\n")
    return rendered


def _make_fixture_hf(root: Path) -> Path:
    """Build a minimal HF project on disk with two scenes; the `hook` scene
    contains a `gsap_infinite_repeat` violation that `hyperframes lint` would
    catch (the smoke does not actually shell out to the CLI — it only proves
    the LLM dispatch path works against synthetic state).
    """
    hf = root / "hyperframes"
    hf.mkdir(parents=True, exist_ok=True)
    (hf / "compositions").mkdir(parents=True, exist_ok=True)

    # Root index.html with the canonical injection markers + two beats.
    (hf / "index.html").write_text(
        "<!doctype html>\n<html><head>\n"
        '<meta name="viewport" content="width=1920, height=1080">\n'
        "</head><body>\n"
        '<div id="root" data-composition-id="root" data-width="1920" data-height="1080">\n'
        "<!-- p4_assemble_index: beats -->\n"
        "<!-- beat: hook -->\n"
        '<div id="scene-hook" class="scene clip" data-start="0" data-duration="5">\n'
        "  <script>(function(){ const tl = gsap.timeline({paused:true});\n"
        "    tl.to('.aura', { scale: 1.1, repeat: -1 });  // OFFENDING LINE\n"
        "    window.__sceneTimelines = window.__sceneTimelines || {};\n"
        "    window.__sceneTimelines['hook'] = tl;\n"
        "  })();</script>\n"
        "</div>\n"
        "<!-- beat: payoff -->\n"
        '<div id="scene-payoff" class="scene clip" data-start="5" data-duration="4">\n'
        "  <script>(function(){ const tl = gsap.timeline({paused:true});\n"
        "    window.__sceneTimelines['payoff'] = tl;\n"
        "  })();</script>\n"
        "</div>\n"
        "<!-- p4_assemble_index: end -->\n"
        "</div>\n</body></html>\n",
        encoding="utf-8",
    )
    # Author the offending fragment file too so the LLM can `Read` it.
    (hf / "compositions" / "hook.html").write_text(
        '<div id="scene-hook" class="scene clip" data-start="0" data-duration="5">\n'
        "<script>(function(){\n"
        "  const tl = gsap.timeline({paused:true});\n"
        "  tl.to('.aura', { scale: 1.1, repeat: -1 });\n"
        "  window.__sceneTimelines = window.__sceneTimelines || {};\n"
        "  window.__sceneTimelines['hook'] = tl;\n"
        "})();</script>\n"
        "</div>\n",
        encoding="utf-8",
    )
    (hf / "compositions" / "payoff.html").write_text(
        '<div id="scene-payoff" class="scene clip" data-start="5" data-duration="4">\n'
        "<script>(function(){ const tl = gsap.timeline({paused:true});\n"
        "  window.__sceneTimelines = window.__sceneTimelines || {};\n"
        "  window.__sceneTimelines['payoff'] = tl;\n"
        "})();</script></div>\n",
        encoding="utf-8",
    )
    # Fake DESIGN.md + expanded-prompt.md so the LLM can `Read` paths without 404.
    (hf / "DESIGN.md").write_text("# Design (smoke fixture)\n\nPalette: monochrome.\n", encoding="utf-8")
    (hf / ".hyperframes").mkdir(parents=True, exist_ok=True)
    (hf / ".hyperframes" / "expanded-prompt.md").write_text(
        "# Expanded (smoke fixture)\n\n## hook\nIntense opening.\n\n## payoff\nResolution.\n",
        encoding="utf-8",
    )
    return hf


def case_real_cli_haiku() -> None:
    print("\n=== Case 3: real-CLI dispatch (Haiku) — verify integration shape ===")
    if os.environ.get("SMOKE_SKIP_CLI") == "1":
        print("  SMOKE_SKIP_CLI=1 — skipping live dispatch")
        return

    tmp = Path(tempfile.mkdtemp(prefix="hom148-smoke-"))
    try:
        hf = _make_fixture_hf(tmp)
        state = _state(gate="gate:lint", iteration=1, hf_dir=hf)
        # Wire the path-context fields the brief expects to canon paths.
        state["compose"]["design_md_path"] = str(hf / "DESIGN.md")
        state["compose"]["expanded_prompt_path"] = str(hf / ".hyperframes" / "expanded-prompt.md")

        backends = [ClaudeCodeBackend(), CodexBackend()]
        sems = BackendSemaphores({b.name: b.capabilities.max_concurrent for b in backends})
        router = BackendRouter(backends, sems)

        node = _build_node()
        ctx = {"slug": state["slug"], "episode_dir": state["episode_dir"]}
        ctx.update(_render_ctx(state))
        update = node._invoke_with(
            router, state, render_ctx=ctx,
            requirements=NodeRequirements(tier="cheap", needs_tools=True, backends=["claude"]),
            timeout_s=240,
            model_override="claude-haiku-4-5-20251001",
        )

        runs = update.get("llm_runs") or []
        print(f"  attempts: {len(runs)}")
        for r in runs:
            print(f"    backend={r.get('backend')} model={r.get('model')} "
                  f"success={r.get('success')} reason={r.get('reason')} "
                  f"wall={r.get('wall_time_s')}s")
        assert runs, "expected ≥1 attempt — telemetry append failed"

        hook_after = (hf / "compositions" / "hook.html").read_text(encoding="utf-8")
        if "repeat: -1" in hook_after or "repeat:-1" in hook_after:
            print("  ! hook.html still contains 'repeat: -1' after dispatch — Haiku did not fix")
            print("    (acceptable — smoke proves integration shape, not model correctness)")
        else:
            print("  ✓ hook.html no longer contains the infinite-repeat sentinel")
        print("  ✓ integration shape intact (subprocess + parser + telemetry)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    case_routing()
    case_render_only()
    case_real_cli_haiku()
    print("\nDONE")
