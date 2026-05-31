"""Fingerprint invalidation assertion helpers (HOM-184 / spec §3 L0).

Each creative LLM node carries a ``_cache_key(state)`` function that
feeds ``langgraph.types.CachePolicy``. The HOM-157 mechanism guarantees
that ``cache_key`` changes when:

* ``_CACHE_VERSION`` is bumped (brief / schema / tool-list change).
* ``graph/config.yaml`` for the node changes (tier / model / timeout /
  backend_preference) — covered by ``make_llm_key`` auto-prepending a
  ``cfg:<sha>`` extra.
* An upstream artifact in ``files=`` changes content (sha256-hashed via
  :func:`edit_episode_graph._caching.file_fingerprint`).

This module asserts those invariants per-node so a future refactor that
silently drops one of those inputs surfaces immediately, without paid
LLM dispatches. Spec §3 «Fingerprint invalidation assertion».

Usage:

    from tests._helpers.fingerprint_assertions import (
        assert_brief_change_invalidates,
        assert_model_change_invalidates,
        assert_upstream_artifact_change_invalidates,
    )

    def test_p3_strategy_brief_invalidates():
        assert_brief_change_invalidates("p3_strategy")

The convenience helpers package a sensible base state per known node;
the lower-level :func:`assert_fingerprint_changes_when` is exposed for
custom mutations that aren't covered by the canned set.
"""

from __future__ import annotations

import hashlib
import importlib
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

# ---------------------------------------------------------------------------
# Per-node base-state factories.
#
# Each factory returns a dict that the node's ``_cache_key`` accepts
# (matches the shape it pulls from ``state`` — ``slug``, ``episode_dir``,
# the relevant ``edit``/``compose``/``transcripts`` blobs).
#
# State values are deliberately minimal: just enough for ``_cache_key``
# to pick up every input it fingerprints. The bodies (LLM dispatch,
# validators) are NOT exercised here — this is a key-only L0 check.
# ---------------------------------------------------------------------------


_FP_SLUG = "fp-fixture"


def _pin_project_root_to(tmp_dir: Path) -> Path:
    """HOM-224: pin HOMESTUDIO_PROJECT_ROOT so EpisodePaths(slug) resolves
    under tmp_dir. Returns the slug-derived episode dir (created on disk).

    Pre-HOM-223/224 the cache_key consumed state echoes (e.g.
    `transcripts.takes_packed_path`); post-HOM-224 it derives via
    `EpisodePaths(slug)`. The fingerprint test edits a real file and
    expects the key to flip — so the file MUST live at the path
    `_cache_key` resolves, which is now slug-derived.
    """
    os.environ["HOMESTUDIO_PROJECT_ROOT"] = str(tmp_dir)
    episode_dir = tmp_dir / "episodes" / _FP_SLUG
    episode_dir.mkdir(parents=True, exist_ok=True)
    return episode_dir


def _p3_strategy_base(tmp_dir: Path) -> dict:
    episode_dir = _pin_project_root_to(tmp_dir)
    takes = episode_dir / "edit" / "takes_packed.md"
    takes.parent.mkdir(parents=True, exist_ok=True)
    takes.write_text("snapshot fixture takes\n", encoding="utf-8")
    return {
        "slug": _FP_SLUG,
        "episode_dir": str(episode_dir),
        "transcripts": {},
        "edit": {
            "pre_scan": {"slips": []},
            "strategy": {},
        },
        "strategy_revisions": [],
    }


def _p4_design_system_base(tmp_dir: Path) -> dict:
    episode_dir = _pin_project_root_to(tmp_dir)
    # HOM-224: cache_key consumes the slug-derived `transcripts/final.json`,
    # not the legacy `transcripts/raw.json` echo. Seed at the slug-derived
    # path so the fingerprint test's edit lands where _cache_key reads.
    transcript = episode_dir / "edit" / "transcripts" / "final.json"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text('{"segments":[]}', encoding="utf-8")
    edl = episode_dir / "edit" / "edl.json"
    edl.write_text('{"ranges":[]}', encoding="utf-8")
    return {
        "slug": _FP_SLUG,
        "episode_dir": str(episode_dir),
        "transcripts": {},
        "edit": {
            "edl": {"ranges": []},
            "strategy": {"shape": "hpp", "takes": ["t1"]},
        },
    }


