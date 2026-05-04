"""Schema for p4_design_system output.

Mirrors hyperframes SKILL.md §"Step 1: Design system" + `visual-styles.md`
+ `references/design-picker.md`. The dispatched sub-agent reads canon and
writes a real `DESIGN.md` (YAML frontmatter + prose sections) to disk; the
JSON returned to the graph is the *substance check input* used by
`gate:design_ok`. Both surfaces matter — the YAML feeds downstream beat
sub-agents, the structured object lets the gate enforce coverage without
re-parsing markdown.

Substance bounds (`refs ≥ 2`, `alternatives ≥ 1`, `anti_patterns ≥ 3`,
non-empty `beat_visual_mapping`) come from the HOM-118 ticket and are
load-bearing — they prevent the LLM from emitting a one-line palette + a
generic "avoid neon" list and calling it a design system. The gate
re-asserts these so a schema-only validation regression never silently
weakens enforcement.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


_HEX_RE = re.compile(r"^#[0-9a-fA-F]{3}([0-9a-fA-F]{3}([0-9a-fA-F]{2})?)?$")


class PaletteEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1, description="e.g. background / foreground / accent / surface.")
    hex: str = Field(description="CSS hex color, including the leading `#`.")

    @field_validator("hex")
    @classmethod
    def _hex_shape(cls, v: str) -> str:
        if not _HEX_RE.match(v):
            raise ValueError(f"hex {v!r} not a valid CSS hex color")
        return v


class TypographyEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1, description="e.g. headline / body / label / stat.")
    family: str = Field(min_length=1, description="font-family value as it will appear in CSS.")
    weight: int | None = Field(default=None, ge=100, le=900)
    size: str | None = Field(default=None, description="CSS size token, e.g. `4rem`, `120px`.")


class VisualReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, description="Designer / movement / brand the reference points at.")
    description: str = Field(
        min_length=1,
        description="One sentence on which specific aspect (typography, palette, motion) is being referenced.",
    )


class Alternative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="Direction considered (e.g. `Folk Frequency`).")
    rejected_because: str = Field(min_length=1, description="Why this direction was not chosen.")


class BeatVisualMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat: str = Field(min_length=1, description="Beat label as it will appear in the composition plan.")
    treatment: str = Field(
        min_length=1,
        description="One sentence on the visual treatment for that beat — palette emphasis, typography "
                    "scale, motion intensity, decoratives.",
    )


class DesignDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style_name: str = Field(
        min_length=1,
        description="Canonical visual-style name (one of the 8 in `visual-styles.md`) or a custom name "
                    "when the brand calls for a fresh direction.",
    )
    palette: list[PaletteEntry] = Field(
        min_length=2,
        description="At least background + foreground; usually background + foreground + accent.",
    )
    typography: list[TypographyEntry] = Field(min_length=1)
    refs: list[VisualReference] = Field(min_length=2)
    alternatives: list[Alternative] = Field(min_length=1)
    anti_patterns: list[str] = Field(min_length=3)
    beat_visual_mapping: list[BeatVisualMapping] = Field(min_length=1)
    design_md_path: str = Field(
        min_length=1,
        description="Absolute path to the DESIGN.md the sub-agent wrote to disk.",
    )
