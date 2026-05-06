"""Graph assembly entry point.

`langgraph.json` points at the module-level `graph` object below. Re-importing
this module rebuilds it; `langgraph dev` does so on every code change.

v1 topology (spec §4.1, §8 — LLM-free coverage):

    pickup ─┬─ idle/error ──────────────────────────────────► END
            │
            └─ skip_phase2? ┬─ tagged ───────────────────────┐
                            │                                ▼
                            └─ untagged ─► isolate_audio ─► preflight_canon
                                                                ▼
                            skip_phase3? ┬─ final.mp4 ─► glue_remap_transcript
                                          │                     ▼
                                          │   skip_phase4? ┬─ idx.html ─► END
                                          │                 ▼
                                          │              p4_scaffold ─► END (notice)
                                          │
                                          ├─ takes_packed.md ─► p3_pre_scan ─► p3_strategy ─► p3_edl_select ─► gate_edl_ok ┬─ pass ─► p3_render_segments ─► p3_self_eval ─► gate_eval_ok ┬─ pass ─► p3_persist_session ─► p3_review_interrupt (HITL) ─► glue_remap_transcript ─► … (Phase 4)
                                          │                                                                                   │                                                              ├─ fail+iter<3 ─► p3_render_segments
                                          │                                                                                   │                                                              └─ fail+iter≥3 ─► eval_failure_interrupt (HITL) ─► END
                                          │                                                                                   └─ fail ─► edl_failure_interrupt (HITL suspend) ─► END
                                          └─ no inventory ─► p3_inventory ┬─ error ─► END
                                                                          └─ ok ─► p3_pre_scan ─► p3_strategy ─► p3_edl_select ─► gate_edl_ok ─► …
"""

from pathlib import Path

from langgraph.cache.sqlite import SqliteCache
from langgraph.graph import END, StateGraph
from langgraph.types import RetryPolicy

from ._paths import repo_root
from .backends._types import BackendTimeout

