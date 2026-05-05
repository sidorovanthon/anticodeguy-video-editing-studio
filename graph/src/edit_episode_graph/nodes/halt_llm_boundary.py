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
    captions_state = compose_state.get("captions") or {}
    captions_block_path = compose_state.get("captions_block_path") or captions_state.get(
        "captions_block_path"
    )

    def _captions_summary() -> str:
        if assemble_state.get("captions_included"):
            return "captions inlined"
        if captions_state.get("skipped"):
            reason = captions_state.get("skip_reason") or "no reason given"
            return f"captions skipped ({reason})"
        if captions_block_path:
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
    if cluster_supersedes_static_guard:
        n_v = len(cluster_failure.get("violations") or [])
        gate_name = cluster_failure.get("gate")
        msg = (
            f"v4 halt: {gate_name} FAILED ({n_v} violation(s)) — see gate_results; "
            f"{_persist_summary()}; "
            "v4-sans-HITL routes post-assemble gate failures here, "
            "retry-with-feedback is HOM-77/v5"
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
                f"{_persist_summary()}; "
                "next is HITL user_review (HOM-78/v6) → p4_final_render"
            )
        else:
            n_v = len(static_guard_record.get("violations") or [])
            msg = (
                f"v4 halt: gate:static_guard FAILED ({n_v} violation(s)) — see gate_results; "
                f"{_persist_summary()}; "
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
            n = len(assemble_state.get("beat_names") or [])
            msg = (
                f"v4 halt: scenes assembled from compositions/*.html into root index.html "
                f"({n} scene(s), {_captions_summary()}; hard-cut between scenes — "
                "transitions node ships under HOM-77/v5); studio_launch did not "
                "record a static_guard result — see errors[]"
            )
        return {"notices": [msg]}
    if catalog_state:
        # HOM-123: captions are authored after catalog. If we halt at the
        # catalog stage with no captions yet, the next reachable artifact is
        # `p4_captions_layer`; otherwise it's `p4_assemble_index`.
        next_artifact = (
            "p4_assemble_index" if captions_block_path else "p4_captions_layer"
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
    if eval_state.get("passed") and render_state.get("final_mp4"):
        n = render_state.get("n_segments") or 0
        n_issues = len(eval_state.get("issues") or [])
        msg = (
            f"v3 halt: self-eval passed ({n} segment(s), {n_issues} note(s)); "
            "downstream persist/glue are future tickets (HOM-105..107)"
        )
        return {"notices": [msg]}
    if render_state.get("final_mp4"):
        n = render_state.get("n_segments") or 0
        delta = render_state.get("delta_ms")
        cached = render_state.get("cached")
        delta_part = f" (Δ {delta}ms vs EDL)" if delta is not None else ""
        cached_part = " [cached]" if cached else ""
        msg = (
            f"v3 halt: final.mp4 rendered ({n} segment(s)){cached_part}{delta_part}; "
            "downstream self_eval/persist/glue are future tickets (HOM-104..107)"
        )
    elif edl_state.get("ranges"):
        n = len(edl_state.get("ranges") or [])
        msg = f"v3 halt: EDL passed gate:edl_ok ({n} range(s)); render requires p3_render_segments (future)"
    elif pre_scan_state.get("slips") is not None and not pre_scan_state.get("skipped"):
        msg = (
            "v2 halt: pre_scan ran ({n} slip(s) recorded); EDL + render require v3 LLM nodes"
            .format(n=len(pre_scan_state.get("slips") or []))
        )
    else:
        msg = "v1 halt: `final.mp4` missing; Phase 3 (`p3_inventory`+) requires LLM nodes (v3+)"
    return {"notices": [msg]}