def _p4_prompt_expansion_base(tmp_dir: Path) -> dict:
    """Base state for p4_prompt_expansion cache key (HOM-240 → HOM-279).

    Post-HOM-279 the node's `_cache_key`:
      - files=[] — transcript body migrated to in-state extras.
      - extras += stable_fingerprint(style_request),
                   stable_fingerprint(design_md body),
                   stable_fingerprint(transcript body).

    Seed the in-state DESIGN.md + transcript bodies; the file-edit
    invariant for transcripts is owned by `glue_remap_transcript` and
    asserted via the state-body mutator below.
    """
    _pin_project_root_to(tmp_dir)
    return {
        "slug": _FP_SLUG,
        "compose": {"design": {"design_md": "# DESIGN.md fixture\n"}},
        "transcripts": {
            "bodies": {
                "raw": '{"words":[]}',
                "final": '{"edl_hash":"abc","words":[]}',
            },
        },
        "edit": {"edl": {"ranges": []}, "strategy": {"shape": "hpp"}},
    }


def _p4_plan_base(tmp_dir: Path) -> dict:
    """Base state for p4_plan cache key (HOM-240).

    Post-HOM-240 the node's `_cache_key`:
      - files=[transcripts_final_json_path] — Phase 3 disk artifact.
      - extras += stable_fingerprint(design_md body),
                  stable_fingerprint(expanded_prompt body).
    """
    episode_dir = _pin_project_root_to(tmp_dir)
    transcript = episode_dir / "edit" / "transcripts" / "final.json"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text('{"segments":[]}', encoding="utf-8")
    return {
        "slug": _FP_SLUG,
        "episode_dir": str(episode_dir),
        "compose": {
            "design": {"design_md": "# DESIGN.md fixture\n"},
            "expansion": {"expanded_prompt": "# expanded-prompt fixture\n"},
        },
        "edit": {"edl": {"ranges": []}, "strategy": {"shape": "hpp"}},
    }


def _gate_animation_map_classify_base(tmp_dir: Path) -> dict:
    """Base state for the gate_animation_map_classify LLM node.

    HOM-156 — initial extraction; HOM-204 — input shape moved from
    ``pending_justifiable`` to ``advisory_findings.pending_classify``;
    HOM-225 — paths derive via ``EpisodePaths(slug)``, so the base state
    pins ``HOMESTUDIO_PROJECT_ROOT`` and seeds the slug-derived layout.

    The node's cache key reads:
      - `EpisodePaths(slug).hyperframes_dir / .hyperframes/anim-map/
        animation-map.json` → content-hashed.
      - `EpisodePaths(slug).design_md_path` → content-hashed.
      - `compose.plan.beats` → fingerprinted via stable_fingerprint.
      - `gate_results[*].advisory_findings.pending_classify` (latest
        gate:animation_map record) → fingerprinted via stable_fingerprint.
    """
    episode_dir = _pin_project_root_to(tmp_dir)
    hf_dir = episode_dir / "hyperframes"
    hf_dir.mkdir(parents=True, exist_ok=True)
    anim_dir = hf_dir / ".hyperframes" / "anim-map"
    anim_dir.mkdir(parents=True, exist_ok=True)
    anim_map = anim_dir / "animation-map.json"
    anim_map.write_text('{"tweens":[],"deadZones":[]}', encoding="utf-8")
    design_md = hf_dir / "DESIGN.md"
    design_md.write_text("# DESIGN.md fixture\n", encoding="utf-8")
    return {
        "slug": _FP_SLUG,
        "compose": {
            "plan": {
                "beats": [
                    {"beat": "HOOK", "concept": "c", "mood": "m",
                     "energy": "high", "duration_s": 6.9},
                ],
            },
        },
        "gate_results": [
            {
                "gate": "gate:animation_map",
                "passed": True,  # HOM-204: advisory — successful helper run.
                "violations": [],
                "advisory_findings": {
                    "always_fix": [],
                    "dead_zones": [],
                    "pending_classify": [
                        {"flag_id": ".flash::1::paced-fast", "selector": ".flash",
                         "flag": "paced-fast", "duration": 0.12, "index": 1},
                    ],
                },
                "iteration": 1,
                "timestamp": "2026-05-09T00:00:00Z",
            },
        ],
    }