# HOM-158: native LangGraph RetryPolicy
# (https://langchain-ai.github.io/langgraph/reference/types/#langgraph.types.RetryPolicy).
# `_llm.py` raises `AllBackendsExhausted` on terminal failure (per HOM-158
# contract change); pregel applies this policy on every Exception subclass
# matched by `retry_on`. We retry only `BackendTimeout` — auth/CLI/schema
# errors are deterministic and would just burn the same dollar twice.
# `max_attempts=2` = one retry on top of the original call, since the LLM
# subprocess timeout is already 240–300s on Opus-tier nodes; budgeting a
# second 5-minute wait is enough to ride out a Windows shim hiccup without
# creating a 30-minute hang on a permanently sick backend. cfg-fingerprint
# (HOM-157) handles cross-thread recovery once an operator bumps timeout
# or model.
_LLM_RETRY_POLICY = RetryPolicy(
    max_attempts=2,
    retry_on=(BackendTimeout,),
)
from .gates.animation_map import animation_map_gate_node
from .gates.captions_track import captions_track_gate_node
from .gates.design_adherence import design_adherence_gate_node
from .gates.design_ok import design_ok_gate_node
from .gates.edl_ok import edl_ok_gate_node
from .gates.eval_ok import eval_ok_gate_node
from .gates.inspect import inspect_gate_node
from .gates.lint import lint_gate_node
from .gates.plan_ok import plan_ok_gate_node
from .gates.snapshot import snapshot_gate_node
from .gates.static_guard import static_guard_gate_node
from .gates.validate import validate_gate_node
from .nodes._routing import (
    route_after_animation_map,
    route_after_assemble_index,
    route_after_captions_layer,
    route_after_captions_track,
    route_after_catalog_scan,
    route_after_design_adherence,
    route_after_design_ok,
    route_after_design_system,
    route_after_edl_failure_interrupt,
    route_after_edl_ok,
    route_after_edl_select,
    route_after_eval_failure_interrupt,
    route_after_eval_ok,
    route_after_inspect,
    route_after_inventory,
    route_after_lint,
    route_after_p3_review_interrupt,
    route_after_p4_persist_session,
    route_after_persist_session,
    route_after_pickup,
    route_after_plan,
    route_after_plan_ok,
    route_after_preflight,
    route_after_pre_scan,
    route_after_prompt_expansion,
    route_after_remap,
    route_after_render_segments,
    route_after_scaffold,
    route_after_self_eval,
    route_after_snapshot,
    route_after_static_guard,
    route_after_strategy,
    route_after_strategy_confirmed,
    route_after_studio_launch,
    route_after_validate,
)
from .nodes.edl_failure_interrupt import edl_failure_interrupt_node
from .nodes.eval_failure_interrupt import eval_failure_interrupt_node
from .nodes.glue_remap_transcript import (
    CACHE_POLICY as glue_remap_transcript_cache_policy,
    glue_remap_transcript_node,
)
from .nodes.halt_llm_boundary import halt_llm_boundary_node
from .nodes.isolate_audio import (
    CACHE_POLICY as isolate_audio_cache_policy,
    isolate_audio_node,
)
from .nodes.p3_edl_select import (
    CACHE_POLICY as p3_edl_select_cache_policy,
    p3_edl_select_node,
)
from .nodes.p3_inventory import (
    CACHE_POLICY as p3_inventory_cache_policy,
    p3_inventory_node,
)
from .nodes.p3_pre_scan import (
    CACHE_POLICY as p3_pre_scan_cache_policy,
    p3_pre_scan_node,
)
from .nodes.p3_render_segments import (
    CACHE_POLICY as p3_render_segments_cache_policy,
    p3_render_segments_node,
)
from .nodes.p3_persist_session import (
    CACHE_POLICY as p3_persist_session_cache_policy,
    p3_persist_session_node,
)
from .nodes.p3_review_interrupt import p3_review_interrupt_node
from .nodes.p3_self_eval import (
    CACHE_POLICY as p3_self_eval_cache_policy,
    p3_self_eval_node,
)
from .nodes.p3_strategy import (
    CACHE_POLICY as p3_strategy_cache_policy,
    p3_strategy_node,
)
from .nodes.p4_assemble_index import (
    CACHE_POLICY as p4_assemble_index_cache_policy,
    p4_assemble_index_node,
)
from .nodes.p4_catalog_scan import (
    CACHE_POLICY as p4_catalog_scan_cache_policy,
    p4_catalog_scan_node,
)
from .nodes.p4_beat import (
    CACHE_POLICY as p4_beat_cache_policy,
    p4_beat_node,
)
from .nodes.p4_captions_layer import (
    CACHE_POLICY as p4_captions_layer_cache_policy,
    p4_captions_layer_node,
)
from .nodes.p4_dispatch_beats import p4_dispatch_beats_node
from .nodes.p4_design_system import (
    CACHE_POLICY as p4_design_system_cache_policy,
    p4_design_system_node,
)
from .nodes.p4_plan import (
    CACHE_POLICY as p4_plan_cache_policy,
    p4_plan_node,
)
from .nodes.p4_persist_session import (
    CACHE_POLICY as p4_persist_session_cache_policy,
    p4_persist_session_node,
)
from .nodes.p4_prompt_expansion import (
    CACHE_POLICY as p4_prompt_expansion_cache_policy,
    p4_prompt_expansion_node,
)
from .nodes.p4_redispatch_beat import p4_redispatch_beat_node
from .nodes.p4_scaffold import (
    CACHE_POLICY as p4_scaffold_cache_policy,
    p4_scaffold_node,
)
from .nodes.pickup import pickup_node
from .nodes.preflight_canon import preflight_canon_node
from .nodes.strategy_confirmed_interrupt import strategy_confirmed_interrupt_node
from .nodes.studio_launch import studio_launch_node
from .state import GraphState


