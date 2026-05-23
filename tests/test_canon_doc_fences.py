"""Catch nested/orphaned code fences in canon walkthroughs.

CommonMark fences do not nest with the same backtick count. Two adjacent ``` lines
with no content between produce an empty rendered code block in GitHub / VSCode preview.
Bumping the outer fence to four backticks (````) lets a 3-backtick fence nest inside.
"""

from __future__ import annotations

from pathlib import Path

import pytest

CANON_DIR = Path(__file__).resolve().parent.parent / "docs" / "canon"


def _adjacent_bare_fences(path: Path) -> list[tuple[int, int]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    prev: int | None = None
    hits: list[tuple[int, int]] = []
    for idx, line in enumerate(lines, 1):
        if line.strip() == "```":
            if prev is not None and idx - prev == 1:
                hits.append((prev, idx))
            prev = idx
    return hits


@pytest.mark.parametrize("doc", sorted(CANON_DIR.glob("*.md")))
def test_no_adjacent_bare_fences(doc: Path) -> None:
    hits = _adjacent_bare_fences(doc)
    assert not hits, (
        f"{doc.relative_to(CANON_DIR.parent.parent)} has adjacent bare ``` fences at "
        f"{hits} — produces empty rendered code block. Bump outer fence to ```` if "
        f"nesting a code block inside a prose-quote fence."
    )
