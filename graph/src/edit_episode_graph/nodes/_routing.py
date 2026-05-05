"""Conditional-edge routing helpers — pure-function decisions on graph state.

LangGraph conditional edges return the name of the next node (or `END`).
These functions are imported by `graph.py` and exercised directly by unit
tests. They MUST NOT mutate state — state deltas are emitted by nodes.

`skip_phase2?` reads the container tag deterministically (per spec §4.1),
not the script's own tag layer. The script *also* checks the tag when it
runs, but the conditional-edge form makes the decision visible in Studio
(idempotency observable, ElevenLabs not invoked) — that's the v1 DoD.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from langgraph.graph import END

# Mirrors scripts/isolate_audio.py — kept in sync by convention; the graph is
# allowed to know the tag it's gating on.
SUPPORTED_EXTS = (".mp4", ".mov", ".mkv", ".webm")
TAG_KEY = "ANTICODEGUY_AUDIO_CLEANED"
TAG_VALUE = "elevenlabs-v1"


def _find_raw_video(episode_dir: Path) -> Path | None:
    if not episode_dir.exists():
        return None
    matches = [
        p for p in episode_dir.iterdir()
        if p.is_file() and p.stem == "raw" and p.suffix.lower() in SUPPORTED_EXTS
    ]
    return matches[0] if len(matches) == 1 else None


def _container_has_clean_tag(video: Path) -> bool:
    """Return True iff ffprobe reports the clean-audio tag at the container level.

    Conservative: any failure (missing ffprobe, malformed JSON, missing file)
    returns False, which routes through `isolate_audio`. The script will then
    raise its own clear error — better than masking a bad raw with a skip.
    """
    if shutil.which("ffprobe") is None:
        return False
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(video)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    if result.returncode != 0:
        return False
    try:
        probe = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return False
    tags = (probe.get("format") or {}).get("tags") or {}
    return any(k.lower() == TAG_KEY.lower() and v == TAG_VALUE for k, v in tags.items())


def route_after_pickup(state) -> str:
    """pickup → END | isolate_audio | preflight_canon (skip_phase2 baked in)."""
    if state.get("errors"):
        return END
    if state.get("pickup", {}).get("idle"):
        return END
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return END
    raw = _find_raw_video(Path(episode_dir))
    if raw is not None and _container_has_clean_tag(raw):
        return "preflight_canon"
    return "isolate_audio"


def route_after_preflight(state) -> str:
    """preflight_canon -> glue_remap_transcript | p3_pre_scan | p3_inventory."""
    if state.get("errors"):
        return END
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return END
    edit_dir = Path(episode_dir) / "edit"
    if (edit_dir / "final.mp4").exists():
        return "glue_remap_transcript"
    if (edit_dir / "takes_packed.md").exists():
        return "p3_pre_scan"
    return "p3_inventory"


def route_after_inventory(state) -> str:
    """p3_inventory -> END on error | p3_pre_scan on success."""
    if state.get("errors"):
        return END
    return "p3_pre_scan"


def route_after_pre_scan(state) -> str:
    """p3_pre_scan -> END on error | p3_strategy on success."""
    if state.get("errors"):
        return END
    return "p3_strategy"


def route_after_strategy(state) -> str:
    """p3_strategy -> END on error | strategy_confirmed_interrupt on success.

    Inserts canon HR 11 approval gate before EDL selection. The interrupt
    node short-circuits if strategy was skipped upstream (no plan to confirm)
    or if the operator already approved on a prior turn.
    """
    if state.get("errors"):
        return END
    return "strategy_confirmed_interrupt"


STRATEGY_REVISION_CAP = 3


def route_after_strategy_confirmed(state) -> str:
    """strategy_confirmed_interrupt -> p3_edl_select | p3_strategy | halt | END.

    Three branches matching the interrupt node's three outcomes:
      - approved → p3_edl_select (canon path forward)
      - skipped or errors → END (defensive)
      - otherwise (revision queued) → p3_strategy if cap not exceeded,
        halt_llm_boundary if it has been (avoid infinite loop)
    """
    if state.get("errors"):
        return END
    strategy = (state.get("edit") or {}).get("strategy") or {}
    if strategy.get("skipped"):
        return END
    if strategy.get("approved"):
        return "p3_edl_select"
    revisions = state.get("strategy_revisions") or []
    if len(revisions) >= STRATEGY_REVISION_CAP:
        return "halt_llm_boundary"
    return "p3_strategy"


def route_after_edl_select(state) -> str:
    """p3_edl_select -> END on error/skip | gate:edl_ok on success."""
    if state.get("errors"):
        return END
    edl = (state.get("edit") or {}).get("edl") or {}
    if edl.get("skipped"):
        return END
    return "gate_edl_ok"


def route_after_edl_ok(state) -> str:
    """gate:edl_ok -> p3_render_segments on pass | edl_failure_interrupt on fail.

    The interrupt node suspends the graph (HITL) so an operator can inspect
    `state["gate_results"]`, fix the EDL, and resume. Per spec §6.2 the gate
    itself stays pure (state-update only); routing decides what to do with
    the recorded outcome. The retry-loop variant (re-call p3_edl_select with
    violations fed back into the brief) is tracked separately under HOM-75.
    """
    from ..gates._base import latest_gate_result
    result = latest_gate_result(state, "gate:edl_ok")
    if result and result.get("passed"):
        return "p3_render_segments"
    return "edl_failure_interrupt"


def route_after_render_segments(state) -> str:
    """p3_render_segments -> END on error | p3_self_eval | halt on render-skip.

    HOM-104 wires the canon Step 7 self-eval pass downstream. If render was
    skipped (e.g., upstream EDL skip), there is nothing to check; route to
    halt_llm_boundary so the existing skip-notice surfaces.
    """
    if state.get("errors"):
        return END
    render = (state.get("edit") or {}).get("render") or {}
    if render.get("skipped"):
        return "halt_llm_boundary"
    return "p3_self_eval"


def route_after_self_eval(state) -> str:
    """p3_self_eval -> END on error/skip | gate_eval_ok on success."""
    if state.get("errors"):
        return END
    report = (state.get("edit") or {}).get("eval") or {}
    if report.get("skipped"):
        return "halt_llm_boundary"
    return "gate_eval_ok"


def route_after_eval_ok(state) -> str:
    """gate:eval_ok -> p3_persist_session on pass | p3_render_segments on fail+iter<3 | escalate."""
    from ..gates._base import latest_gate_result
    record = latest_gate_result(state, "gate:eval_ok")
    if record is None:
        return "eval_failure_interrupt"
    if record.get("passed"):
        return "p3_persist_session"
    if (record.get("iteration") or 0) < 3:
        return "p3_render_segments"
    return "eval_failure_interrupt"


def route_after_persist_session(state) -> str:
    """p3_persist_session -> END on hard error | halt_llm_boundary otherwise.

    A persist skip or sub-agent failure is non-fatal — the Session block is
    a memory aid for the next run, not load-bearing for Phase 4. Errors
    surfaced into `state['errors']` (e.g. AllBackendsExhausted) still END
    the graph; otherwise we continue to halt_llm_boundary.
    """
    if state.get("errors"):
        return END
    return "halt_llm_boundary"


def route_after_remap(state) -> str:
    """glue_remap_transcript → END | p4_scaffold (skip_phase4 = idempotent)."""
    if state.get("errors"):
        return END
    episode_dir = state.get("episode_dir")
    if not episode_dir:
        return END
    if (Path(episode_dir) / "hyperframes" / "index.html").exists():
        return END
    return "p4_scaffold"


def route_after_scaffold(state) -> str:
    """p4_scaffold → END on error/skip | p4_design_system on success.

    The scaffold node creates the hyperframes/ project skeleton; the design
    system pass that follows consumes it and writes DESIGN.md alongside.
    """
    if state.get("errors"):
        return END
    return "p4_design_system"


def route_after_design_system(state) -> str:
    """p4_design_system → END on error/skip | gate:design_ok on success."""
    if state.get("errors"):
        return END
    design = (state.get("compose") or {}).get("design") or {}
    if design.get("skipped"):
        return END
    return "gate_design_ok"


def route_after_design_ok(state) -> str:
    """gate:design_ok → p4_prompt_expansion on pass | halt_llm_boundary on fail.

    v4-sans-HITL routing per spec §"v4 — Phase 4 sans HITL": gate failures
    surface as a halt rather than a HITL retry loop. The retry-with-violations
    re-dispatch (analogous to gate:eval_ok's iter<3 re-render) is a v5 concern
    tracked under HOM-77.
    """
    from ..gates._base import latest_gate_result
    record = latest_gate_result(state, "gate:design_ok")
    if record and record.get("passed"):
        return "p4_prompt_expansion"
    return "halt_llm_boundary"


def route_after_prompt_expansion(state) -> str:
    """p4_prompt_expansion → END on error/skip | p4_plan otherwise.

    HOM-120 wires `p4_plan` after the expansion step (spec §4.3 ordering:
    design → gate:design_ok → prompt_expansion → plan → gate:plan_ok). The
    plan node consumes both DESIGN.md and the just-written
    `.hyperframes/expanded-prompt.md`, so it must run downstream of both.
    """
    if state.get("errors"):
        return END
    expansion = (state.get("compose") or {}).get("expansion") or {}
    if expansion.get("skipped"):
        return END
    return "p4_plan"


def route_after_plan(state) -> str:
    """p4_plan → END on error/skip | gate:plan_ok on success."""
    if state.get("errors"):
        return END
    plan = (state.get("compose") or {}).get("plan") or {}
    if plan.get("skipped"):
        return END
    return "gate_plan_ok"


def route_after_plan_ok(state) -> str:
    """gate:plan_ok → p4_catalog_scan on pass | halt_llm_boundary on fail.

    v4-sans-HITL routing per spec §"v4 — Phase 4 sans HITL": gate failures
    surface as a halt rather than a HITL retry loop (same pattern as
    `route_after_design_ok`). Pass-side advances to catalog scan
    (HOM-121); the per-beat fan-out and captions nodes that populate
    `compose.beats` / `compose.captions_block_path` are future tickets,
    so `p4_assemble_index` currently skips and the run halts there.
    """
    from ..gates._base import latest_gate_result
    record = latest_gate_result(state, "gate:plan_ok")
    if record and record.get("passed"):
        return "p4_catalog_scan"
    return "halt_llm_boundary"


def route_after_catalog_scan(state) -> str:
    """p4_catalog_scan → END on error | p4_captions_layer otherwise.

    HOM-123 inserts the captions authoring node between catalog scan and the
    beat-fan-out decision. Captions depend only on `DESIGN.md` + transcript
    (both available before catalog scan completes), so authoring them once
    here — outside the per-beat fan-out — keeps the topology linear and
    avoids re-running the smart-tier captions node N times. The beat-vs-skip
    decision moves to `route_after_captions_layer`.
    """
    if state.get("errors"):
        return END
    return "p4_captions_layer"


def route_after_captions_layer(state) -> str:
    """p4_captions_layer → END on error | p4_dispatch_beats (beats present) |
    p4_assemble_index (no beats).

    Mirrors the pre-HOM-123 `route_after_catalog_scan` decision, shifted one
    node downstream. A captions skip (e.g. missing transcript) is non-fatal:
    `p4_assemble_index` treats `compose.captions_block_path` as optional and
    assembles without it; the run continues so the operator sees both the
    assembled scenes and the skip notice in Studio.
    """
    if state.get("errors"):
        return END
    plan = (state.get("compose") or {}).get("plan") or {}
    if plan.get("beats"):
        return "p4_dispatch_beats"
    return "p4_assemble_index"


def route_after_assemble_index(state) -> str:
    """p4_assemble_index → END on error | studio_launch | halt_llm_boundary.

    A successful assemble (patched index.html on disk) advances to
    `studio_launch` (HOM-125). A skipped assemble (e.g. missing scenes)
    routes to halt so the boundary's notice surfaces — there is nothing
    to preview. HOM-127 inserts the gate cluster (lint/validate/inspect
    /design_adherence/animation_map/snapshot/captions_track) + p4_persist_session
    between assemble and studio_launch.
    """
    if state.get("errors"):
        return END
    assemble = (state.get("compose") or {}).get("assemble") or {}
    if assemble.get("skipped"):
        return "halt_llm_boundary"
    return "studio_launch"


def route_after_studio_launch(state) -> str:
    """studio_launch → END on error | gate_static_guard otherwise."""
    if state.get("errors"):
        return END
    return "gate_static_guard"


def route_after_static_guard(state) -> str:
    """gate:static_guard → halt_llm_boundary on pass or fail.

    v4 ends here. Failures surface in `gate_results` for operator review;
    HITL `user_review` (which would re-route on fail) is HOM-78/v6.
    """
    return "halt_llm_boundary"
