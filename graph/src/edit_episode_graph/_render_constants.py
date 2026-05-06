"""Shared render-physics constants for Phase 3.

Single source of truth for cross-validation between `p3_render_segments`
(produces `final.mp4`) and `gate:eval_ok` (validates duration). Keeping
these here prevents the two call sites from drifting independently — see
HOM-107 PR review where the formula started life duplicated and required
this consolidation.
"""

from __future__ import annotations


_TOLERANCE_CAP_MS = 500


def duration_tolerance_ms(n_segments: int) -> int:
    """Acceptable drift between EDL-arithmetic and rendered final.mp4.

    Canon `render.py` re-encodes to 24fps (libx264 `-r 24`); each segment
    edge snaps to the 24fps grid (~42ms max per boundary, random direction).
    With N segments there are 2N edges contributing independent drift, plus
    per-segment container/timestamp overhead from the concat.

    Empirically (HOM-107 integration smoke), a 5-segment 24fps render
    drifts ~220ms vs sum-of-EDL-ranges — within physics, not a render bug.

    The original HOM-103 DoD threshold of 100ms was tuned against
    1-2-segment test EDLs and false-flagged healthy 5-segment renders.
    Linear formula `100 + 50*N` keeps the 1-segment baseline (~150ms)
    close to original intent while permitting frame-snap physics on
    longer EDLs. Genuine render-pipeline failures (dropped segments,
    broken concat, multi-second audio drift) still trip it — they
    produce deltas measured in seconds, not the hundreds-of-ms
    band this function permits.

    Hard cap at 500ms (HOM-116d): the linear formula keeps growing
    without ceiling — at N=20 → 1100ms, N=30 → 1600ms — wide enough to
    mask real render bugs on long-form content. 500ms = 12 frames at
    24fps, well above the random-walk frame-snap aggregate
    (`sqrt(2N) * 21ms` ≈ 130ms at N=20) we'd expect on a healthy
    render but small enough to still catch single-segment-dropped
    failures (which produce seconds of drift). The cap kicks in at
    N=8; below that the linear formula already gives more headroom.
    """
    return min(100 + 50 * n_segments, _TOLERANCE_CAP_MS)