def _p4_persist_session_base(tmp_dir: Path) -> dict:
    """HOM-229 → HOM-240: cache key fingerprints `compose.index_html` body
    + extras=(assembled_at,). Pre-HOM-240 it file_fingerprinted
    `EpisodePaths(slug).index_html_path`; post-HOM-240 the file is no
    longer on disk while this node runs, so the body in state is the
    source of truth.
    """
    episode_dir = _pin_project_root_to(tmp_dir)
    return {
        "slug": _FP_SLUG,
        "episode_dir": str(episode_dir),
        "compose": {
            "assemble": {"assembled_at": "2026-05-10T12:00:00+00:00"},
            "index_html": "<html><body>fp fixture</body></html>",
        },
    }


def _p4_captions_layer_base(tmp_dir: Path) -> dict:
    """Base state for p4_captions_layer cache key.

    HOM-224: paths derive via EpisodePaths(slug).
    HOM-240: `design_md_path` dropped from files=; DESIGN.md body lives
    in `compose.design.design_md`.
    HOM-279: transcript body dropped from files= too; both DESIGN.md
    and transcript bodies live in state extras.
    """
    _pin_project_root_to(tmp_dir)
    return {
        "slug": _FP_SLUG,
        "compose": {"design": {"design_md": "# DESIGN.md fixture\n"}},
        "transcripts": {
            "bodies": {
                "raw": '{"words":[]}',
                "final": '{"edl_hash":"abc","words":[]}',
            },
        },
    }


def _p4_scaffold_base(tmp_dir: Path) -> dict:
    """Base state for p4_scaffold cache key (HOM-280).

    The node's `_cache_key` reads slug only (`files=[]`) — the subprocess
    is deterministic given slug+episode_dir, and the post-HOM-280 output
    (`compose.scaffold.index_html`) is fully derived from the subprocess.
    The registry mutator therefore flips the SLUG (not a file or state
    body) — that's the only `_cache_key` input besides `_CACHE_VERSION`.
    """
    _pin_project_root_to(tmp_dir)
    return {
        "slug": _FP_SLUG,
        "compose": {},
    }


def _p4_assemble_index_base(tmp_dir: Path) -> dict:
    """Base state for p4_assemble_index cache key (HOM-280).

    Post-HOM-280 the cache key fingerprints (in extras):
      - scene bodies from `state.scenes[<sid>].html`
      - captions body from `compose.captions.html`
      - design tokens (palette + typography) from `compose.design`
      - scaffold body from `compose.scaffold.index_html` (HOM-280 add)

    The registry mutator flips `compose.scaffold.index_html` — that's
    the HOM-280-specific fingerprint input. Pre-existing inputs are
    covered by their own producer-node fingerprint tests.
    """
    _pin_project_root_to(tmp_dir)
    return {
        "slug": _FP_SLUG,
        "compose": {
            "scaffold": {
                "index_html": "<html><body>scaffolded</body></html>",
            },
            "plan": {"beats": [{"beat": "Hook", "duration_s": 3.0}]},
            "design": {
                "palette": [{"role": "background", "hex": "#000"}],
                "typography": [{"role": "body", "family": "Inter"}],
            },
            "captions": {"html": "<div/>"},
        },
        "scenes": {"hook": {"html": "<div id='scene-hook'/>"}},
    }


