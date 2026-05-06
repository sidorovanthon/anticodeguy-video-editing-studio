"""HOM-147 smoke — generic gate retry-with-feedback (helper + macro + EDL adoption).

Two cases:

  1. **Render-only.** Build state with one prior failed `gate:edl_ok` record,
     run the producer's `_render_ctx` + the brief through the Jinja Env, and
     assert the rendered string contains the prior violations and the
     "address them on this attempt" instruction. Deterministic, no API spend.

  2. **Real-CLI dispatch (Haiku).** Same retry state, but actually invoke
     `LLMNode._invoke_with` with `model_override="claude-haiku-4-5-20251001"`
     so the brief flows through the subprocess + parser + telemetry path.
     We assert the run produced ≥1 backend attempt; we do NOT require the
     model to honor the violations (Haiku may or may not, that's fine — the
     point is to prove the integration shape, not model correctness).

Run from the worktree's graph directory:

    PYTHONPATH=$(pwd)/src .venv/Scripts/python smoke_hom147.py

Skip Case 2 with SMOKE_SKIP_CLI=1 (Case 1 always runs — it's free).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from edit_episode_graph._paths import repo_root
from edit_episode_graph.backends._concurrency import BackendSemaphores
from edit_episode_graph.backends._router import BackendRouter
from edit_episode_graph.backends._types import NodeRequirements
from edit_episode_graph.backends.claude import ClaudeCodeBackend
from edit_episode_graph.backends.codex import CodexBackend
from edit_episode_graph.nodes._llm import _BRIEF_ENV, _load_brief
from edit_episode_graph.nodes.p3_edl_select import _build_node, _render_ctx

REPO_ROOT = repo_root()
SLUG = "edl-smoke"
# Default fixture (gitignored); override with env or CLI for any
# real episode that has edit/takes_packed.md + edit/transcripts/raw.json.
EPISODE = Path(
    os.environ.get(
        "HOM147_EPISODE",
        str(REPO_ROOT / "episodes" / SLUG),
    )
).resolve()


PRIOR_VIOLATIONS = [
    "range[0].start=1.5 cuts inside word 'alpha' [1.0, 2.0]",
    "overlays must be empty (Phase 4 owns animation)",
    "total_duration_s=0.3 deviates from strategy.length_estimate_s=5.0 by >20%",
]


def _retry_state() -> dict:
    """State as it would be on the second attempt — one prior failed gate
    record sits in `gate_results`. The producer's render context picks this
    up via `gate_retry_context` and the brief macro renders the feedback."""
    transcripts = sorted(str(p) for p in (EPISODE / "edit" / "transcripts").glob("*.json"))
    return {
        "slug": SLUG,
        "episode_dir": str(EPISODE),
        "gate_results": [
            {
                "gate": "gate:edl_ok",
                "passed": False,
                "violations": list(PRIOR_VIOLATIONS),
                "iteration": 1,
                "timestamp": "2026-05-06T00:00:00Z",
            },
        ],
        "transcripts": {
            "raw_json_paths": transcripts,
            "takes_packed_path": str(EPISODE / "edit" / "takes_packed.md"),
        },
        "edit": {
            "inventory": {
                "transcript_json_paths": transcripts,
                "sources": [{"stem": "raw", "duration_s": 70.0}],
            },
            "pre_scan": {"slips": []},
            "strategy": {
                "shape": "tutorial", "takes": [], "grade": "neutral",
                "pacing": "tight", "length_estimate_s": 50.0,
            },
        },
    }


def case_render_only() -> str:
    print("\n=== Case 1: render-only — verify prior_violations_block fires ===")
    state = _retry_state()
    ctx = {"slug": state["slug"], "episode_dir": state["episode_dir"]}
    ctx.update(_render_ctx(state))
    print(f"  ctx.prior_iteration: {ctx['prior_iteration']}")
    print(f"  ctx.prior_violations: {len(ctx['prior_violations'])} item(s)")
    rendered = _BRIEF_ENV.from_string(_load_brief("p3_edl_select")).render(**ctx)

    expectations = [
        ("Previous attempt (iteration 1) failed these checks", "macro header"),
        (PRIOR_VIOLATIONS[0], "first violation verbatim"),
        (PRIOR_VIOLATIONS[1], "second violation verbatim"),
        (PRIOR_VIOLATIONS[2], "third violation verbatim"),
        ("address them on this attempt", "macro instruction"),
    ]
    for needle, label in expectations:
        present = needle in rendered
        marker = "✓" if present else "✗"
        print(f"  {marker} {label}: {needle!r}")
        assert present, f"missing in rendered brief: {needle!r}"

    print("  ✓ all violations present in brief\n")
    print("  --- rendered brief tail (last 500 chars) ---")
    print("  " + rendered[-500:].replace("\n", "\n  "))
    return rendered


def case_real_cli_haiku() -> None:
    print("\n=== Case 2: real-CLI dispatch (Haiku) — verify integration shape ===")
    if os.environ.get("SMOKE_SKIP_CLI") == "1":
        print("  SMOKE_SKIP_CLI=1 — skipping live dispatch")
        return
    if not (EPISODE / "edit" / "takes_packed.md").exists():
        print(f"  fixture missing: {EPISODE / 'edit' / 'takes_packed.md'} — skipping")
        return

    state = _retry_state()
    backends = [ClaudeCodeBackend(), CodexBackend()]
    sems = BackendSemaphores({b.name: b.capabilities.max_concurrent for b in backends})
    router = BackendRouter(backends, sems)

    # Build the LLMNode but bypass __call__ so we can pin Haiku without
    # touching config.yaml. _invoke_with takes model_override directly.
    node = _build_node()
    ctx = {"slug": state["slug"], "episode_dir": state["episode_dir"]}
    ctx.update(_render_ctx(state))
    update = node._invoke_with(
        router, state, render_ctx=ctx,
        requirements=NodeRequirements(tier="cheap", needs_tools=True, backends=["claude"]),
        timeout_s=180,
        model_override="claude-haiku-4-5-20251001",
    )

    runs = update.get("llm_runs") or []
    print(f"  attempts: {len(runs)}")
    for r in runs:
        print(f"    backend={r.get('backend')} model={r.get('model')} "
              f"success={r.get('success')} reason={r.get('reason')} "
              f"wall={r.get('wall_time_s')}s")
    assert runs, "expected ≥1 attempt — telemetry append failed"
    edl = (update.get("edit") or {}).get("edl") or {}
    if "raw_text" in edl:
        print(f"  schema parse failed (expected on Haiku occasionally) — "
              f"raw_text preview: {(edl['raw_text'] or '')[:200]!r}")
    elif "skipped" in edl:
        print(f"  skipped: {edl.get('skip_reason')}")
    else:
        print(f"  EDL ranges: {len(edl.get('ranges') or [])}, "
              f"overlays: {edl.get('overlays')}, total: {edl.get('total_duration_s')}")
    print("  ✓ integration shape intact (subprocess + parser + telemetry)")


if __name__ == "__main__":
    print(f"episode: {EPISODE}")
    case_render_only()
    case_real_cli_haiku()
    print("\nDONE")
