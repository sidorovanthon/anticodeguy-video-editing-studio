"""Schema for p3_self_eval output.

Mirrors video-use SKILL.md §"The process" Step 7. Phase 3 has no overlays
and no subtitles, so HR 1 (subtitles last) and HR 4 (overlay PTS-shift)
checks fall to Phase 4. The remaining canon checks at this stage are visual
discontinuity at cuts, audio-pop past the 30ms fade (HR 3), and grade
consistency across the rendered output. ffprobe duration vs
`total_duration_s` is checked deterministically by `gate:eval_ok`.

`passed` is the sub-agent's final verdict; `gate:eval_ok` cross-checks it
together with iteration cap and ffprobe duration so a misjudged "passed"
still gets caught when the rendered duration disagrees with the EDL.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EvalIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(
        min_length=1,
        description="Issue category: visual_discontinuity | audio_pop | grade_drift | duration_mismatch | other.",
    )
    location: str = Field(
        min_length=1,
        description="Where in the output: cut boundary index or output timestamp (e.g. `cut[2]@1.42s`).",
    )
    severity: str = Field(
        min_length=1,
        description="`blocker` (must re-render) or `note` (acceptable, recorded for reviewer).",
    )
    note: str = Field(min_length=1, description="One-line description of what was observed.")


class EvalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[EvalIssue] = Field(default_factory=list)
    passed: bool = Field(description="True when no blocker-severity issues remain.")
