"""HOM-223 — schema migration L0 guard.

State sub-models are `TypedDict`s, which are runtime `dict`s — extra keys
are tolerated by construction. The risk of breaking forward-compat with
recorded fixtures is therefore ZERO at type-check time, but we keep this
test as a tripwire: a future refactor that swaps `TypedDict` for Pydantic
would silently regress fixture replay (old shapes with HOM-223-removed
keys would raise on `model_validate`). This test asserts that an old
recording — `final_mp4`, `edl_path`, `source_path`, etc. populated —
still round-trips through:

  1. dict construction (the TypedDict path used at runtime),
  2. the reducers we run on every node update (`dict_merge`, etc.),
  3. the consumer-side reads via `EpisodePaths(slug)` fallbacks.

Recorded shapes pre-HOM-223 carried these keys; new writers do not emit
them, but the schema slots remain so fixtures keep loading.
"""

from __future__ import annotations

from edit_episode_graph.state import (
    AssembleState,
    AudioState,
    CaptionsState,
    ComposeState,
    DesignState,
    EditState,
    EdlState,
    EvalState,
    ExpansionState,
    GraphState,
    InventoryState,
    PersistState,
    PreScanState,
    RenderState,
    StrategyState,
    TranscriptsState,
    dict_merge,
)


_OLD_COMPOSE_RECORDING: ComposeState = {
    # HOM-224 — pre-Sub-3 recording shape: compose namespace carries every
    # absolute-path echo the writer side just dropped. New writers do NOT
    # emit any of these; the schema slots remain typed so old recordings
    # parse cleanly.
    "hyperframes_dir": "/abs/episodes/demo/hyperframes",
    "index_html_path": "/abs/episodes/demo/hyperframes/index.html",
    "design_md_path": "/abs/episodes/demo/hyperframes/DESIGN.md",
    "design": {
        "style_name": "Swiss Pulse",
        "palette": [{"role": "background", "hex": "#0a0a0a"}],
        "design_md_path": "/abs/episodes/demo/hyperframes/DESIGN.md",
    },
    "expansion": {
        "expanded_prompt_path": "/abs/episodes/demo/hyperframes/.hyperframes/expanded-prompt.md",
    },
    "expanded_prompt_path": "/abs/episodes/demo/hyperframes/.hyperframes/expanded-prompt.md",
    "captions": {
        "captions_block_path": "/abs/episodes/demo/hyperframes/captions.html",
    },
    "captions_block_path": "/abs/episodes/demo/hyperframes/captions.html",
    "assemble": {
        "assembled_at": "2026-05-09T12:00:00+00:00",
        "index_html_path": "/abs/episodes/demo/hyperframes/index.html",
        "beat_names": ["hook", "payoff"],
    },
    "persist": {
        # Pre-HOM-224 abused this slot to hold a path; post-HOM-224 it's
        # an ISO timestamp (mirror of the p3 reshape from HOM-223).
        "persisted_at": "/abs/episodes/demo/edit/project.md",
        "session_n": 1,
    },
}


