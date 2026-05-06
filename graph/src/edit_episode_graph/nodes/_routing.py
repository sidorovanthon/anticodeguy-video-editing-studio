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


# HOM-158: routers must distinguish "the immediate predecessor just failed in
# this run" from "something failed earlier on this thread". The pre-HOM-158
# predicate `if state.get("errors"): return END` conflated the two: because
# `state["errors"]` uses an `add` (append-only) reducer, a single failure
# anywhere on the thread permanently routed every downstream conditional to
# END — even on a fresh turn after the operator fixed the cause.
#
# Mechanism after HOM-158:
#  - LLM nodes raise on terminal failure (see `_llm.py`); pregel does NOT
#    commit writes when a task raises, so LLM failures never appear in
#    `state["errors"]` at all. Deterministic nodes still swallow into
#    `state["errors"]` (see `_deterministic.py` and per-node modules).
#  - This helper checks whether the *latest* error was emitted by the named
#    predecessor. If so, the predecessor failed (most likely on the current
#    turn — a deterministic node that just ran) and the run should END.
#    Otherwise the predecessor either succeeded or never ran since the last
#    error, and routing should proceed.
#
# Edge case: if the same deterministic predecessor failed on a previous turn
# AND succeeds on the current turn without overwriting `state["errors"][-1]`,
# this helper still returns True and the router routes to END. Acceptable for
# v1 — deterministic failures are usually structural (missing files, bad
# input) and don't recover by retry; the operator clearing state is the
# documented escape hatch. Option C from the ticket (`split error channels`)
# is the long-term fix and is tracked separately.
def _predecessor_just_failed(state, *predecessors: str) -> bool:
    errs = state.get("errors") or []
    if not errs:
        return False
    return errs[-1].get("node") in predecessors


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
    if _predecessor_just_failed(state, "pickup"):
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
    if _predecessor_just_failed(state, "preflight_canon"):
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
    if _predecessor_just_failed(state, "p3_inventory"):
        return END
    return "p3_pre_scan"


def route_after_pre_scan(state) -> str:
    """p3_pre_scan -> p3_strategy.

    HOM-158: p3_pre_scan is an LLM node — it raises on terminal failure
    rather than writing to `state["errors"]`. The pre-HOM-158 errors check
    here is therefore a no-op for LLM-origin failures and would only fire on
    historical errors from earlier nodes (poisoning routing across turns).
    Removed.
    """
    return "p3_strategy"


def route_after_strategy(state) -> str:
    """p3_strategy -> strategy_confirmed_interrupt.

    Inserts canon HR 11 approval gate before EDL selection. The interrupt
    node short-circuits if strategy was skipped upstream (no plan to confirm)
    or if the operator already approved on a prior turn.

    HOM-158: p3_strategy is an LLM node (raises on terminal failure); errors
    check removed — see `route_after_pre_scan`.
    """
    return "strategy_confirmed_interrupt"


STRATEGY_REVISION_CAP = 3


def route_after_strategy_confirmed(state) -> str:
    """strategy_confirmed_interrupt -> p3_edl_select | p3_strategy | halt | END.

    Three branches matching the interrupt node's three outcomes:
      - approved → p3_edl_select (canon path forward)
      - skipped → END (defensive)
      - otherwise (revision queued) → p3_strategy if cap not exceeded,
        halt_llm_boundary if it has been (avoid infinite loop)

    HOM-158: interrupt nodes never write `state["errors"]`; check removed.
    """
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
    """p3_edl_select -> END on skip | gate:edl_ok on success.

    HOM-158: p3_edl_select is an LLM node (raises on terminal failure);
    errors check removed.
    """
    edl = (state.get("edit") or {}).get("edl") or {}
    if edl.get("skipped"):
        return END
    return "gate_edl_ok"