def _p4_beat_base(tmp_dir: Path) -> dict:
    """HOM-224 → HOM-240: paths derived via EpisodePaths(slug). Post-HOM-240
    `_cache_key` fingerprints in-state body strings only (files=[]).
    """
    episode_dir = _pin_project_root_to(tmp_dir)
    return {
        "slug": _FP_SLUG,
        "episode_dir": str(episode_dir),
        "compose": {
            "design": {"design_md": "# DESIGN.md fixture\n"},
            "expansion": {"expanded_prompt": "# expanded-prompt fixture\n"},
        },
        "_beat_dispatch": {
            "scene_id": "scene-hook",
            "plan_beat": {"beat": "HOOK", "concept": "fixture", "duration_s": 5.0},
        },
    }


# Map node_name → (module_path, base_state_factory, upstream_mutator).
#
# ``upstream_mutator`` is a callable ``(state: dict) -> None`` that
# mutates a load-bearing upstream input — either by editing a file in
# ``files=`` or by overwriting a state body in ``extras=`` —
# such that the node's ``_cache_key`` MUST flip. Used by
# :func:`assert_upstream_artifact_change_invalidates`.
#
# HOM-240 (Step E of HOM-230): mutator semantics changed from
# path-pointer to free-form callable. Pre-HOM-240 the third slot was a
# ``Callable[[dict], Path]`` returning the file whose content the
# helper would sha-edit. Post-HOM-240, Phase-4 creative nodes
# fingerprint in-state body strings (the canonical disk files are no
# longer present while the node runs — `p4_materialize_disk` is the
# single deterministic writer at chain end). The mutator now does
# whatever is needed to flip the key: write to a file that's still in
# ``files=``, or mutate a state body in ``extras=``.
from edit_episode_graph._paths import EpisodePaths


def _mutate_file(get_path: Callable[[dict], Path]) -> Callable[[dict], None]:
    """Return a mutator that appends bytes to a slug-derived file."""

    def _mut(state: dict) -> None:
        target = get_path(state)
        if not target.exists():
            raise FileNotFoundError(
                f"upstream_mutator: expected file at {target} but it was not "
                "seeded by base-state factory"
            )
        target.write_bytes(target.read_bytes() + b"\n# fp-mutated\n")

    return _mut


def _slug_path(prop_name: str) -> Callable[[dict], Path]:
    """Slug-derived path resolver — uses EpisodePaths(slug).<prop_name>."""

    def _resolve(state: dict) -> Path:
        slug = state["slug"]
        ep = EpisodePaths(slug)
        return getattr(ep, prop_name)

    return _resolve


def _mutate_state_at(*path: str) -> Callable[[dict], None]:
    """Return a mutator that overwrites a state body string at `path`.

    Each segment is a dict key; intermediate dicts are auto-created.
    Used post-HOM-240 for nodes whose `_cache_key` fingerprints in-state
    bodies rather than disk files.
    """

    def _mut(state: dict) -> None:
        cur: dict = state
        for key in path[:-1]:
            nxt = cur.get(key)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[key] = nxt
            cur = nxt
        prior = cur.get(path[-1]) or ""
        cur[path[-1]] = str(prior) + "\n# fp-mutated\n"

    return _mut


_p3_strategy_mutator = _mutate_file(
    lambda s: EpisodePaths(s["slug"]).edit_dir / "takes_packed.md"
)


def _p3_inventory_base(tmp_dir: Path) -> dict:
    """Base state for p3_inventory cache key (HOM-285).

    Cache key reads slug + `pickup.raw_path` + `audio.wav_path`
    (deterministic file fingerprints; HOM-223 identity-only state). The
    mutator flips the `pickup.raw_path` file to invalidate the key — the
    HOM-285 body hoist is a state-output-shape change, not a new
    cache-key input, so the mutator covers the load-bearing file edge.
    """
    episode_dir = _pin_project_root_to(tmp_dir)
    raw_video = episode_dir / "raw.mp4"
    raw_video.write_bytes(b"fp-fixture raw video bytes")
    wav = episode_dir / "edit" / "audio.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    wav.write_bytes(b"fp-fixture wav bytes")
    return {
        "slug": _FP_SLUG,
        "pickup": {"raw_path": str(raw_video)},
        "audio": {"wav_path": str(wav)},
    }


