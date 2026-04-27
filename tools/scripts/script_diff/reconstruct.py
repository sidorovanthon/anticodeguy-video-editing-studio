"""Reconstruct the final-audio token sequence from raw words + an EDL."""
from __future__ import annotations

from .normalize import Token


def reconstruct_final(raw_tokens: list[Token], edl: dict) -> list[Token]:
    """Return raw_tokens whose start time falls inside any EDL range.
    Half-open intervals: [range.start, range.end). Output preserves raw order
    (EDL ranges are required to be non-overlapping and sorted by spec).
    """
    ranges = [(float(r["start"]), float(r["end"]))
              for r in edl.get("ranges", []) if r.get("source") == "raw"]
    if not ranges:
        return []

    out: list[Token] = []
    ri = 0
    for tok in raw_tokens:
        if tok.start is None:
            continue
        # Advance ranges pointer while token start is past current range end.
        while ri < len(ranges) and tok.start >= ranges[ri][1]:
            ri += 1
        if ri >= len(ranges):
            break
        r_start, r_end = ranges[ri]
        if r_start <= tok.start < r_end:
            out.append(tok)
    return out