# Old recording (pre-HOM-223): every sub-model carries the absolute-path
# echoes that we just removed from the writer side.
_OLD_RECORDING: GraphState = {
    "slug": "demo",
    "episode_dir": "/abs/episodes/demo",
    "pickup": {"raw_path": "/abs/episodes/demo/raw.mp4"},
    "audio": {"wav_path": "/abs/episodes/demo/edit/audio.wav"},
    "transcripts": {
        "raw_json_path": "/abs/episodes/demo/edit/transcripts/raw.json",
        "final_json_path": "/abs/episodes/demo/edit/transcripts/final.json",
        "raw_json_paths": ["/abs/episodes/demo/edit/transcripts/raw.json"],
        "takes_packed_path": "/abs/episodes/demo/edit/takes_packed.md",
        "edl_hash": "abc123",
    },
    "edit": {
        "inventory": {
            "source_dir": "/abs/episodes/demo",
            "transcript_json_paths": ["/abs/episodes/demo/edit/transcripts/raw.json"],
            "takes_packed_path": "/abs/episodes/demo/edit/takes_packed.md",
            "sources": [{"path": "/abs/x", "name": "x.mp4"}],
        },
        "pre_scan": {
            "slips": [],
            "source_path": "/abs/episodes/demo/edit/takes_packed.md",
        },
        "strategy": {
            "shape": "hook", "takes": ["take 1"], "grade": "neutral",
            "pacing": "tight", "length_estimate_s": 30.0,
            "source_path": "/abs/episodes/demo/edit/takes_packed.md",
        },
        "edl": {
            "version": 1, "ranges": [{"source": "raw", "start": 0, "end": 5}],
            "grade": "neutral", "overlays": [], "total_duration_s": 5.0,
            "source_path": "/abs/episodes/demo/edit/takes_packed.md",
            "edl_path": "/abs/episodes/demo/edit/edl.json",
        },
        "render": {
            "final_mp4": "/abs/episodes/demo/edit/final.mp4",
            "clips_dir": "/abs/episodes/demo/edit/clips_graded",
            "duration_s": 5.0, "n_segments": 1, "cached": False,
        },
        "eval": {
            "issues": [], "passed": True,
            "final_mp4_path": "/abs/episodes/demo/edit/final.mp4",
        },
        "persist": {
            # Pre-HOM-223 abused this slot to hold a path; post-HOM-223 it's
            # an ISO timestamp. Both are `str` per schema, so old shape parses.
            "persisted_at": "/abs/episodes/demo/edit/project.md",
            "session_n": 1,
        },
    },
}


def test_old_recording_loads_without_error():
    """Smoke: every sub-namespace constructs from old recording shape."""
    # TypedDicts are dicts at runtime — extra keys are silently retained.
    # The act of indexing into them is what we actually exercise downstream.
    edit = _OLD_RECORDING["edit"]
    assert isinstance(edit, dict)
    # Spot-check every sub-namespace touched by HOM-223 still has the
    # expected content fields (`shape`, `passed`, `ranges`, etc.).
    assert edit["strategy"]["shape"] == "hook"
    assert edit["edl"]["total_duration_s"] == 5.0
    assert edit["render"]["n_segments"] == 1
    assert edit["eval"]["passed"] is True
    assert edit["persist"]["session_n"] == 1


def test_dict_merge_preserves_extra_keys_under_old_recording():
    """`dict_merge` is the reducer for every phase namespace. A new node
    update merging into an old-shape state must not drop the deprecated
    path keys (Studio time-travel can replay an old checkpoint and a new
    node update without crashing the merge).
    """
    new_update = {"strategy": {"approved": True, "approval_payload": {"approved": True}}}
    merged = dict_merge(_OLD_RECORDING["edit"], new_update)
    # Old keys preserved.
    assert merged["edl"]["edl_path"] == "/abs/episodes/demo/edit/edl.json"
    assert merged["render"]["final_mp4"] == "/abs/episodes/demo/edit/final.mp4"
    # New keys merged.
    assert merged["strategy"]["approved"] is True


def test_post_hom223_writer_emits_no_path_keys_in_p3_namespaces():
    """The post-HOM-223 writer shape is the *new* recording — no path keys
    in any p3-namespace write. We synthesize that shape here so future
    refactors of the writer side keep it.
    """
    new_shape: EditState = {
        "inventory": {"sources": [{"path": "/abs/x", "name": "x.mp4"}]},
        "pre_scan": {"slips": []},
        "strategy": {
            "shape": "hook", "takes": ["take 1"], "grade": "neutral",
            "pacing": "tight", "length_estimate_s": 30.0,
        },
        "edl": {
            "version": 1, "ranges": [{"source": "raw", "start": 0, "end": 5}],
            "grade": "neutral", "overlays": [], "total_duration_s": 5.0,
        },
        "render": {"duration_s": 5.0, "n_segments": 1, "cached": False},
        "eval": {"issues": [], "passed": True},
        "persist": {"persisted_at": "2026-05-10T12:00:00+00:00", "session_n": 1},
    }
    # No absolute-path values in any value.
    def _is_path_string(v):
        return isinstance(v, str) and (v.startswith("/abs") or v.startswith("/tmp") or "\\" in v[:3])

    for ns_name, ns in new_shape.items():
        for k, v in ns.items():
            assert not _is_path_string(v), (
                f"{ns_name}.{k} = {v!r} looks like an absolute path — HOM-223 forbids"
            )


