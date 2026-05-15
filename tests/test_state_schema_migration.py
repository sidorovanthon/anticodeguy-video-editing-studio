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