def _p3_pre_scan_base(tmp_dir: Path) -> dict:
    """Base state for p3_pre_scan cache key (HOM-377).

    `_cache_key`: files=[takes_packed.md] + extras=(canon:<fp>,). The mutator
    edits takes_packed.md to flip the key; the canon extra is exercised
    separately by `assert_canon_change_invalidates`.
    """
    episode_dir = _pin_project_root_to(tmp_dir)
    takes = episode_dir / "edit" / "takes_packed.md"
    takes.parent.mkdir(parents=True, exist_ok=True)
    takes.write_text("fp fixture takes\n", encoding="utf-8")
    return {"slug": _FP_SLUG, "episode_dir": str(episode_dir), "edit": {}}


def _p3_self_eval_base(tmp_dir: Path) -> dict:
    """Base state for p3_self_eval cache key (HOM-377).

    `_cache_key`: files=[final.mp4, edl.json] + extras=(eval_iteration,
    canon:<fp>). The mutator edits final.mp4 to flip the key.
    """
    episode_dir = _pin_project_root_to(tmp_dir)
    ep = EpisodePaths(_FP_SLUG)
    final_mp4 = ep.final_mp4_path
    final_mp4.parent.mkdir(parents=True, exist_ok=True)
    final_mp4.write_bytes(b"fp fixture mp4 bytes")
    edl = ep.edit_dir / "edl.json"
    edl.parent.mkdir(parents=True, exist_ok=True)
    edl.write_text('{"ranges":[]}', encoding="utf-8")
    return {
        "slug": _FP_SLUG,
        "episode_dir": str(episode_dir),
        "edit": {"edl": {"ranges": []}},
        "gate_results": [],
    }


def _p3_edl_select_base(tmp_dir: Path) -> dict:
    """Base state for p3_edl_select cache key (HOM-377).

    `_cache_key`: files=[takes_packed.md, *transcripts] + extras=(slips,
    strategy_fp, prior_violations, prior_iteration, canon:<fp>). The mutator
    edits takes_packed.md to flip the key.
    """
    episode_dir = _pin_project_root_to(tmp_dir)
    takes = episode_dir / "edit" / "takes_packed.md"
    takes.parent.mkdir(parents=True, exist_ok=True)
    takes.write_text("fp fixture takes\n", encoding="utf-8")
    return {
        "slug": _FP_SLUG,
        "episode_dir": str(episode_dir),
        "edit": {"pre_scan": {"slips": []}, "strategy": {"shape": "hpp"}},
    }


