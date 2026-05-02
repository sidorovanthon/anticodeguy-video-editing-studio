# graph/src/edit_episode_graph/schemas/p3_pre_scan.py
"""Schema for p3_pre_scan output.

Mirrors video-use SKILL.md §"The process" Step 2: "verbal slips, obvious
mis-speaks, or phrasings to avoid". A slip is a single phrase the editor
should skip; `take_index` is optional because some slips span multiple takes
or are not anchored to a specific `## Take N` header.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Slip(BaseModel):
    quote: str = Field(min_length=1, description="Exact phrase from takes_packed.md to avoid in the cut.")
    take_index: int | None = Field(default=None, description="Take number where the slip occurs, if anchored.")
    reason: str = Field(min_length=1, description="Why the editor should skip this — slip, mis-speak, off-topic, etc.")


class PreScanReport(BaseModel):
    slips: list[Slip] = Field(default_factory=list)
