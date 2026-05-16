"""Schema-migration smoke for HOM-231 (state-first artifacts Step A).

Asserts that a state dict shaped like a pre-HOM-231 checkpoint — only
``*_path`` body locators on the compose namespace, no ``compose.scenes``
or ``compose.*.{html,markdown,session_block,expanded_prompt,design_md}``
body fields — still parses cleanly under the new schema. The new fields
are all ``total=False``, so a TypedDict is forward-compatible by
construction; this test pins that contract so a future tightening
(e.g. promotion to a Pydantic ``BaseModel`` with required fields) breaks
loudly here instead of silently corrupting in-flight checkpoints.

CLAUDE.md §"Definition of done for LLM-node tickets" item 4 (schema
migration test, L0).
"""

from __future__ import annotations

from edit_episode_graph.state import (
    ComposeState,
    GraphState,
    TranscriptBodies,
    TranscriptsState,
    _scenes_merge,
)


def _old_shape_compose() -> dict:
    """A compose dict the way pre-HOM-231 nodes wrote it.

    Only path locators, no body fields. No ``scenes`` channel.
    """
    return {
        "hyperframes_dir": "/episodes/foo/hyperframes",
        "index_html_path": "/episodes/foo/hyperframes/index.html",
        "design": {
            "design_md_path": "/episodes/foo/hyperframes/.hyperframes/DESIGN.md",
            "style_name": "minimalist",
            "palette": [{"name": "ink", "hex": "#111"}],
        },
        "expansion": {
            "expanded_prompt_path": "/episodes/foo/hyperframes/.hyperframes/expanded-prompt.md",
        },
        "captions": {
            "captions_block_path": "/episodes/foo/hyperframes/compositions/captions.html",
            "cached": False,
        },
        "assemble": {
            "assembled_at": "2026-05-01T12:00:00Z",
            "beat_names": ["intro", "body", "outro"],
            "captions_included": True,
        },
        "persist": {
            "persisted_at": "2026-05-01T12:01:00Z",
            "session_n": 1,
        },
    }


def _old_shape_state() -> dict:
    return {
        "slug": "foo",
        "episode_dir": "/episodes/foo",
        "compose": _old_shape_compose(),
        "errors": [],
        "notices": [],
        "llm_runs": [],
        "gate_results": [],
        "strategy_revisions": [],
    }


def test_old_compose_shape_parses_under_new_schema() -> None:
    """An old-shape compose dict is a valid ``ComposeState`` value.

    TypedDicts are runtime ``dict``s — extra keys are ignored, missing
    optional keys are fine. The assertion that matters is structural:
    constructing the dict and reading expected keys back doesn't raise,
    and none of the new HOM-231 keys are required to be present.
    """
    compose: ComposeState = _old_shape_compose()  # type: ignore[assignment]
    # Existing path locators round-trip.
    assert compose["index_html_path"].endswith("index.html")
    assert compose["design"]["design_md_path"].endswith("DESIGN.md")
    assert compose["captions"]["captions_block_path"].endswith("captions.html")
    # New HOM-231 body fields are absent from the old shape — and that's fine.
    assert "scenes" not in compose
    assert "index_html" not in compose
    assert "materialize" not in compose
    assert "design_md" not in compose["design"]
    assert "expanded_prompt" not in compose["expansion"]
    assert "html" not in compose["captions"]
    assert "session_block" not in compose["persist"]


def test_old_top_level_state_parses() -> None:
    """A pre-HOM-231 ``GraphState`` snapshot is still a valid GraphState dict.

    HOM-234 also promoted ``scenes`` to a top-level channel; old snapshots
    never carried that key either, so it must be absent at the top level
    too. (The deprecated nested ``compose.scenes`` slot is also absent.)
    """
    state: GraphState = _old_shape_state()  # type: ignore[assignment]
    assert state["slug"] == "foo"
    assert "compose" in state
    assert "scenes" not in state["compose"]
    assert "scenes" not in state