def route_after_gate_with_retry(
    *,
    gate_name: str,
    on_pass: str,
    retry_node: str,
    fail_route: str,
    max_iterations: int = 3,
):
    """Build a conditional-edge router for an artifact-validation gate that
    supports a retry-with-feedback middle path.

    Three outcomes per spec §6.2:

      * pass                                → ``on_pass``
      * fail + iteration < max_iterations   → ``retry_node`` (re-run producer
        with prior violations injected via the `prior_violations_block` macro)
      * fail + iteration ≥ max_iterations   → ``fail_route`` (interrupt or halt)

    A missing record is treated as fail-with-no-iteration: route to
    ``fail_route`` rather than burning a retry on phantom state.

    The producer's ``_render_ctx`` MUST splat
    ``gate_retry_context(state, gate_name)`` into its dict so the brief can
    render the violations feedback block; see `gates._base.gate_retry_context`.
    """
    def _route(state) -> str:
        from ..gates._base import latest_gate_result
        record = latest_gate_result(state, gate_name)
        if record is None:
            return fail_route
        if record.get("passed"):
            return on_pass
        if (record.get("iteration") or 0) < max_iterations:
            return retry_node
        return fail_route

    _route.__name__ = (
        f"route_after_{gate_name.replace(':', '_').removeprefix('gate_')}_with_retry"
    )
    return _route


# HOM-147: `gate:edl_ok` adopts the generic retry helper. On failure with
# iter < 3 we re-invoke `p3_edl_select`, whose brief renders the prior
# violations via `briefs/_macros.j2 :: prior_violations_block`. Once retries
# exhaust, control still falls to `edl_failure_interrupt` so an operator can
# inspect state and resume (or abort).
route_after_edl_ok = route_after_gate_with_retry(
    gate_name="gate:edl_ok",
    on_pass="p3_render_segments",
    retry_node="p3_edl_select",
    fail_route="edl_failure_interrupt",
    max_iterations=3,
)
route_after_edl_ok.__doc__ = (
    "gate:edl_ok → p3_render_segments (pass) | p3_edl_select (fail+iter<3) | "
    "edl_failure_interrupt (fail+iter≥3 or no record). HOM-147."
)


# HOM-130: tokens that count as "operator gave up" on a failure interrupt.
# Anything else (including empty payload — the natural Studio Submit gesture
# after editing state) is treated as "retry — re-run the gate".
_ABORT_TOKENS = frozenset({"abort", "stop", "end", "give_up", "give up", "no", "n"})


def _is_abort(decision: object) -> bool:
    if isinstance(decision, str):
        return decision.strip().lower() in _ABORT_TOKENS
    if isinstance(decision, dict):
        return decision.get("abort") is True
    return False


def route_after_edl_failure_interrupt(state) -> str:
    """edl_failure_interrupt → gate_edl_ok (retry) | halt_llm_boundary (abort).

    The interrupt node captures the operator's resume payload at
    `state.edit.edl.failure_resume.action`. Abort tokens route to
    halt_llm_boundary so its notice surfaces in Studio (END would be silent).
    Anything else re-runs gate:edl_ok — which records a fresh iteration and
    either passes (operator fixed the EDL) or re-suspends here.

    HOM-158: interrupt nodes never write `state["errors"]`; check removed.
    """
    edl = (state.get("edit") or {}).get("edl") or {}
    fr = edl.get("failure_resume") or {}
    if _is_abort(fr.get("action")):
        return "halt_llm_boundary"
    return "gate_edl_ok"


def route_after_eval_failure_interrupt(state) -> str:
    """eval_failure_interrupt → gate_eval_ok (retry) | halt_llm_boundary (abort).

    Mirror of `route_after_edl_failure_interrupt`. Resume payload lives at
    `state.edit.eval.failure_resume.action`. Note: gate_eval_ok's iteration
    counter has already reached `max_iterations` by the time we land here
    (that's how `route_after_eval_ok` decides to escalate to the interrupt);
    re-running the gate post-resume increments to N+1, so a still-failing
    eval routes via `route_after_eval_ok` straight back into this interrupt
    rather than re-rendering — operator must fix and re-run, or abort.

    HOM-158: interrupt nodes never write `state["errors"]`; check removed.
    """
    eval_state = (state.get("edit") or {}).get("eval") or {}
    fr = eval_state.get("failure_resume") or {}
    if _is_abort(fr.get("action")):
        return "halt_llm_boundary"
    return "gate_eval_ok"


def route_after_render_segments(state) -> str:
    """p3_render_segments -> END on error | p3_self_eval | halt on render-skip.

    HOM-104 wires the canon Step 7 self-eval pass downstream. If render was
    skipped (e.g., upstream EDL skip), there is nothing to check; route to
    halt_llm_boundary so the existing skip-notice surfaces.

    HOM-158: p3_render_segments is deterministic (ffmpeg) — keep an
    errors check, but scope it to this predecessor so prior-turn errors
    from other nodes don't poison routing.
    """
    if _predecessor_just_failed(state, "p3_render_segments"):
        return END
    render = (state.get("edit") or {}).get("render") or {}
    if render.get("skipped"):
        return "halt_llm_boundary"
    return "p3_self_eval"


