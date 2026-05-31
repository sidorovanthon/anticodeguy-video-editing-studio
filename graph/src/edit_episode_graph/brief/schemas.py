"""Pydantic schemas for the profile + brand + episode-intent context layers.

Mirrors the YAML shapes in spec
`docs/superpowers/specs/2026-05-07-resolved-brief-profiles-brand-architecture.md`
§4. Profiles use a tight `extra="forbid"` schema (operator-authored, must fail
loud on a typo before reaching any LLM node). Brand `defaults` sub-sections are
permissive `dict` values — the operator iterates motion/grade/transition tuning
freely — but the top-level brand keys are still `extra="forbid"` to catch
section typos.

`skill_default` is the sentinel meaning "inherit the skill-canon default"; it is
NOT a hyperframes/skill version pin (memory
`feedback_no_version_pins_evolve_with_skills` — the system never pins versions).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SKILL_DEFAULT = "skill_default"


class OutputCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: int = Field(gt=0)


class CaptionsCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    mode: str | None = None
    safe_zone: str | None = None


class MusicProfileCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    default_mix_db: float | None = None


class CtaCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    placement: str | None = None


class PaddingCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    head_ms: int = Field(ge=0)
    tail_ms: int = Field(ge=0)


class EditCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    remove: list[str] = Field(default_factory=list)
    padding: PaddingCfg | None = None


class ProfileConfig(BaseModel):
    """A video-class profile (spec §3 — first-class abstraction, not a bool flag)."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1)
    human_label: str = Field(min_length=1)
    output: OutputCfg | None = None
    pacing: str = SKILL_DEFAULT
    structural_archetype: str = SKILL_DEFAULT
    rhythm_template: str = SKILL_DEFAULT
    captions: CaptionsCfg
    animation_density: str = SKILL_DEFAULT
    music: MusicProfileCfg
    cta: CtaCfg
    edit: EditCfg | None = None


class ContrastPair(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fg: str = Field(min_length=1)
    bg: str = Field(min_length=1)


class BrandPalette(BaseModel):
    model_config = ConfigDict(extra="forbid")
    colors: dict[str, str] = Field(default_factory=dict)
    typography: dict[str, str] = Field(default_factory=dict)
    contrast_pairs: list[ContrastPair] = Field(default_factory=list)


class BrandDefaults(BaseModel):
    """Brand-layer defaults laid OVER skill canon (spec §3 — brand wins on conflict).

    Sub-sections are permissive dicts so the operator can iterate; section keys
    are fixed (`extra="forbid"`) to catch typos. Anchors referenced by spec §9:
    `defaults.yaml.motion_language`, `.captions`, `.transitions`.
    """

    model_config = ConfigDict(extra="forbid")

    motion_language: dict[str, Any] = Field(default_factory=dict)
    captions: dict[str, Any] = Field(default_factory=dict)
    cta: dict[str, Any] = Field(default_factory=dict)
    grade: dict[str, Any] = Field(default_factory=dict)
    transitions: dict[str, Any] = Field(default_factory=dict)


class BrandKit(BaseModel):
    """Convenience bundle of the file-backed brand layers for one brand id."""

    model_config = ConfigDict(extra="forbid")

    brand_id: str = Field(min_length=1)
    palette: BrandPalette
    defaults: BrandDefaults


class IntentMusic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id: str | None = None
    volume_db: float | None = None


class EpisodeIntent(BaseModel):
    """Per-episode override layer (spec §4 — all fields optional)."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str | None = None
    brand_id: str | None = None
    narrative_context: str | None = None
    target_runtime_s: float | None = None
    must_preserves: list[str] = Field(default_factory=list)
    must_cuts: list[str] = Field(default_factory=list)
    music: IntentMusic | None = None
    animation_wishes: str | None = None
    grade_overrides: dict[str, Any] = Field(default_factory=dict)
    beat_overrides: dict[str, Any] = Field(default_factory=dict)
