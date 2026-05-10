"""Stable render-context fixtures for L0 brief snapshot tests (HOM-183).

Each function returns the kwargs dict that the corresponding node's
``_render_ctx`` would yield in production, but pinned to deterministic
placeholder values so the snapshot is stable across runs and operators.

Contracts (don't drift these without bumping the snapshot in the same
PR — that's the whole point of the L0 layer):

* Slug is fixed to ``"snapshot-fixture"``.
* Episode dir is a forward-slash POSIX-style path so Windows / *nix
  produce identical snapshots.
* Hashes / fingerprints / file paths are obvious placeholders.
* JSON sub-blobs use ``ensure_ascii=False`` to match production
  (``json.dumps(..., ensure_ascii=False)`` in every node's
  ``_render_ctx``).

The base context (``slug`` + ``episode_dir``) that ``LLMNode.__call__``
adds is provided here too, so each fixture is a complete render-ctx
ready to splat into ``render_brief(node, ctx)``.
"""

from __future__ import annotations

import json

SLUG = "snapshot-fixture"
EPISODE_DIR = "/tmp/snapshot-fixture/episode"
DESIGN_MD_PATH = f"{EPISODE_DIR}/hyperframes/DESIGN.md"
EXPANDED_PROMPT_PATH = f"{EPISODE_DIR}/hyperframes/.hyperframes/expanded-prompt.md"
TAKES_PACKED_PATH = f"{EPISODE_DIR}/edit/takes_packed.md"
TRANSCRIPT_JSON_PATH = f"{EPISODE_DIR}/edit/transcripts/raw.json"
CAPTIONS_BLOCK_PATH = f"{EPISODE_DIR}/hyperframes/captions.html"
SCENE_HTML_PATH = f"{EPISODE_DIR}/hyperframes/compositions/scene-hook.html"
PROJECT_MD_PATH = f"{EPISODE_DIR}/edit/project.md"
INDEX_HTML_PATH = f"{EPISODE_DIR}/hyperframes/index.html"

_FIXED_TAKES_PACKED_TEXT = (
    "[take-1] 00:00:00.500 --> 00:00:04.200\n"
    "Snapshot fixture transcript line one.\n"
    "[take-1] 00:00:04.500 --> 00:00:08.100\n"
    "Snapshot fixture transcript line two.\n"
)

_FIXED_PRE_SCAN_SLIPS = [
    {"reason": "filler", "range_s": [1.20, 1.45]},
]

_FIXED_STRATEGY = {
    "shape": "hook-problem-payoff",
    "takes": ["take-1"],
    "grade": "neutral, mild contrast lift",
    "pacing": "fast-SLOW-fast",
    "length_estimate_s": 30.0,
}

_FIXED_EDL_BEATS = ["HOOK", "PROBLEM", "PAYOFF"]

_FIXED_TRANSCRIPT_PATHS = [TRANSCRIPT_JSON_PATH]

_FIXED_PLAN_BEAT = {
    "beat": "HOOK",
    "concept": "Tight typographic close-up; an oversized stat slams into existence.",
    "mood": "Editorial restraint, Stripe Press energy.",
    "energy": "medium",
    "duration_s": 6.9,
    "catalog_or_custom": "custom",
    "justification": "Off-axis layout carries the surprise; catalog hero blocks all centered.",
}

_FIXED_CATALOG_SUMMARY = (
    "blocks:\n"
    "  - hero-stat-hold (stat-hold beat)\n"
    "components:\n"
    "  - hairline-rule"
)


def _base() -> dict:
    """Slug + episode_dir — what LLMNode.__call__ injects unconditionally."""
    return {"slug": SLUG, "episode_dir": EPISODE_DIR}


def p3_strategy_ctx() -> dict:
    revisions: list[dict] = []
    return {
        **_base(),
        "takes_packed_path": TAKES_PACKED_PATH,
        "takes_packed_text": _FIXED_TAKES_PACKED_TEXT,
        "pre_scan_slips_json": json.dumps(_FIXED_PRE_SCAN_SLIPS, ensure_ascii=False),
        "strategy_revisions": revisions,
        "strategy_revisions_json": json.dumps(revisions, ensure_ascii=False),
    }


def p3_edl_select_ctx() -> dict:
    return {
        **_base(),
        "takes_packed_path": TAKES_PACKED_PATH,
        "transcript_paths_json": json.dumps(_FIXED_TRANSCRIPT_PATHS, ensure_ascii=False),
        "pre_scan_slips_json": json.dumps(_FIXED_PRE_SCAN_SLIPS, ensure_ascii=False),
        "strategy_json": json.dumps(_FIXED_STRATEGY, ensure_ascii=False),
        # gate_retry_context defaults — iteration 1 (no prior failure)
        "prior_violations": [],
        "prior_iteration": 0,
    }


def p4_design_system_ctx() -> dict:
    return {
        **_base(),
        "design_md_path": DESIGN_MD_PATH,
        "strategy_json": json.dumps(_FIXED_STRATEGY, ensure_ascii=False),
        "edl_beats_json": json.dumps(_FIXED_EDL_BEATS, ensure_ascii=False),
    }


