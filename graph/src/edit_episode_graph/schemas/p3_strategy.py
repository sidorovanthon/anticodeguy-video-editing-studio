# graph/src/edit_episode_graph/schemas/p3_strategy.py
"""Schema for p3_strategy output.

The absence of animation/subtitle fields is intentional: Phase 3 produces only
the cuts/grade strategy. Phase 4 owns hyperframes animation and captions.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Strategy(BaseModel):
    # HOM-166 (spec §7): extra="allow" + prose fields. The strategist agent
    # produces prose the narrow 5-field shape dropped; `rationale` /
    # `taste_notes` carry it downstream alongside the structural fields. Both
    # optional (default "") so pre-HOM-166 recordings still validate.
    model_config = ConfigDict(extra="allow")

    shape: str = Field(min_length=1, description="Plain-English narrative shape for the cut.")
    takes: list[str] = Field(default_factory=list, description="Take-selection guidance, by take or phrase.")
    grade: str = Field(min_length=1, description="Color/grade direction for the deterministic render step.")
    pacing: str = Field(min_length=1, description="Pacing guidance and target density.")
    length_estimate_s: float = Field(gt=0, description="Estimated final cut length in seconds.")
    rationale: str = Field(default="", description="3-6 sentences of prose justifying the strategy.")
    taste_notes: str = Field(default="", description="Free-form markdown taste notes (tone, brand fit).")
