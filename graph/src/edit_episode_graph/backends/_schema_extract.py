"""Extract a Pydantic model from free-form LLM assistant text.

Handles the common shapes: (a) a ```json ... ``` fenced block, (b) a ``` ... ```
unfenced block, (c) bare JSON. Raises SchemaValidationError on any failure
with the raw text attached so the router can surface it as feedback on retry.
"""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from ._types import SchemaValidationError

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)
_BARE_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


def extract_structured(raw_text: str, schema: type[T]) -> T:
    candidates: list[str] = []
    candidates.extend(m.group(1) for m in _FENCE_RE.finditer(raw_text))
    if not candidates:
        m = _BARE_RE.search(raw_text)
        if m:
            candidates.append(m.group(1))

    if not candidates:
        raise SchemaValidationError("no JSON object/array found in assistant text", raw_text)

    last_err: Exception | None = None
    for cand in candidates:
        try:
            data = json.loads(cand)
        except json.JSONDecodeError as e:
            last_err = e
            continue
        try:
            return schema.model_validate(data)
        except ValidationError as e:
            last_err = e
            continue
    raise SchemaValidationError(f"schema validation failed: {last_err}", raw_text)