def route_after_self_eval(state) -> str:
    """p3_self_eval -> END on skip | gate_eval_ok on success.

    HOM-158: p3_self_eval is an LLM node — raises on terminal failure.
    Errors check removed (LLM raises do not commit writes).
    """
    report = (state.get("edit") or {}).get("eval") or {}
    if report.get("skipped"):
        return "halt_llm_boundary"
    return "gate_eval_ok"


# HOM-147: gate:eval_ok was the prior-art retry router; migrate to the
# generic helper. Behavior is identical (pass→persist, fail+iter<3→re-render,
# otherwise→eval_failure_interrupt).
route_after_eval_ok = route_after_gate_with_retry(
    gate_name="gate:eval_ok",
    on_pass="p3_persist_session",
    retry_node="p3_render_segments",
    fail_route="eval_failure_interrupt",
    max_iterations=3,
)
route_after_eval_ok.__doc__ = (
    "gate:eval_ok → p3_persist_session (pass) | p3_render_segments (fail+iter<3) | "
    "eval_failure_interrupt (otherwise). HOM-147 — was the prior-art pattern."
)


def route_after_persist_session(state) -> str:
    """p3_persist_session -> END on hard error | p3_review_interrupt otherwise.

    HOM-146: replaces the prior `→ halt_llm_boundary` terminus with a linear
    edge into the Phase-3-review interrupt checkpoint. After the operator
    approves, routing flows on to `glue_remap_transcript` and Phase 4 — a
    single linear pass through both phases instead of two separate Submits.

    HOM-158: p3_persist_session is an LLM node (raises on terminal failure);
    errors check removed.
    """
    return "p3_review_interrupt"


def route_after_p3_review_interrupt(state) -> str:
    """p3_review_interrupt → glue_remap_transcript | halt_llm_boundary | END.

    Conservative routing: `approved is True` is required to advance into
    Phase 4. Aborted (or any non-approved state — e.g. injected via
    update_state) routes to halt so the boundary's notice surfaces.
    Errors → END defensively. The node itself always sets one of the two
    flags in normal flow; this asymmetric default exists to keep replay /
    state-injection scenarios from silently bypassing the checkpoint.

    HOM-158: interrupt nodes never write `state["errors"]`; check removed.
    """
    review = ((state.get("edit") or {}).get("review") or {}).get("phase3") or {}
    if review.get("approved") is True:
        return "glue_remap_transcript"
    return "halt_llm_boundary"


def route_after_remap(state) -> str:
    """glue_remap_transcript → END | p4_scaffold (skip_phase4 = idempotent).

    HOM-158: glue_remap_transcript is deterministic — keep an errors check
    scoped to this predecessor.
    """
    if _predecessor_just_failed(state, "glue_remap_transcript"):
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

    HOM-158: p4_scaffold is deterministic — errors check scoped to this
    predecessor.
    """
    if _predecessor_just_failed(state, "p4_scaffold"):
        return END
    return "p4_design_system"


def route_after_design_system(state) -> str:
    """p4_design_system → END on skip | gate:design_ok on success.

    HOM-158: p4_design_system is an LLM node (raises on terminal failure);
    errors check removed.
    """
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

    HOM-158: p4_prompt_expansion is an LLM node (raises on terminal failure);
    errors check removed.
    """
    expansion = (state.get("compose") or {}).get("expansion") or {}
    if expansion.get("skipped"):
        return END
    return "p4_plan"


def route_after_plan(state) -> str:
    """p4_plan → END on skip | gate:plan_ok on success.

    HOM-158: p4_plan is an LLM node (raises on terminal failure);
    errors check removed.
    """
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

    HOM-158: p4_catalog_scan is deterministic — errors check scoped to this
    predecessor.
    """
    if _predecessor_just_failed(state, "p4_catalog_scan"):
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

    HOM-158: p4_captions_layer is an LLM node (raises on terminal failure);
    errors check removed.
    """
    plan = (state.get("compose") or {}).get("plan") or {}
    if plan.get("beats"):
        return "p4_dispatch_beats"
    return "p4_assemble_index"


