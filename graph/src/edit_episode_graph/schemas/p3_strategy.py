# graph/src/edit_episode_graph/schemas/p3_strategy.py
"""Schema for p3_strategy output.

The absence of animation/subtitle fields is intentional: Phase 3 produces only
the cuts/grade strategy. Phase 4 owns hyperframes animation and captions.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Strategy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shape: str = Field(min_length=1, description="Plain-English narrative shape for the cut.")
    takes: list[str] = Field(default_factory=list, description="Take-selection guidance, by take or phrase.")
    grade: str = Field(min_length=1, description="Color/grade direction for the deterministic render step.")
    pacing: str = Field(min_length=1, description="Pacing guidance and target density.")
    length_estimate_s: float = Field(gt=0, description="Estimated final cut length in seconds.")