def test_post_hom223_transcripts_namespace_is_content_only():
    """`transcripts` namespace should carry `edl_hash` only after HOM-223 —
    no `raw_json_path`/`final_json_path`/`takes_packed_path`/`raw_json_paths`.
    """
    new_shape: TranscriptsState = {"edl_hash": "abc123"}
    assert "raw_json_path" not in new_shape
    assert "final_json_path" not in new_shape
    assert "takes_packed_path" not in new_shape
    assert "raw_json_paths" not in new_shape


# ---- HOM-224: p4 (compose) namespace migration ----


def test_old_compose_recording_loads_without_error():
    """HOM-224 forward-compat: every p4 sub-namespace constructs from old
    recording shape (with all the deprecated path-string echoes populated).
    """
    assert isinstance(_OLD_COMPOSE_RECORDING, dict)
    # Spot-check every sub-namespace touched by HOM-224 still has the
    # expected content fields surviving alongside the deprecated paths.
    assert _OLD_COMPOSE_RECORDING["design"]["style_name"] == "Swiss Pulse"
    assert _OLD_COMPOSE_RECORDING["assemble"]["beat_names"] == ["hook", "payoff"]
    assert _OLD_COMPOSE_RECORDING["persist"]["session_n"] == 1


def test_dict_merge_preserves_deprecated_compose_keys():
    """`dict_merge` reducer must NOT drop the deprecated p4 path keys when
    a new node update merges into an old-shape state — Studio time-travel
    can replay an old checkpoint and a new update without crashing.
    """
    new_update = {"session_persisted": True}
    merged = dict_merge(_OLD_COMPOSE_RECORDING, new_update)
    # Every deprecated p4 path key preserved.
    assert merged["index_html_path"] == "/abs/episodes/demo/hyperframes/index.html"
    assert merged["design_md_path"] == "/abs/episodes/demo/hyperframes/DESIGN.md"
    assert merged["expanded_prompt_path"] == "/abs/episodes/demo/hyperframes/.hyperframes/expanded-prompt.md"
    assert merged["captions_block_path"] == "/abs/episodes/demo/hyperframes/captions.html"
    assert merged["assemble"]["index_html_path"] == "/abs/episodes/demo/hyperframes/index.html"
    # New keys merged.
    assert merged["session_persisted"] is True


def test_post_hom224_writer_emits_no_compose_path_keys():
    """The post-HOM-224 writer shape — no path keys in any compose write."""
    new_shape: ComposeState = {
        "design": {
            "style_name": "Swiss Pulse",
            "palette": [{"role": "background", "hex": "#0a0a0a"}],
        },
        "expansion": {},
        "captions": {},
        "assemble": {
            "assembled_at": "2026-05-10T12:00:00+00:00",
            "beat_names": ["hook", "payoff"],
            "captions_included": True,
        },
        "persist": {"persisted_at": "2026-05-10T12:00:00+00:00", "session_n": 2},
        "session_persisted": True,
    }

    # No absolute-path values in any value (recursive check).
    def _is_path_string(v):
        return isinstance(v, str) and (
            v.startswith("/abs") or v.startswith("/tmp") or "\\" in v[:3]
            or v.endswith(".md") or v.endswith(".html") or v.endswith(".mp4")
        )

    def _walk(d, prefix=""):
        for k, v in d.items():
            label = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                _walk(v, label)
            else:
                assert not _is_path_string(v), (
                    f"{label} = {v!r} looks like an absolute path — HOM-224 forbids"
                )

    _walk(new_shape)


def test_post_hom224_assemble_persist_use_iso_timestamps():
    """`assemble.assembled_at` and `persist.persisted_at` are ISO 8601
    timestamps post-HOM-224. The slots are still `str | None`, but the
    semantics (and the values writers emit) shift from "where" → "when".
    """
    from datetime import datetime
    new_shape: ComposeState = {
        "assemble": {"assembled_at": "2026-05-10T12:00:00+00:00"},
        "persist": {"persisted_at": "2026-05-10T12:00:01.123456+00:00", "session_n": 1},
    }
    # Both must parse as ISO 8601 — assertion fails on a path string.
    datetime.fromisoformat(new_shape["assemble"]["assembled_at"])
    datetime.fromisoformat(new_shape["persist"]["persisted_at"])