_NODE_REGISTRY: dict[
    str, tuple[str, Callable[[Path], dict], Callable[[dict], None]]
] = {
    "p3_strategy": (
        "edit_episode_graph.nodes.p3_strategy",
        _p3_strategy_base,
        _p3_strategy_mutator,
    ),
    # HOM-377: p3_pre_scan / p3_self_eval / p3_edl_select gained a
    # `canon:<fp>` extra (verbatim canon pulled into the brief). Registered
    # here so the parametrised version/model/upstream invariants cover them;
    # the canon extra itself is asserted by `assert_canon_change_invalidates`.
    "p3_pre_scan": (
        "edit_episode_graph.nodes.p3_pre_scan",
        _p3_pre_scan_base,
        _mutate_file(lambda s: EpisodePaths(s["slug"]).edit_dir / "takes_packed.md"),
    ),
    "p3_self_eval": (
        "edit_episode_graph.nodes.p3_self_eval",
        _p3_self_eval_base,
        _mutate_file(_slug_path("final_mp4_path")),
    ),
    "p3_edl_select": (
        "edit_episode_graph.nodes.p3_edl_select",
        _p3_edl_select_base,
        _mutate_file(lambda s: EpisodePaths(s["slug"]).edit_dir / "takes_packed.md"),
    ),
    # HOM-285: p3_inventory is a deterministic node (make_key, not
    # make_llm_key) — same CREATIVE_NODES exemption as p4_scaffold /
    # p4_assemble_index / gate_animation_map. Cache key reads slug,
    # `pickup.raw_path`, `audio.wav_path` (via files=). The mutator
    # edits the raw video file to flip the key.
    "p3_inventory": (
        "edit_episode_graph.nodes.p3_inventory",
        _p3_inventory_base,
        _mutate_file(lambda s: Path(s["pickup"]["raw_path"])),
    ),
    # p4_design_system: files=[final_json_path, edl_path] (Phase 3 disk),
    # extras=(strategy_fingerprint,). The Phase 3 transcript file edit
    # still flips the key — no HOM-240 migration needed for this node
    # (it produces DESIGN.md, doesn't consume it).
    "p4_design_system": (
        "edit_episode_graph.nodes.p4_design_system",
        _p4_design_system_base,
        _mutate_file(_slug_path("transcripts_final_json_path")),
    ),
    # HOM-240: p4_beat files=[]; cache_key fingerprints
    # `compose.design.design_md` + `compose.expansion.expanded_prompt`
    # in state. Mutator overwrites the design body to flip the key.
    "p4_beat": (
        "edit_episode_graph.nodes.p4_beat",
        _p4_beat_base,
        _mutate_state_at("compose", "design", "design_md"),
    ),
    # HOM-279: p4_captions_layer files=[]; both DESIGN.md and transcript
    # bodies live in state extras. The mutator overwrites the transcript
    # body — this catches a Step-HOM-279 regression where someone
    # reintroduces `transcripts_final_json_path` to files= without
    # adding the body to extras.
    "p4_captions_layer": (
        "edit_episode_graph.nodes.p4_captions_layer",
        _p4_captions_layer_base,
        _mutate_state_at("transcripts", "bodies", "final"),
    ),
    # HOM-279: p4_prompt_expansion files=[]; style_request + DESIGN.md
    # body + transcript body all in state extras. Mutator overwrites
    # the transcript body — catches the same regression class as
    # p4_captions_layer.
    "p4_prompt_expansion": (
        "edit_episode_graph.nodes.p4_prompt_expansion",
        _p4_prompt_expansion_base,
        _mutate_state_at("transcripts", "bodies", "final"),
    ),
    # HOM-240: p4_persist_session files=[];
    # cache_key fingerprints `compose.index_html` body.
    "p4_persist_session": (
        "edit_episode_graph.nodes.p4_persist_session",
        _p4_persist_session_base,
        _mutate_state_at("compose", "index_html"),
    ),
    # HOM-280: p4_scaffold is a deterministic node (make_key, not
    # make_llm_key). The CREATIVE_NODES parametrised invariants don't
    # apply (no `cfg:<sha>` extra to flip), so this entry is consumed
    # by focused tests in `graph/tests/test_p4_scaffold_node.py`
    # (HOM-204 pattern — gate_animation_map carries the same exemption).
    # The mutator flips the slug because `files=[]` and the cache key
    # depends on slug + _CACHE_VERSION only.
    "p4_scaffold": (
        "edit_episode_graph.nodes.p4_scaffold",
        _p4_scaffold_base,
        lambda s: s.update(slug=s["slug"] + "-v2"),
    ),
    # HOM-280: p4_assemble_index is deterministic (make_key). Same
    # exemption from CREATIVE_NODES — focused tests in
    # `graph/tests/test_p4_assemble_index_node.py`. The mutator flips
    # the new HOM-280 input (scaffold body); pre-existing inputs
    # (scenes / captions / design) are covered by their producer
    # nodes' fingerprint tests.
    "p4_assemble_index": (
        "edit_episode_graph.nodes.p4_assemble_index",
        _p4_assemble_index_base,
        _mutate_state_at("compose", "scaffold", "index_html"),
    ),
    # HOM-156 (review S1): cheap-tier LLM classifier extracted into its own
    # graph node so cache_policy= actually fires.
    # HOM-225: primary_artifact derives via EpisodePaths(slug).
    "gate_animation_map_classify": (
        "edit_episode_graph.nodes.gate_animation_map_classify",
        _gate_animation_map_classify_base,
        _mutate_file(
            lambda s: _slug_path("hyperframes_dir")(s)
            / ".hyperframes" / "anim-map" / "animation-map.json"
        ),
    ),
}

