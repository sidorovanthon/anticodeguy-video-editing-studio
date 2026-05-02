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
    return {
        "notices": [
            "v1 halt: `final.mp4` missing; Phase 3 (`p3_inventory`+) requires LLM nodes (v3+)",
        ],
    }
