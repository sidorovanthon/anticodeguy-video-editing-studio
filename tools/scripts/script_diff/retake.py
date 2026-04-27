"""Detect retakes: script spans that occur multiple times in the raw recording."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from .normalize import Token


RATIO_THRESHOLD = 0.85
MIN_SPAN_TOKENS = 3


@dataclass
class Retake:
    text: str                              # script span text
    raw_ranges: list[tuple[float, float]]  # (start, end) seconds for each raw match
    kept_range: tuple[float, float] | None # the raw_range that survived in the final, if any


def _span_in_kept(start: float, end: float, edl: dict) -> bool:
    """A raw range counts as kept if its start sits in any EDL kept range
    (matches reconstruct.py's 'is the word kept' rule)."""
    for r in edl.get("ranges", []):
        if r.get("source") != "raw":
            continue
        if float(r["start"]) <= start < float(r["end"]):
            return True
    return False


def _find_matches(script_span_text: list[str],
                  raw_tokens: list[Token]) -> list[tuple[int, int]]:
    """Slide a window of len(script_span_text) over raw_tokens; return list of
    (start_idx, end_idx_exclusive) where SequenceMatcher.ratio >= RATIO_THRESHOLD.
    Greedy: when a match is found at position i, jump past it (i + len) before
    looking for the next, so two adjacent retakes don't get merged.
    """
    n = len(script_span_text)
    matches: list[tuple[int, int]] = []
    i = 0
    while i + n <= len(raw_tokens):
        window = [t.text for t in raw_tokens[i:i + n]]
        sm = SequenceMatcher(a=script_span_text, b=window, autojunk=False)
        if sm.ratio() >= RATIO_THRESHOLD:
            matches.append((i, i + n))
            i += n
        else:
            i += 1
    return matches


def find_retakes(script_tokens: list[Token],
                 raw_tokens: list[Token],
                 edl: dict,
                 span_size: int = 6) -> list[Retake]:
    """Walk the script in non-overlapping spans of `span_size` tokens; for each
    span, count matches in raw_tokens. Spans matching >= 2 times are retakes.
    """
    results: list[Retake] = []
    if span_size < MIN_SPAN_TOKENS:
        span_size = MIN_SPAN_TOKENS

    for s in range(0, len(script_tokens) - span_size + 1, span_size):
        span = script_tokens[s:s + span_size]
        span_text = [t.text for t in span]
        matches = _find_matches(span_text, raw_tokens)
        if len(matches) < 2:
            continue
        raw_ranges: list[tuple[float, float]] = []
        kept: tuple[float, float] | None = None
        for (lo, hi) in matches:
            r_start = raw_tokens[lo].start or 0.0
            r_end = raw_tokens[hi - 1].end or r_start
            raw_ranges.append((r_start, r_end))
            if kept is None and _span_in_kept(r_start, r_end, edl):
                kept = (r_start, r_end)
        results.append(Retake(
            text=" ".join(span_text),
            raw_ranges=raw_ranges,
            kept_range=kept,
        ))
    return results
