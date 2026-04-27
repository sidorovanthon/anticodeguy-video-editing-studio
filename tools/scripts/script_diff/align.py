"""Word-level alignment between a script token list and a target token list."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from .normalize import Token


MIN_SPAN_TOKENS = 3


@dataclass
class Span:
    """A contiguous slice of script_tokens or target_tokens (depending on side)."""
    text: str                 # space-joined token texts
    tokens: list[Token]       # the actual tokens in this span (target side carries times)
    script_index: int         # start index in script_tokens (always populated)
    target_index: int         # start index in target_tokens (always populated)


@dataclass
class DiffResult:
    script_tokens: list[Token]
    target_tokens: list[Token]
    dropped: list[Span]   # in script, not in target
    inserted: list[Span]  # in target, not in script
    matched_script_count: int  # number of script tokens classified as 'equal'


def _span_from(side_tokens: list[Token], lo: int, hi: int,
               script_index: int, target_index: int) -> Span:
    slc = side_tokens[lo:hi]
    return Span(
        text=" ".join(t.text for t in slc),
        tokens=slc,
        script_index=script_index,
        target_index=target_index,
    )


def diff(script_tokens: list[Token], target_tokens: list[Token]) -> DiffResult:
    """Run SequenceMatcher on the .text of each side and pull out spans."""
    s_text = [t.text for t in script_tokens]
    t_text = [t.text for t in target_tokens]
    sm = SequenceMatcher(a=s_text, b=t_text, autojunk=False)

    dropped: list[Span] = []
    inserted: list[Span] = []
    matched = 0

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            matched += (i2 - i1)
        elif tag == "delete":
            if (i2 - i1) >= MIN_SPAN_TOKENS:
                dropped.append(_span_from(script_tokens, i1, i2, i1, j1))
        elif tag == "insert":
            if (j2 - j1) >= MIN_SPAN_TOKENS:
                inserted.append(_span_from(target_tokens, j1, j2, i1, j1))
        elif tag == "replace":
            if (i2 - i1) >= MIN_SPAN_TOKENS:
                dropped.append(_span_from(script_tokens, i1, i2, i1, j1))
            if (j2 - j1) >= MIN_SPAN_TOKENS:
                inserted.append(_span_from(target_tokens, j1, j2, i1, j1))

    return DiffResult(
        script_tokens=script_tokens,
        target_tokens=target_tokens,
        dropped=dropped,
        inserted=inserted,
        matched_script_count=matched,
    )