def p4_prompt_expansion_ctx() -> dict:
    return {
        **_base(),
        "expanded_prompt_path": EXPANDED_PROMPT_PATH,
        "design_md_path": DESIGN_MD_PATH,
        "strategy_json": json.dumps(_FIXED_STRATEGY, ensure_ascii=False),
        "edl_beats_json": json.dumps(_FIXED_EDL_BEATS, ensure_ascii=False),
        "transcript_json_path": TRANSCRIPT_JSON_PATH,
        "style_request_json": json.dumps(
            "Editorial restraint; analytical not festive.", ensure_ascii=False
        ),
    }


def p4_plan_ctx() -> dict:
    return {
        **_base(),
        "design_md_path": DESIGN_MD_PATH,
        "expanded_prompt_path": EXPANDED_PROMPT_PATH,
        "strategy_json": json.dumps(_FIXED_STRATEGY, ensure_ascii=False),
        "edl_beats_json": json.dumps(_FIXED_EDL_BEATS, ensure_ascii=False),
    }


def p4_beat_ctx() -> dict:
    return {
        **_base(),
        "scene_id": "hook",
        "beat_index": 0,
        "total_beats": 3,
        "is_final": False,
        "data_start_s": 0.0,
        "data_duration_s": 6.9,
        "data_track_index": 1,
        "data_width": 1080,
        "data_height": 1920,
        "plan_beat_json": json.dumps(_FIXED_PLAN_BEAT, ensure_ascii=False),
        "design_md_path": DESIGN_MD_PATH,
        "expanded_prompt_path": EXPANDED_PROMPT_PATH,
        "catalog_summary": _FIXED_CATALOG_SUMMARY,
        "scene_html_path": SCENE_HTML_PATH,
    }


def gate_animation_map_classify_ctx() -> dict:
    """HOM-156: cheap-tier fix-or-justify classifier brief context."""
    flagged = [
        {
            "flag_id": ".flash::1::paced-fast",
            "selector": ".flash",
            "flag": "paced-fast",
            "duration": 0.12,
            "index": 1,
        },
        {
            "flag_id": ".ambient::2::paced-slow",
            "selector": ".ambient",
            "flag": "paced-slow",
            "duration": 3.0,
            "index": 2,
        },
    ]
    plan_beats = [
        {"beat": "HOOK", "concept": "Tight stat slam.", "mood": "Editorial.",
         "energy": "high", "duration_s": 6.9},
        {"beat": "HOLD", "concept": "Sustained ambient.", "mood": "Meditative.",
         "energy": "calm", "duration_s": 5.0},
    ]
    return {
        **_base(),
        "animation_map_json_path": (
            f"{EPISODE_DIR}/hyperframes/.hyperframes/anim-map/animation-map.json"
        ),
        "design_md_path": DESIGN_MD_PATH,
        "plan_beats_json": json.dumps(plan_beats, ensure_ascii=False),
        "flagged_tweens_json": json.dumps(flagged, ensure_ascii=False),
    }


def p4_persist_session_ctx() -> dict:
    plan = {
        "shape": "hook-problem-payoff",
        "beats": [
            {"id": "hook", "title": "Hook", "duration_s": 6.9},
            {"id": "payoff", "title": "Payoff", "duration_s": 5.0},
        ],
    }
    beats_summary = [
        {
            "beat_id": "hook",
            "title": "Hook",
            "duration_s": 6.9,
            "scene_path": SCENE_HTML_PATH,
            "status": "assembled",
        },
        {
            "beat_id": "payoff",
            "title": "Payoff",
            "duration_s": 5.0,
            "scene_path": f"{EPISODE_DIR}/hyperframes/compositions/scene-payoff.html",
            "status": "assembled",
        },
    ]
    gate_results = [
        {"gate": "gate:design_ok", "ok": True, "iteration": 1},
        {"gate": "gate:plan_ok", "ok": True, "iteration": 1},
        {"gate": "gate:static_guard", "ok": True, "iteration": 1},
    ]
    return {
        **_base(),
        "project_md_path": PROJECT_MD_PATH,
        "design_md_path": DESIGN_MD_PATH,
        "expanded_prompt_path": EXPANDED_PROMPT_PATH,
        "plan_json": json.dumps(plan, ensure_ascii=False),
        "beats_json": json.dumps(beats_summary, ensure_ascii=False),
        "captions_block_path": CAPTIONS_BLOCK_PATH,
        "index_html_path": INDEX_HTML_PATH,
        "gate_results_json": json.dumps(gate_results, ensure_ascii=False),
        "today": "2026-05-10",
    }


def p4_captions_layer_ctx() -> dict:
    return {
        **_base(),
        "captions_block_path": CAPTIONS_BLOCK_PATH,
        "design_md_path": DESIGN_MD_PATH,
        "transcript_json_path": TRANSCRIPT_JSON_PATH,
        "transcript_json_filename": "raw.json",
        "data_width": 1080,
        "data_height": 1920,
        "data_duration_s": 30.0,
    }


# Mapping used by the test module to drive parameterization.
NODE_CONTEXTS = {
    "p3_strategy": p3_strategy_ctx,
    "p3_edl_select": p3_edl_select_ctx,
    "p4_design_system": p4_design_system_ctx,
    "p4_prompt_expansion": p4_prompt_expansion_ctx,
    "p4_plan": p4_plan_ctx,
    "p4_beat": p4_beat_ctx,
    "p4_captions_layer": p4_captions_layer_ctx,
    "p4_persist_session": p4_persist_session_ctx,
    "gate_animation_map_classify": gate_animation_map_classify_ctx,
}