def route_after_assemble_index(state) -> str:
    """p4_assemble_index → END on error | gate_lint | halt_llm_boundary.

    HOM-127 wires the post-assemble gate cluster — the success leg now
    enters the chain at `gate_lint`. A skipped assemble (e.g. missing
    scenes) still routes to halt so the boundary's notice surfaces;
    there is nothing to lint or preview.

    HOM-158: p4_assemble_index is deterministic — errors check scoped to
    this predecessor.
    """
    if _predecessor_just_failed(state, "p4_assemble_index"):
        return END
    assemble = (state.get("compose") or {}).get("assemble") or {}
    if assemble.get("skipped"):
        return "halt_llm_boundary"
    return "gate_lint"


# HOM-148: post-assemble gate cluster adopts the generic retry helper from
# HOM-147. Each gate routes:
#   pass                     → next gate in chain
#   fail + iter < 3          → p4_redispatch_beat (re-author offending scene)
#                              → p4_assemble_index → re-run the gate
#   fail + iter >= 3         → halt_llm_boundary (notice surfaces violations)
#
# Chain order matches spec §4.3: gate_lint → gate_validate → gate_inspect →
# gate_design_adherence → gate_animation_map → gate_snapshot →
# gate_captions_track → p4_persist_session. Cheap deterministic checks first
# (lint), browser-heavy headless checks last (snapshot, captions_track).
#
# Cap is **per-gate**, not per-cluster. Each gate maintains its own
# `_iteration` counter (gates._base.Gate._iteration counts records for the
# named gate only). Worst-case redispatch invocations across one cluster
# pass = 7 gates × 2 retries = 14 LLM calls; in practice early failures halt
# the chain before later gates accumulate retries. Per-cluster cap is a v6
# concern (HOM-78). Spec §6.2 reference.

route_after_lint = route_after_gate_with_retry(
    gate_name="gate:lint",
    on_pass="gate_validate",
    retry_node="p4_redispatch_beat",
    fail_route="halt_llm_boundary",
    max_iterations=3,
)
route_after_validate = route_after_gate_with_retry(
    gate_name="gate:validate",
    on_pass="gate_inspect",
    retry_node="p4_redispatch_beat",
    fail_route="halt_llm_boundary",
    max_iterations=3,
)
route_after_inspect = route_after_gate_with_retry(
    gate_name="gate:inspect",
    on_pass="gate_design_adherence",
    retry_node="p4_redispatch_beat",
    fail_route="halt_llm_boundary",
    max_iterations=3,
)
route_after_design_adherence = route_after_gate_with_retry(
    gate_name="gate:design_adherence",
    on_pass="gate_animation_map",
    retry_node="p4_redispatch_beat",
    fail_route="halt_llm_boundary",
    max_iterations=3,
)
route_after_animation_map = route_after_gate_with_retry(
    gate_name="gate:animation_map",
    on_pass="gate_snapshot",
    retry_node="p4_redispatch_beat",
    fail_route="halt_llm_boundary",
    max_iterations=3,
)
route_after_snapshot = route_after_gate_with_retry(
    gate_name="gate:snapshot",
    on_pass="gate_captions_track",
    retry_node="p4_redispatch_beat",
    fail_route="halt_llm_boundary",
    max_iterations=3,
)
route_after_captions_track = route_after_gate_with_retry(
    gate_name="gate:captions_track",
    on_pass="p4_persist_session",
    retry_node="p4_redispatch_beat",
    fail_route="halt_llm_boundary",
    max_iterations=3,
)


def route_after_p4_persist_session(state) -> str:
    """p4_persist_session → END on hard error | studio_launch otherwise.

    A persist skip or sub-agent failure is non-fatal — the Session block is
    a memory aid for the next run, not load-bearing for the preview.

    HOM-158: p4_persist_session is an LLM node — terminal failures raise
    (RetryPolicy applies, then pregel surfaces the exception). Errors check
    removed; if the node returns at all, persist either succeeded or skipped
    cleanly.
    """
    return "studio_launch"


def route_after_studio_launch(state) -> str:
    """studio_launch → END on error | gate_static_guard otherwise.

    HOM-158: studio_launch is deterministic — errors check scoped to this
    predecessor.
    """
    if _predecessor_just_failed(state, "studio_launch"):
        return END
    return "gate_static_guard"


def route_after_static_guard(state) -> str:
    """gate:static_guard → halt_llm_boundary on pass or fail.

    v4 ends here. Failures surface in `gate_results` for operator review;
    HITL `user_review` (which would re-route on fail) is HOM-78/v6.
    """
    return "halt_llm_boundary"
