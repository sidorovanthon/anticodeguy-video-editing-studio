import pytest
from pydantic import BaseModel

from edit_episode_graph.backends._schema_extract import extract_structured
from edit_episode_graph.backends._types import SchemaValidationError


class _Demo(BaseModel):
    n: int
    label: str


def test_extracts_from_fenced_block():
    raw = "Here is the result:\n```json\n{\"n\": 7, \"label\": \"ok\"}\n```\nDone."
    out = extract_structured(raw, _Demo)
    assert out.n == 7 and out.label == "ok"


def test_extracts_bare_json():
    raw = '{"n": 1, "label": "bare"}'
    out = extract_structured(raw, _Demo)
    assert out.label == "bare"


def test_validation_error_includes_raw():
    raw = '```json\n{"n": "not-a-number", "label": 1}\n```'
    with pytest.raises(SchemaValidationError) as exc:
        extract_structured(raw, _Demo)
    assert exc.value.raw_text == raw


def test_no_json_at_all_raises():
    with pytest.raises(SchemaValidationError):
        extract_structured("just prose", _Demo)


class _Nested(BaseModel):
    items: list[_Demo]


def test_extracts_nested_object_from_fence():
    raw = '```json\n{"items":[{"n":1,"label":"a"},{"n":2,"label":"b"}]}\n```'
    out = extract_structured(raw, _Nested)
    assert len(out.items) == 2
    assert out.items[1].label == "b"


@pytest.mark.parametrize("tag", ["jsonl", "python", "JSON", "json5", "ndjson"])
def test_extracts_from_fence_with_arbitrary_language_tag(tag):
    raw = f"prefix\n```{tag}\n{{\"n\": 3, \"label\": \"tagged\"}}\n```\nsuffix"
    out = extract_structured(raw, _Demo)
    assert out.n == 3 and out.label == "tagged"


def test_extracts_from_unfenced_triple_backtick_block():
    raw = "intro\n```\n{\"n\": 9, \"label\": \"plain\"}\n```\nend"
    out = extract_structured(raw, _Demo)
    assert out.n == 9 and out.label == "plain"