def test_old_shape_roundtrips_through_jsonplus_serializer() -> None:
    """In-flight checkpoint compat — spec §6.1 / §12.2.

    The TypedDict-only assertions above pin the structural contract but
    pass trivially (TypedDict has no runtime validation). The actual
    risk per the spec is `JsonPlusSerializer` — LangGraph's checkpoint
    serde — failing to roundtrip an old-shape state dict written before
    HOM-231 added the new fields. This test exercises that path
    explicitly so a future serde tightening (custom type tags, schema
    versioning) breaks loudly here instead of corrupting in-flight
    threads on resume.
    """
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    serde = JsonPlusSerializer()
    original = _old_shape_state()
    type_tag, blob = serde.dumps_typed(original)
    restored = serde.loads_typed((type_tag, blob))

    assert restored == original
    # Spot-check the keys the new schema added — they must remain absent
    # post-roundtrip (forward-compat only, not auto-population).
    assert "scenes" not in restored["compose"]
    assert "scenes" not in restored  # HOM-234: top-level scenes channel.
    assert "html" not in restored["compose"]["captions"]
    assert "design_md" not in restored["compose"]["design"]


def test_old_transcripts_shape_parses_without_bodies_field() -> None:
    """HOM-279 forward-compat: a pre-HOM-279 ``transcripts`` dict
    (no ``bodies`` field) is still a valid ``TranscriptsState``.

    Pre-HOM-279 ``glue_remap_transcript`` emitted only ``edl_hash`` on
    success. Already-recorded fixture cache.db rows + in-flight
    checkpoints carry that shape and MUST keep parsing under the new
    schema — ``bodies`` is ``total=False``, so absence is a no-op.
    """
    old: TranscriptsState = {"edl_hash": "abc123"}  # type: ignore[assignment]
    assert old["edl_hash"] == "abc123"
    assert "bodies" not in old


def test_new_transcripts_bodies_field_is_total_false() -> None:
    """HOM-279: the four ``TranscriptBodies`` fields (raw, final,
    raw_path, final_path) are all optional. A partial body dict
    (e.g. ``raw`` only, ``final`` still ``None``) is valid — that's
    the in-flight shape between Phase-3 raw transcription and the
    EDL remap step.
    """
    partial: TranscriptBodies = {"raw": "{}", "raw_path": "/x/raw.json"}  # type: ignore[assignment]
    assert partial["raw"] == "{}"
    assert "final" not in partial
    full: TranscriptBodies = {
        "raw": "{}",
        "final": '{"edl_hash":"x"}',
        "raw_path": "/x/raw.json",
        "final_path": "/x/final.json",
    }  # type: ignore[assignment]
    transcripts: TranscriptsState = {
        "edl_hash": "x",
        "bodies": full,
    }  # type: ignore[assignment]
    assert transcripts["bodies"]["final"].startswith("{")


def test_old_transcripts_shape_roundtrips_through_jsonplus_serializer() -> None:
    """HOM-279: pre-HOM-279 ``transcripts`` (no ``bodies``) roundtrips
    through the LangGraph checkpoint serializer cleanly. Guards the
    same in-flight-checkpoint contract as the compose-shape roundtrip.
    """
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    serde = JsonPlusSerializer()
    state = {
        **_old_shape_state(),
        "transcripts": {"edl_hash": "abc123"},
    }
    type_tag, blob = serde.dumps_typed(state)
    restored = serde.loads_typed((type_tag, blob))
    assert restored == state
    assert "bodies" not in restored["transcripts"]


def test_new_scenes_field_merges_via_reducer_when_added() -> None:
    """A migrated state can grow `scenes` incrementally without breaking
    the existing ``compose`` shape — i.e. the new field plays nicely with
    the rest of the namespace via ``_scenes_merge``.
    """
    base = _old_shape_compose()
    updated_scenes = _scenes_merge(
        base.get("scenes", {}),
        {"intro": {"html": "<intro/>"}, "outro": {"html": "<outro/>"}},
    )
    base["scenes"] = updated_scenes
    assert list(base["scenes"].keys()) == ["intro", "outro"]
    # Old keys still present and untouched.
    assert base["index_html_path"].endswith("index.html")
    assert base["design"]["design_md_path"].endswith("DESIGN.md")