# HOM-204: gate:animation_map is a deterministic gate (uses make_key, not
# make_llm_key) — the parametrised CREATIVE_NODES tests in
# test_fingerprint_invalidation.py exercise make_llm_key invariants, which
# do NOT apply to make_key. Its version bump is asserted directly in
# graph/tests/test_animation_map_gate.py instead of via parametrisation.


def _load_node_module(node_name: str):
    if node_name not in _NODE_REGISTRY:
        raise KeyError(
            f"unknown node {node_name!r}; supported: {sorted(_NODE_REGISTRY)}"
        )
    return importlib.import_module(_NODE_REGISTRY[node_name][0])


def _node_base_state(node_name: str, tmp_dir: Path) -> dict:
    return _NODE_REGISTRY[node_name][1](tmp_dir)


def _upstream_mutator(node_name: str) -> Callable[[dict], None]:
    return _NODE_REGISTRY[node_name][2]


def _compute_key(node_name: str, state: dict) -> str:
    """Invoke the node's ``_cache_key(state)`` — the production call shape."""
    mod = _load_node_module(node_name)
    return mod._cache_key(state)


# ---------------------------------------------------------------------------
# Core assertion + convenience wrappers.
# ---------------------------------------------------------------------------


def assert_fingerprint_changes_when(
    node_name: str,
    base_state: dict,
    mutation_fn: Callable[[dict], None],
) -> tuple[str, str]:
    """Assert ``_cache_key`` differs after ``mutation_fn`` mutates ``state``.

    ``mutation_fn`` receives the (single, shared) state dict and mutates
    it in place. Both calls go through the node module's real
    ``_cache_key`` so any drift in cache-key plumbing is caught.

    Returns the ``(before, after)`` keys for downstream assertions if the
    caller wants to inspect them.
    """
    before = _compute_key(node_name, base_state)
    mutation_fn(base_state)
    after = _compute_key(node_name, base_state)
    assert before != after, (
        f"{node_name}: cache key did not change after mutation\n"
        f"  before={before}\n"
        f"  after ={after}\n"
        f"  state ={base_state!r}"
    )
    return before, after


def assert_brief_change_invalidates(node_name: str, *, tmp_path: Path) -> None:
    """Bumping the node's ``_CACHE_VERSION`` MUST change the cache key.

    Modeled by monkey-bumping the module's ``_CACHE_VERSION`` constant
    around a key-recompute. Restores on exit so other tests in the same
    session see the original value.
    """
    mod = _load_node_module(node_name)
    state = _node_base_state(node_name, tmp_path)
    original = mod._CACHE_VERSION
    try:
        before = _compute_key(node_name, state)
        mod._CACHE_VERSION = original + 1
        after = _compute_key(node_name, state)
    finally:
        mod._CACHE_VERSION = original
    assert before != after, (
        f"{node_name}: cache key did not change when _CACHE_VERSION bumped "
        f"from {original} to {original + 1} — make_llm_key/make_key may not "
        f"be honoring the version arg"
    )


@contextmanager
def _patched_node_config_fingerprint(target_node: str, override: str) -> Iterator[None]:
    """Force :func:`_caching.node_config_fingerprint` to a stable override.

    Only intercepts calls for ``target_node`` so other LLM nodes evaluated
    transitively (none in our helpers, but defensive) keep their real
    fingerprint.
    """
    from edit_episode_graph import _caching

    original = _caching.node_config_fingerprint

    def _patched(name: str) -> str:
        if name == target_node:
            return override
        return original(name)

    _caching.node_config_fingerprint = _patched
    try:
        yield
    finally:
        _caching.node_config_fingerprint = original


