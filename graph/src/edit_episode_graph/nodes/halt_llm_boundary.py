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
    if assemble_state.get("skipped") or assemble_state.get("assembled_at"):
        if assemble_state.get("skipped"):
            reason = assemble_state.get("skip_reason") or "no reason given"
            msg = (
                f"v4 halt: p4_assemble_index skipped: {reason}; per-beat fan-out + "
                "captions block are future tickets (HOM-122..HOM-123)"
            )
        else:
            n = len(assemble_state.get("beat_names") or [])
            msg = (
                f"v4 halt: scenes assembled from compositions/*.html into root index.html "
                f"({n} scene(s); hard-cut between scenes — transitions node ships under "
                "HOM-77/v5); next gate cluster ships in HOM-124"
            )
        return {"notices": [msg]}
    if catalog_state:
        n_b = len(catalog_state.get("blocks") or [])
        n_c = len(catalog_state.get("components") or [])
        msg = (
            f"v4 halt: catalog scanned ({n_b} block(s), {n_c} component(s)); next is "
            "p4_assemble_index"
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
