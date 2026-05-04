"""Schema for p3_edl_select output.

Mirrors video-use SKILL.md §"EDL format". Phase 3 orchestrator policy keeps
animations and subtitles out of the cut: `overlays` defaults to `[]` and there
is intentionally **no** `subtitles` field. `extra="forbid"` makes the absence
load-bearing — the LLM cannot smuggle a subtitle path past the gate.

HR 6 (word-boundary cuts) and HR 7 (30–200ms padding) are validated by
`gates.edl_ok`, not by this schema; the schema only constrains shape.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Overlay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str = Field(min_length=1)
    start_in_output: float = Field(ge=0)
    duration: float = Field(gt=0)


class Range(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, description="Key into EDL.sources.")
    start: float = Field(ge=0, description="Cut start in source seconds.")
    end: float = Field(gt=0, description="Cut end in source seconds.")
    beat: str = Field(min_length=1, description="Narrative beat label, e.g. HOOK / SOLUTION.")
    quote: str = Field(min_length=1, description="Verbatim transcript phrase used by this range.")
    reason: str = Field(min_length=1, description="One-line rationale for take selection.")

    @model_validator(mode="after")
    def _end_after_start(self) -> "Range":
        if self.end <= self.start:
            raise ValueError(f"end ({self.end}) must be greater than start ({self.start})")
        return self


class EDL(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, ge=1)
    sources: dict[str, str] = Field(description="Source key -> absolute path on disk.")
    ranges: list[Range] = Field(min_length=1)
    grade: str = Field(min_length=1, description="Preset name or raw ffmpeg filter.")
    overlays: list[Overlay] = Field(default_factory=list)
    total_duration_s: float = Field(gt=0)