def assert_model_change_invalidates(node_name: str, *, tmp_path: Path) -> None:
    """Changing routing-config (tier/model/timeout) MUST change the key.

    HOM-157 mechanism (3): ``make_llm_key`` prepends ``cfg:<sha>`` from
    :func:`node_config_fingerprint`. We monkeypatch that single function
    to return two different sentinel values around two key-recomputes —
    if the prepend isn't actually wired, the keys would match.
    """
    state = _node_base_state(node_name, tmp_path)
    with _patched_node_config_fingerprint(node_name, "cfg-fp-A"):
        before = _compute_key(node_name, state)
    with _patched_node_config_fingerprint(node_name, "cfg-fp-B"):
        after = _compute_key(node_name, state)
    assert before != after, (
        f"{node_name}: cache key did not change when node_config_fingerprint "
        f"flipped (A→B) — make_llm_key may have dropped the cfg extra "
        f"(HOM-157 regression)"
    )


def assert_canon_change_invalidates(node_name: str, *, tmp_path: Path) -> None:
    """An upstream canon edit MUST change the node's cache key (HOM-377).

    The node folds ``canon_fingerprint(node)`` into ``make_llm_key`` extras so
    a verbatim canon section it pulls invalidates exactly that node. We patch
    the ``canon_fingerprint`` symbol *imported into the node module* to two
    sentinels around two key-recomputes — if the ``canon:`` extra was dropped
    from ``_cache_key``, the keys would match and this fails. (Patching the
    node-module symbol, not the loader, mirrors how the node actually calls it:
    ``from .._canon_loader import canon_fingerprint``.)
    """
    mod = _load_node_module(node_name)
    if not hasattr(mod, "canon_fingerprint"):
        raise AssertionError(
            f"{node_name} module does not import canon_fingerprint — "
            "expected for a canon-consuming node (HOM-377)"
        )
    state = _node_base_state(node_name, tmp_path)
    original = mod.canon_fingerprint
    try:
        # HOM-166: canon_fingerprint is now called dir-fed for the
        # profile/brand-consuming nodes — ``canon_fingerprint(node,
        # profile_dir, brand_dir)`` (3 args) for p3_strategy / p3_edl_select /
        # p4_design_system / p4_prompt_expansion, still 1-arg elsewhere. The
        # sentinel must accept either arity.
        mod.canon_fingerprint = lambda *_a, **_k: "canon-fp-A"
        before = _compute_key(node_name, state)
        mod.canon_fingerprint = lambda *_a, **_k: "canon-fp-B"
        after = _compute_key(node_name, state)
    finally:
        mod.canon_fingerprint = original
    assert before != after, (
        f"{node_name}: cache key did not change when canon_fingerprint flipped "
        f"(A->B) — the `canon:` extra may have been dropped from _cache_key "
        f"(HOM-377 regression)"
    )


def assert_upstream_artifact_change_invalidates(
    node_name: str,
    *,
    tmp_path: Path,
    artifact_path: Path | None = None,
) -> None:
    """Mutating a load-bearing upstream input MUST change the cache key.

    The upstream input may be either a file in ``files=`` (pre-HOM-240
    shape — Phase 3 disk artifacts) or a state body in ``extras=``
    (post-HOM-240 shape — Phase 4 creative nodes after the state-first
    cutover). The per-node registry mutator decides which.

    Pass ``artifact_path`` to override and force a file edit at a custom
    path (used by the secondary-artifact focused test for p4_beat
    ``expanded-prompt.md``).
    """
    state = _node_base_state(node_name, tmp_path)
    before = _compute_key(node_name, state)
    if artifact_path is not None:
        target = Path(artifact_path)
        if not target.exists():
            raise FileNotFoundError(
                f"{node_name}: artifact override {target} not seeded by "
                "base-state factory"
            )
        target.write_bytes(target.read_bytes() + b"\n# fp-mutated\n")
        diagnostic = f"file {target} edited"
    else:
        mutator = _upstream_mutator(node_name)
        mutator(state)
        diagnostic = f"upstream_mutator for {node_name} ran"
    after = _compute_key(node_name, state)
    assert before != after, (
        f"{node_name}: cache key did not change when {diagnostic} "
        f"— files=/extras= may not cover this input"
    )


__all__ = [
    "assert_fingerprint_changes_when",
    "assert_brief_change_invalidates",
    "assert_model_change_invalidates",
    "assert_canon_change_invalidates",
    "assert_upstream_artifact_change_invalidates",
]