def build_graph_uncompiled() -> StateGraph:
    """Assemble the v1 graph topology without compiling.

    Exposed so direct-invocation callers (smoke tests, ad-hoc scripts) can
    attach their own checkpointer at compile time:

        from langgraph.checkpoint.memory import InMemorySaver
        compiled = build_graph_uncompiled().compile(checkpointer=InMemorySaver())
    """
    g = StateGraph(GraphState)

    g.add_node("pickup", pickup_node)
    # HOM-132.4: cache_policy on the deterministic heavy nodes — primary cost
    # saving of the HOM-132 epic (`isolate_audio` re-run no longer re-spends
    # ElevenLabs Scribe credits). Spec §6.
    g.add_node(
        "isolate_audio",
        isolate_audio_node,
        cache_policy=isolate_audio_cache_policy,
    )
    g.add_node("preflight_canon", preflight_canon_node)
    g.add_node(
        "glue_remap_transcript",
        glue_remap_transcript_node,
        cache_policy=glue_remap_transcript_cache_policy,
    )
    g.add_node(
        "p4_scaffold",
        p4_scaffold_node,
        cache_policy=p4_scaffold_cache_policy,
    )
    # HOM-132.1: pilot node for `cache_policy=`. Spec
    # `docs/superpowers/specs/2026-05-06-langgraph-node-caching-design.md`
    # §6 — `files=[transcripts.final_json_path]`. Re-runs on the same slug
    # with unchanged upstream skip the Opus visual-identity dispatch.
    g.add_node(
        "p4_design_system",
        p4_design_system_node,
        cache_policy=p4_design_system_cache_policy,
        retry_policy=_LLM_RETRY_POLICY,
    )
    g.add_node("gate_design_ok", design_ok_gate_node)
    # HOM-150: cache_policy on the Phase 4 LLM nodes. Spec
    # `docs/superpowers/specs/2026-05-06-langgraph-node-caching-design.md` §6.
    g.add_node(
        "p4_prompt_expansion",
        p4_prompt_expansion_node,
        cache_policy=p4_prompt_expansion_cache_policy,
        retry_policy=_LLM_RETRY_POLICY,
    )
    g.add_node(
        "p4_plan",
        p4_plan_node,
        cache_policy=p4_plan_cache_policy,
        retry_policy=_LLM_RETRY_POLICY,
    )
    g.add_node("gate_plan_ok", plan_ok_gate_node)
    g.add_node(
        "p4_catalog_scan",
        p4_catalog_scan_node,
        cache_policy=p4_catalog_scan_cache_policy,
    )
    g.add_node(
        "p4_captions_layer",
        p4_captions_layer_node,
        cache_policy=p4_captions_layer_cache_policy,
        retry_policy=_LLM_RETRY_POLICY,
    )
    # p4_dispatch_beats returns Command(goto=...) — either a list of Send
    # objects (fan-out to p4_beat, wired in HOM-134) or a string node name
    # for the skip paths. The `destinations=` tuple makes those static
    # destinations visible to LangGraph Studio's graph view (and to the
    # topology test). `END` is included for the empty-plan branch.
    g.add_node(
        "p4_dispatch_beats",
        p4_dispatch_beats_node,
        destinations=("p4_beat", "p4_assemble_index", END),
    )
    g.add_node(
        "p4_beat",
        p4_beat_node,
        cache_policy=p4_beat_cache_policy,
        retry_policy=_LLM_RETRY_POLICY,
    )
    g.add_node(
        "p4_assemble_index",
        p4_assemble_index_node,
        cache_policy=p4_assemble_index_cache_policy,
    )
    # HOM-127: post-assemble gate cluster (spec §4.3, §6.2). Each gate
    # routes pass→next, fail→halt_llm_boundary. Order matches spec —
    # cheap deterministic checks first (lint), browser-heavy headless
    # checks last (snapshot, captions_track).
    g.add_node("gate_lint", lint_gate_node)
    g.add_node("gate_validate", validate_gate_node)
    g.add_node("gate_inspect", inspect_gate_node)
    g.add_node("gate_design_adherence", design_adherence_gate_node)
    g.add_node("gate_animation_map", animation_map_gate_node)
    g.add_node("gate_snapshot", snapshot_gate_node)
    g.add_node("gate_captions_track", captions_track_gate_node)
    # HOM-148: cluster-gate retry node — re-authors one offending scene
    # fragment, then static-edges back to p4_assemble_index so the gate
    # can re-run on the rewritten HTML.
    g.add_node(
        "p4_redispatch_beat",
        p4_redispatch_beat_node,
        retry_policy=_LLM_RETRY_POLICY,
    )
    g.add_node(
        "p4_persist_session",
        p4_persist_session_node,
        cache_policy=p4_persist_session_cache_policy,
        retry_policy=_LLM_RETRY_POLICY,
    )
    g.add_node("studio_launch", studio_launch_node)
    g.add_node("gate_static_guard", static_guard_gate_node)
    g.add_node(
        "p3_inventory",
        p3_inventory_node,
        cache_policy=p3_inventory_cache_policy,
    )
    # HOM-132.3: cache_policy on the Phase 3 LLM nodes. Spec
    # `docs/superpowers/specs/2026-05-06-langgraph-node-caching-design.md` §6.
    g.add_node(
        "p3_pre_scan",
        p3_pre_scan_node,
        cache_policy=p3_pre_scan_cache_policy,
        retry_policy=_LLM_RETRY_POLICY,
    )
    g.add_node(
        "p3_strategy",
        p3_strategy_node,
        cache_policy=p3_strategy_cache_policy,
        retry_policy=_LLM_RETRY_POLICY,
    )
    g.add_node("strategy_confirmed_interrupt", strategy_confirmed_interrupt_node)
    g.add_node(
        "p3_edl_select",
        p3_edl_select_node,
        cache_policy=p3_edl_select_cache_policy,
        retry_policy=_LLM_RETRY_POLICY,
    )
    g.add_node("gate_edl_ok", edl_ok_gate_node)
    g.add_node(
        "p3_render_segments",
        p3_render_segments_node,
        cache_policy=p3_render_segments_cache_policy,
    )
    g.add_node(
        "p3_self_eval",
        p3_self_eval_node,
        cache_policy=p3_self_eval_cache_policy,
        retry_policy=_LLM_RETRY_POLICY,
    )
    g.add_node("gate_eval_ok", eval_ok_gate_node)
    g.add_node(
        "p3_persist_session",
        p3_persist_session_node,
        cache_policy=p3_persist_session_cache_policy,
        retry_policy=_LLM_RETRY_POLICY,
    )
    g.add_node("p3_review_interrupt", p3_review_interrupt_node)
    g.add_node("edl_failure_interrupt", edl_failure_interrupt_node)
    g.add_node("eval_failure_interrupt", eval_failure_interrupt_node)
    g.add_node("halt_llm_boundary", halt_llm_boundary_node)

    g.set_entry_point("pickup")

    # The explicit path mappings below are not strictly required by LangGraph
    # (it can infer destinations from the function's possible return values),
    # but listing them keeps Studio's static graph rendering honest about
    # which conditional edges exist — without it, skip-edges only appear
    # after a run actually traverses them.

    # skip_phase2? lives inside route_after_pickup.
    g.add_conditional_edges(
        "pickup",
        route_after_pickup,
        {
            END: END,
            "isolate_audio": "isolate_audio",
            "preflight_canon": "preflight_canon",
        },
    )
    g.add_edge("isolate_audio", "preflight_canon")

    # skip_phase3? lives inside route_after_preflight.
    g.add_conditional_edges(
        "preflight_canon",
        route_after_preflight,
        {
            END: END,
            "glue_remap_transcript": "glue_remap_transcript",
            "p3_inventory": "p3_inventory",
            "p3_pre_scan": "p3_pre_scan",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    g.add_conditional_edges(
        "p3_inventory",
        route_after_inventory,
        {
            END: END,
            "p3_pre_scan": "p3_pre_scan",
        },
    )
    g.add_conditional_edges(
        "p3_pre_scan",
        route_after_pre_scan,
        {
            END: END,
            "p3_strategy": "p3_strategy",
        },
    )
    g.add_conditional_edges(
        "p3_strategy",
        route_after_strategy,
        {
            END: END,
            "strategy_confirmed_interrupt": "strategy_confirmed_interrupt",
        },
    )
    g.add_conditional_edges(
        "strategy_confirmed_interrupt",
        route_after_strategy_confirmed,
        {
            END: END,
            "p3_edl_select": "p3_edl_select",
            "p3_strategy": "p3_strategy",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    g.add_conditional_edges(
        "p3_edl_select",
        route_after_edl_select,
        {
            END: END,
            "gate_edl_ok": "gate_edl_ok",
        },
    )
    # HOM-147: gate:edl_ok adopts the generic retry helper. The
    # `gate_edl_ok → p3_edl_select` retry edge sits between pass (render)
    # and exhaustion (interrupt); the producer's render context includes
    # `prior_violations` so the brief shows the prior failures verbatim.
    g.add_conditional_edges(
        "gate_edl_ok",
        route_after_edl_ok,
        {
            "p3_render_segments": "p3_render_segments",
            "p3_edl_select": "p3_edl_select",
            "edl_failure_interrupt": "edl_failure_interrupt",
        },
    )
    g.add_conditional_edges(
        "p3_render_segments",
        route_after_render_segments,
        {
            END: END,
            "halt_llm_boundary": "halt_llm_boundary",
            "p3_self_eval": "p3_self_eval",
        },
    )
    g.add_conditional_edges(
        "p3_self_eval",
        route_after_self_eval,
        {
            END: END,
            "halt_llm_boundary": "halt_llm_boundary",
            "gate_eval_ok": "gate_eval_ok",
        },
    )
    g.add_conditional_edges(
        "gate_eval_ok",
        route_after_eval_ok,
        {
            "p3_persist_session": "p3_persist_session",
            "p3_render_segments": "p3_render_segments",
            "eval_failure_interrupt": "eval_failure_interrupt",
        },
    )
    # HOM-146: Phase 3 → Phase 4 bridge with `interrupt()` review checkpoint.
    # Replaces the prior `p3_persist_session → halt_llm_boundary → END`
    # terminus. Single linear pass through both phases; the operator pauses
    # on `p3_review_interrupt` to glance at `final.mp4`, then resumes (or
    # aborts) — no second Submit / different routing path required.
    # HOM-158: route_after_persist_session no longer returns END (LLM raises
    # don't commit writes; the old `state.errors → END` short-circuit is gone).
    g.add_conditional_edges(
        "p3_persist_session",
        route_after_persist_session,
        {
            "p3_review_interrupt": "p3_review_interrupt",
        },
    )
    g.add_conditional_edges(
        "p3_review_interrupt",
        route_after_p3_review_interrupt,
        {
            END: END,
            "glue_remap_transcript": "glue_remap_transcript",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    # HOM-130: failure interrupts are no longer dead-ends. After resume,
    # routing inspects `state.edit.<edl|eval>.failure_resume.action`:
    #   - abort token        → halt_llm_boundary (notice surfaces in Studio)
    #   - anything else      → re-run the originating gate
    # END is kept reachable for the defensive `state.errors` short-circuit.
    g.add_conditional_edges(
        "edl_failure_interrupt",
        route_after_edl_failure_interrupt,
        {
            END: END,
            "gate_edl_ok": "gate_edl_ok",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    g.add_conditional_edges(
        "eval_failure_interrupt",
        route_after_eval_failure_interrupt,
        {
            END: END,
            "gate_eval_ok": "gate_eval_ok",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )

    # skip_phase4? lives inside route_after_remap.
    g.add_conditional_edges(
        "glue_remap_transcript",
        route_after_remap,
        {
            END: END,
            "p4_scaffold": "p4_scaffold",
        },
    )
    # Phase 4 LLM chain. New P4 LLM-node tickets MUST extend this chain in
    # their own PR (per CLAUDE.md "Topology wiring is part of node DoD") —
    # do NOT defer wiring to HOM-127. The compiled-graph topology smoke
    # (smoke_hom107.py Case 1 + tests/test_p4_topology.py) catches "node
    # added but edges not wired" regressions for free.
    g.add_conditional_edges(
        "p4_scaffold",
        route_after_scaffold,
        {
            END: END,
            "p4_design_system": "p4_design_system",
        },
    )
    g.add_conditional_edges(
        "p4_design_system",
        route_after_design_system,
        {
            END: END,
            "gate_design_ok": "gate_design_ok",
        },
    )
    g.add_conditional_edges(
        "gate_design_ok",
        route_after_design_ok,
        {
            "p4_prompt_expansion": "p4_prompt_expansion",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    g.add_conditional_edges(
        "p4_prompt_expansion",
        route_after_prompt_expansion,
        {
            END: END,
            "p4_plan": "p4_plan",
        },
    )
    g.add_conditional_edges(
        "p4_plan",
        route_after_plan,
        {
            END: END,
            "gate_plan_ok": "gate_plan_ok",
        },
    )
    g.add_conditional_edges(
        "gate_plan_ok",
        route_after_plan_ok,
        {
            "p4_catalog_scan": "p4_catalog_scan",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    g.add_conditional_edges(
        "p4_catalog_scan",
        route_after_catalog_scan,
        {
            END: END,
            "p4_captions_layer": "p4_captions_layer",
        },
    )
    g.add_conditional_edges(
        "p4_captions_layer",
        route_after_captions_layer,
        {
            END: END,
            "p4_dispatch_beats": "p4_dispatch_beats",
            "p4_assemble_index": "p4_assemble_index",
        },
    )
    # HOM-134: Send-spawned p4_beat branches fan in here. LangGraph waits
    # for ALL parallel branches before firing this static edge, so
    # p4_assemble_index sees every fragment that successfully wrote.
    g.add_edge("p4_beat", "p4_assemble_index")
    g.add_conditional_edges(
        "p4_assemble_index",
        route_after_assemble_index,
        {
            END: END,
            "halt_llm_boundary": "halt_llm_boundary",
            "gate_lint": "gate_lint",
        },
    )
    # HOM-148: post-assemble gate cluster — each gate has THREE outcomes:
    #   pass             → next gate in the chain
    #   fail + iter < 3  → p4_redispatch_beat (re-author offending scene,
    #                       then static-edge back to p4_assemble_index → gate)
    #   fail + iter ≥ 3  → halt_llm_boundary (notice surfaces violations)
    # `route_after_gate_with_retry` (from HOM-147) returns the bare node
    # name; the dict below maps it to the edge target — identity in all
    # three cases. The retry edge plus the `p4_redispatch_beat → p4_assemble_index`
    # fan-in edge below close the loop.
    g.add_conditional_edges(
        "gate_lint",
        route_after_lint,
        {
            "gate_validate": "gate_validate",
            "p4_redispatch_beat": "p4_redispatch_beat",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    g.add_conditional_edges(
        "gate_validate",
        route_after_validate,
        {
            "gate_inspect": "gate_inspect",
            "p4_redispatch_beat": "p4_redispatch_beat",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    g.add_conditional_edges(
        "gate_inspect",
        route_after_inspect,
        {
            "gate_design_adherence": "gate_design_adherence",
            "p4_redispatch_beat": "p4_redispatch_beat",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    g.add_conditional_edges(
        "gate_design_adherence",
        route_after_design_adherence,
        {
            "gate_animation_map": "gate_animation_map",
            "p4_redispatch_beat": "p4_redispatch_beat",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    g.add_conditional_edges(
        "gate_animation_map",
        route_after_animation_map,
        {
            "gate_snapshot": "gate_snapshot",
            "p4_redispatch_beat": "p4_redispatch_beat",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    g.add_conditional_edges(
        "gate_snapshot",
        route_after_snapshot,
        {
            "gate_captions_track": "gate_captions_track",
            "p4_redispatch_beat": "p4_redispatch_beat",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    g.add_conditional_edges(
        "gate_captions_track",
        route_after_captions_track,
        {
            "p4_persist_session": "p4_persist_session",
            "p4_redispatch_beat": "p4_redispatch_beat",
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    # HOM-148: redispatched scene fragment → re-assemble → first cluster gate.
    # Static edge keeps Studio's graph view honest about the loop.
    g.add_edge("p4_redispatch_beat", "p4_assemble_index")
    # HOM-126: p4_persist_session appends a Phase 4 Session block to
    # <edit>/project.md (canon §"Memory" format, monotonic N across phases),
    # then advances to studio_launch. A persist skip / sub-agent failure is
    # non-fatal — preview still happens — but a hard `errors[]` entry ENDs
    # the graph.
    # HOM-158: route_after_p4_persist_session no longer returns END — LLM
    # raises don't commit writes; persist_session always advances to studio.
    g.add_conditional_edges(
        "p4_persist_session",
        route_after_p4_persist_session,
        {
            "studio_launch": "studio_launch",
        },
    )
    # HOM-125: studio_launch spawns `hyperframes preview --port 3002` in the
    # background, then gate:static_guard sleeps 5s and scans the preview log.
    g.add_conditional_edges(
        "studio_launch",
        route_after_studio_launch,
        {
            END: END,
            "gate_static_guard": "gate_static_guard",
        },
    )
    g.add_conditional_edges(
        "gate_static_guard",
        route_after_static_guard,
        {
            "halt_llm_boundary": "halt_llm_boundary",
        },
    )
    g.add_edge("halt_llm_boundary", END)

    return g


_CACHE_PATH = repo_root() / "graph" / ".cache" / "langgraph.db"


def _build_cache() -> SqliteCache:
    """Singleton-ish cache backend for `compile(cache=...)`.

    HOM-132.1: gitignored `graph/.cache/langgraph.db`, lifecycle independent
    from `.langgraph_api/checkpoints.sqlite` (spec §5.1). `langgraph_api`
    rejects user-supplied checkpointer/store but NOT cache (verified against
    `langgraph_api/graph.py` 2026-05-06), so wiring `cache=` here is safe
    under both `langgraph dev` and direct compile.
    """
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return SqliteCache(path=str(_CACHE_PATH))


def build_graph():
    """Compile the graph WITHOUT a checkpointer, WITH a SqliteCache.

    Spec §9.6 originally bound a `SqliteSaver` here, but the langgraph-api
    runtime (used by `langgraph dev` and `langgraph up`) manages persistence
    itself and rejects user-supplied checkpointers with a hard ValueError.

    Switching the dev runtime to a real DB is configured via env vars
    (`POSTGRES_URI`) — out of scope for v1.

    The `cache=` argument is NOT rejected by langgraph-api (only
    checkpointer + store are) and powers per-node `cache_policy=` hits
    across runs / threads / processes for the same slug.
    """
    return build_graph_uncompiled().compile(cache=_build_cache())


graph = build_graph()
