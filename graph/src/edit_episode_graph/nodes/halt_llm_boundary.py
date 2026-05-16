"""halt_llm_boundary node — terminal marker when the next required phase is LLM-only.

v1 covers the deterministic surface (`isolate_audio`, glue, scaffold). When
`skip_phase3?` returns "no" — meaning `final.mp4` does not yet exist — the
deterministic graph cannot proceed: Phase 3 is gated on `p3_inventory` etc.,
all of which are LLM nodes deferred to v2/v3.

Rather than route silently to END, this node appends a `notices` entry so
Studio (and headless callers reading state) can see explicitly *why* the run
halted and what would unblock it. Same pattern as the post-`p4_scaffold`
notice in `p4_scaffold.py` — a small marker, not an error.
"""

import re

from .._paths import EpisodePaths


def _final_mp4_exists(state: dict) -> bool:
    """HOM-223: `render.final_mp4` removed from state writes; derive from disk."""
    slug = state.get("slug")
    if not slug:
        return False
    return EpisodePaths(slug).final_mp4_path.exists()


def halt_llm_boundary_node(state):
    edit = state.get("edit") or {}
    edl_state = edit.get("edl") or {}
    render_state = edit.get("render") or {}
    eval_state = edit.get("eval") or {}
    pre_scan_state = edit.get("pre_scan") or {}
    compose_state = state.get("compose") or {}
    plan_state = compose_state.get("plan") or {}
    expansion_state = compose_state.get("expansion") or {}
    design_state = compose_state.get("design") or {}
    catalog_state = compose_state.get("catalog") or {}
    assemble_state = compose_state.get("assemble") or {}
    gate_results = state.get("gate_results") or []
    plan_record = next(
        (r for r in reversed(gate_results) if r.get("gate") == "gate:plan_ok"),
        None,
    )
    # Order matters: assemble runs after catalog runs after plan-gate. Check
    # the latest reachable artifact first so the notice always names the most
    # advanced phase actually completed. We gate on the two known terminal
    # markers (skipped or assembled_at) rather than dict truthiness so a
    # future partial-write that leaves an unrecognized assemble shape doesn't
    # silently format a misleading "assembled" notice.
    transitions_state = compose_state.get("transitions") or {}
    captions_state = compose_state.get("captions") or {}
    # HOM-224: identity-only state — `compose.captions_block_path` /
    # `compose.captions.captions_block_path` echoes are gone. Probe disk
    # via EpisodePaths(slug). When no slug, treat as absent.
    slug = state.get("slug")
    captions_on_disk = bool(
        slug and EpisodePaths(slug).captions_block_path.is_file()
    )

    def _captions_summary() -> str:
        if assemble_state.get("captions_included"):
            return "captions inlined"
        if captions_state.get("skipped"):
            reason = captions_state.get("skip_reason") or "no reason given"
            return f"captions skipped ({reason})"
        if captions_on_disk:
            return "captions written but not inlined"
        return "captions absent"

    persist_state = compose_state.get("persist") or {}

    def _persist_summary() -> str:
        if compose_state.get("session_persisted"):
            n = persist_state.get("session_n")
            n_part = f" #{n}" if n else ""
            return f"Phase 4 Session block persisted{n_part}"
        if persist_state.get("skipped"):
            reason = persist_state.get("skip_reason") or "no reason given"
            return f"Phase 4 Session block skipped ({reason})"
        return "Phase 4 Session block: not yet persisted"

    # HOM-238: p4_materialize_disk lives between p4_persist_session and
    # studio_launch (no-op writer in Step C of HOM-230). Surface its
    # status next to persist's so the operator sees the full post-persist
    # chain. HOM-255 / Step D1 activated atomic writes — ``files_written``
    # carries the per-file count actually changed (idempotent skips
    # excluded). Pre-D1 ``materialized_at`` ≅ "no-op confirmed the body
    # shape"; post-D1 it ≅ "atomic writes happened at this instant".
    materialize_state = compose_state.get("materialize") or {}

    def _materialize_summary() -> str:
        if materialize_state.get("materialized_at"):
            files_written = materialize_state.get("files_written") or []
            count = len(files_written) if isinstance(files_written, list) else 0
            return (
                "Phase 4 artifacts materialized at "
                f"{materialize_state['materialized_at']} "
                f"({count} file{'s' if count != 1 else ''} written)"
            )
        if materialize_state.get("skipped"):
            reason = materialize_state.get("skip_reason") or "no reason given"
            return f"Phase 4 materializer skipped ({reason})"
        return "Phase 4 artifacts not yet materialized"

    # HOM-127: post-assemble gate cluster (lint → validate → inspect →
    # design_adherence → animation_map → snapshot → captions_track) sits
    # between p4_assemble_index and p4_persist_session. A failure on any
    # of these halts the run before studio_launch fires; surface which
    # gate failed and how many violations so the operator sees the
    # specific blocker without digging into gate_results.
    _POST_ASSEMBLE_GATES = (
        "gate:lint",
        "gate:validate",
        "gate:inspect",
        "gate:design_adherence",
        "gate:animation_map",
        "gate:snapshot",
        "gate:captions_track",
    )
    cluster_failure = next(
        (
            r for r in reversed(gate_results)
            if r.get("gate") in _POST_ASSEMBLE_GATES and not r.get("passed")
        ),
        None,
    )

    static_guard_record = next(
        (r for r in reversed(gate_results) if r.get("gate") == "gate:static_guard"),
        None,
    )
    # On a fresh thread (the v4-sans-HITL norm) `static_guard_record` is
    # None whenever a cluster gate halts the run — the cluster sits
    # upstream of studio_launch. On a reused thread a prior run's
    # static_guard record can survive into a re-run that fails earlier;
    # compare ISO timestamps so the cluster failure only wins when it's
    # genuinely the more recent halt cause.
    cluster_supersedes_static_guard = cluster_failure is not None and (
        static_guard_record is None
        or (cluster_failure.get("timestamp") or "")
        > (static_guard_record.get("timestamp") or "")
    )
    # HOM-130: Phase 3 failure interrupts (edl + eval) are now resumable.
    # On abort, routing lands here so the operator sees an explicit notice
    # instead of a silent END. Reuses `_routing._is_abort` to keep the
    # abort-detection contract single-sourced.
    from ._routing import _is_abort

    def _resume_aborted(failure_state: dict) -> bool:
        return _is_abort((failure_state.get("failure_resume") or {}).get("action"))

    if _resume_aborted(edl_state):
        record = next(
            (r for r in reversed(gate_results) if r.get("gate") == "gate:edl_ok"),
            None,
        )
        n_v = len(record.get("violations") or []) if record else 0
        iter_n = (record or {}).get("iteration")
        msg = (
            f"v3 halt: gate:edl_ok FAILED (iter {iter_n}, {n_v} violation(s)) — "
            "operator aborted the resume-loop; see gate_results"
        )
        return {"notices": [msg]}
    if _resume_aborted(eval_state):
        record = next(
            (r for r in reversed(gate_results) if r.get("gate") == "gate:eval_ok"),
            None,
        )
        n_v = len(record.get("violations") or []) if record else 0
        iter_n = (record or {}).get("iteration")
        msg = (
            f"v3 halt: gate:eval_ok FAILED (iter {iter_n}, {n_v} violation(s)) — "
            "operator aborted the resume-loop; see gate_results"
        )
        return {"notices": [msg]}
    # HOM-146: Phase 3 → Phase 4 review interrupt also routes here on abort.
    # Without this branch the operator's explicit abort would surface as the
    # stale "v3 halt: final.mp4 rendered" notice — unrelated to their action.
    review_phase3 = (edit.get("review") or {}).get("phase3") or {}
    if review_phase3.get("aborted"):
        msg = (
            "v3 halt: Phase 3 review aborted by operator — re-Submit on the "
            "same slug to restart at p3_review_interrupt; final.mp4 is intact"
        )
        return {"notices": [msg]}
    if cluster_supersedes_static_guard:
        n_v = len(cluster_failure.get("violations") or [])
        gate_name = cluster_failure.get("gate")
        iter_n = cluster_failure.get("iteration") or 0
        # HOM-204: gate:animation_map is advisory — its `passed=False`
        # path now means infrastructure failure (helper missing, exit
        # != 0, JSON unparseable), not authoring violations. Findings
        # live under `advisory_findings` and never halt the run, but
        # when this halt fires for the animation-map gate (infra
        # failure), surface the advisory counts too so the operator
        # sees what the helper would have reported alongside the
        # infrastructure issue.
        # HOM-205: keep the breakdown shape aligned with the gate's own
        # canonical notice (see gates/animation_map.py §"Notice format")
        # — "N advisory finding(s) (always_fix: a, dead_zones: d,
        # pending_classify: p)". Two sites, same shape; if one drifts,
        # update both.
        advisory_part = ""
        if gate_name == "gate:animation_map":
            advisory = cluster_failure.get("advisory_findings") or {}
            n_always = len(advisory.get("always_fix") or [])
            n_dead = len(advisory.get("dead_zones") or [])
            n_pending = len(advisory.get("pending_classify") or [])
            n_findings = n_always + n_dead + n_pending
            if n_findings:
                advisory_part = (
                    f"; {n_findings} advisory finding(s) "
                    f"(always_fix: {n_always}, dead_zones: {n_dead}, "
                    f"pending_classify: {n_pending})"
                )
        # HOM-212: dead-zone-only blocking is structural — dead zones
        # live on the root timeline (gaps between scenes), not inside
        # any individual beat composition. `p4_redispatch_beat` cannot
        # fix them; the gate halts on the first record without entering
        # the retry loop. The cluster-default notice ("retry-with-feedback
        # exhausted (max 3 attempts)") would mislead the operator into
        # thinking 3 redispatches already ran. Branch on the prefix the
        # gate emits (`gates/animation_map.py::_extract_flags` —
        # "blocking dead zone — …"); if EVERY blocking finding is a
        # dead zone string, route to a structural-only notice that
        # points at p4_assemble_index (root timeline = scene durations).
        # If even one non-dead-zone blocking finding is present, the
        # mixed case keeps the iter-exhausted text — beat-actionable
        # findings did exhaust their retry budget.
        if gate_name == "gate:animation_map":
            blocking_findings = cluster_failure.get("blocking_findings") or []
            if blocking_findings and all(
                s.startswith("blocking dead zone") for s in blocking_findings
            ):
                worst_part = ""
                # Surface the worst dead-zone duration parsed back from the
                # canonical violation string ("max duration X.Xs exceeds
                # threshold Y.Ys"). Best-effort; on parse failure fall
                # through to the generic "structural" message.
                m = re.search(
                    r"max duration ([\d.]+)s exceeds threshold ([\d.]+)s",
                    blocking_findings[0],
                )
                if m:
                    worst_part = (
                        f"dead zone {m.group(1)}s > threshold "
                        f"{m.group(2)}s; "
                    )
                msg = (
                    f"v4 halt: {gate_name} FAILED at iter {iter_n} "
                    f"({n_v} violation(s)){advisory_part} — "
                    f"{worst_part}structural — adjust scene durations on "
                    "root timeline (p4_assemble_index concern); "
                    f"{_persist_summary()}; {_materialize_summary()}; "
                    "dead zones are not beat-actionable so "
                    "p4_redispatch_beat is not invoked"
                )
                return {"notices": [msg]}
        msg = (
            f"v4 halt: {gate_name} FAILED at iter {iter_n} ({n_v} violation(s)){advisory_part} — "
            "see gate_results; "
            f"{_persist_summary()}; {_materialize_summary()}; "
            "p4_redispatch_beat retry-with-feedback exhausted (HOM-148, max 3 "
            "attempts); HITL user_review for cluster-gate failures is HOM-78/v6"
        )
        return {"notices": [msg]}
    if static_guard_record is not None:
        port = compose_state.get("preview_port")
        port_part = f" on port {port}" if port else ""
        if static_guard_record.get("passed"):
            extra = ""
            if static_guard_record.get("canon_video_audio_artifact"):
                extra = " (canon Video/Audio artifact — apply data-has-audio=\"false\")"
            msg = (
                f"v4 halt: studio launched{port_part}, gate:static_guard PASSED{extra}; "
                f"{_persist_summary()}; {_materialize_summary()}; "
                "next is HITL user_review (HOM-78/v6) → p4_final_render"
            )
        else:
            n_v = len(static_guard_record.get("violations") or [])
            msg = (
                f"v4 halt: gate:static_guard FAILED ({n_v} violation(s)) — see gate_results; "
                f"{_persist_summary()}; {_materialize_summary()}; "
                "v4-sans-HITL routes failures here, retry-with-feedback is HOM-78/v6"
            )
        return {"notices": [msg]}
    if assemble_state.get("skipped") or assemble_state.get("assembled_at"):
        if assemble_state.get("skipped"):
            reason = assemble_state.get("skip_reason") or "no reason given"
            msg = (
                f"v4 halt: p4_assemble_index skipped: {reason}; {_captions_summary()}; "
                "p4_dispatch_beats + p4_beat (HOM-133/134) populate "
                "compositions/<scene>.html; studio_launch is bypassed — "
                "nothing assembled to preview"
            )
        else:
            # Reachable if studio_launch errored (routes to END but the halt
            # branch can still be hit via earlier topology paths). On the
            # happy path the static_guard branch above fires first.
            # HOM-137: canonical transitions node now wires after assemble;
            # surface its outcome (authored / skipped / not-yet-run) so the
            # operator sees whether the root timeline carries crossfades or
            # the legacy hard-cut.
            n = len(assemble_state.get("beat_names") or [])
            if transitions_state.get("authored_at"):
                n_t = transitions_state.get("n_transitions") or 0
                mechs = transitions_state.get("mechanisms") or []
                mech_summary = "/".join(sorted(set(mechs))) if mechs else "none"
                trans_part = (
                    f"transitions authored ({n_t} on root timeline, "
                    f"mechanisms: {mech_summary})"
                )
            elif transitions_state.get("skipped"):
                reason = transitions_state.get("skip_reason") or "no reason given"
                trans_part = f"transitions skipped ({reason})"
            else:
                trans_part = "transitions not yet authored (p4_transitions pending)"
            msg = (
                f"v4 halt: scenes assembled from state scene bodies into root index.html "
                f"(compose.index_html, HOM-236 state-first; dual-written to disk) "
                f"({n} scene(s), {_captions_summary()}, {trans_part}); "
                "next is gate cluster (lint → validate → inspect → "
                "design_adherence → animation_map → snapshot → captions_track) "
                "→ p4_persist_session → p4_materialize_disk → studio_launch; "
                "studio_launch did not record a static_guard result — see errors[]"
            )
        return {"notices": [msg]}
    if catalog_state:
        # HOM-123: captions are authored after catalog. If we halt at the
        # catalog stage with no captions yet, the next reachable artifact is
        # `p4_captions_layer`; otherwise it's `p4_assemble_index`.
        next_artifact = (
            "p4_assemble_index" if captions_on_disk else "p4_captions_layer"
        )
        n_b = len(catalog_state.get("blocks") or [])
        n_c = len(catalog_state.get("components") or [])
        msg = (
            f"v4 halt: catalog scanned ({n_b} block(s), {n_c} component(s), "
            f"{_captions_summary()}); next is {next_artifact}"
        )
        return {"notices": [msg]}
    if plan_record is not None:
        n_beats = len(plan_state.get("beats") or [])
        if plan_record.get("passed"):
            msg = (
                f"v4 halt: gate:plan_ok passed ({n_beats} beat(s)); next is "
                "p4_catalog_scan + p4_assemble_index"
            )
        else:
            n_v = len(plan_record.get("violations") or [])
            msg = (
                f"v4 halt: gate:plan_ok FAILED ({n_v} violation(s)); see gate_results — "
                "v4-sans-HITL routes failures here, retry-with-violations is HOM-77"
            )
        return {"notices": [msg]}
    if plan_state.get("skipped"):
        # Reached when p4_plan emitted a skip dict (missing inputs). Surface
        # the skip reason directly — without this branch the notice would
        # fall through to v3/v1 messages, masking the Phase 4 progress.
        reason = plan_state.get("skip_reason") or "no reason given"
        msg = f"v4 halt: p4_plan skipped: {reason}"
        return {"notices": [msg]}
    if expansion_state.get("skipped"):
        reason = expansion_state.get("skip_reason") or "no reason given"
        msg = f"v4 halt: p4_prompt_expansion skipped: {reason}"
        return {"notices": [msg]}
    if design_state.get("skipped"):
        reason = design_state.get("skip_reason") or "no reason given"
        msg = f"v4 halt: p4_design_system skipped: {reason}"
        return {"notices": [msg]}
    final_mp4_present = _final_mp4_exists(state)
    if eval_state.get("passed") and final_mp4_present:
        n = render_state.get("n_segments") or 0
        n_issues = len(eval_state.get("issues") or [])
        msg = (
            f"v3 halt: self-eval passed ({n} segment(s), {n_issues} note(s)); "
            "Phase 3 complete; next is p3_persist_session → p3_review_interrupt → "
            "Phase 4 chain (design → expansion → plan → catalog → assemble)"
        )
        return {"notices": [msg]}
    if final_mp4_present:
        n = render_state.get("n_segments") or 0
        delta = render_state.get("delta_ms")
        cached = render_state.get("cached")
        delta_part = f" (Δ {delta}ms vs EDL)" if delta is not None else ""
        cached_part = " [cached]" if cached else ""
        msg = (
            f"v3 halt: final.mp4 rendered ({n} segment(s)){cached_part}{delta_part}; "
            "next is p3_self_eval → gate:eval_ok → p3_persist_session"
        )
    elif edl_state.get("ranges"):
        n = len(edl_state.get("ranges") or [])
        msg = (
            f"v3 halt: EDL passed gate:edl_ok ({n} range(s)); "
            "next is p3_render_segments → p3_self_eval"
        )
    elif pre_scan_state.get("slips") is not None and not pre_scan_state.get("skipped"):
        msg = (
            "v2 halt: pre_scan ran ({n} slip(s) recorded); next is p3_strategy → "
            "strategy_confirmed_interrupt → p3_edl_select"
            .format(n=len(pre_scan_state.get("slips") or []))
        )
    else:
        msg = (
            "v1 halt: `final.mp4` missing; next is p3_inventory → p3_pre_scan → "
            "p3_strategy (Phase 3 LLM chain)"
        )
    return {"notices": [msg]}
