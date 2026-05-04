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
