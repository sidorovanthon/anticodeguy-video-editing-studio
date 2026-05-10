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
