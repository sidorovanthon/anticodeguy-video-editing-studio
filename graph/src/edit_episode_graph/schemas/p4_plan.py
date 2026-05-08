"""Schema for p4_plan output.

Mirrors hyperframes SKILL.md §"Step 3: Plan" + `references/beat-direction.md`
+ `references/transitions.md`. The dispatched sub-agent decides narrative
arc, rhythm pattern, per-beat concept, and per-boundary transition
mechanism. Output is purely structured — beat sub-agents (HOM-12X) consume
it through the `compose.plan` state slice, no on-disk artifact required at
this step (plan is "thinking" upstream of HTML, not a downstream-readable
file).

Substance bounds (transitions mechanism enumerated to canon's three
options, per-beat catalog/custom + justification) are load-bearing — they
prevent the LLM from emitting a one-line "fast cut" plan and calling it
done. The gate re-asserts these so a schema regression never silently
weakens enforcement.

Beat count is NOT a schema invariant: short clips (e.g. a 22s fixture
strategy) can legitimately produce a 2-beat plan, and an over-strict
floor here turned every backend retry into a Pydantic `ValidationError`
→ `AllBackendsExhausted` (HOM-190). The "≥3 beats for production-quality
multi-scene composition" target is creative direction — it lives in the
brief and `gate:plan_ok`, not in the schema.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PlanBeat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat: str = Field(min_length=1, description="Beat label, must match EDL beat labels exactly.")
    concept: str = Field(
        min_length=1,
        description="2-3 sentence description of the visual world / metaphor / what the viewer "
                    "FEELS — per canon `references/beat-direction.md` §Concept.",
    )
    mood: str = Field(
        min_length=1,
        description="Cultural / design references (e.g. 'Bauhaus color studies', 'cinematic title "
                    "sequence') — per canon §Mood direction.",
    )
    energy: Literal["calm", "medium", "high"] = Field(
        description="Energy band per canon `references/transitions.md` Energy→Primary table — "
                    "drives the per-boundary transition choice.",
    )
    duration_s: float = Field(
        gt=0.0,
        description="Beat duration in seconds. Should approximately match the EDL range for this beat.",
    )
    catalog_or_custom: Literal["catalog", "custom"] = Field(
        description="Whether this beat uses a catalog block (`npx hyperframes catalog`) or a "
                    "custom-authored scene. Required by orchestrator-house catalog-scan gate "
                    "(memory `feedback_hf_catalog_orchestrator_gate`).",
    )
    justification: str = Field(
        min_length=1,
        description="Why catalog vs custom for THIS beat — concrete reason, not 'because it fits'.",
    )


class BeatTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_beat: str = Field(min_length=1, description="Source beat label.")
    to_beat: str = Field(min_length=1, description="Destination beat label, or 'END' for final-fade.")
    mechanism: Literal["css", "shader", "final-fade"] = Field(
        description="Canon allows three mechanisms — CSS keyframes, shader transition, or "
                    "final-fade on the last scene only (memory `feedback_translucent_transitions`).",
    )
    name: str = Field(
        min_length=1,
        description="Specific transition name from canon `references/transitions.md` "
                    "(e.g. 'blur crossfade', 'cinematic zoom', 'fade-to-black').",
    )
    duration_s: float = Field(
        gt=0.0,
        description="Transition duration. Per canon Energy→Primary: calm 0.5-0.8s, medium 0.3-0.5s, "
                    "high 0.15-0.3s.",
    )
    easing: str = Field(
        min_length=1,
        description="GSAP easing token (e.g. 'sine.inOut', 'power2.out', 'expo.in').",
    )
    why: str = Field(
        min_length=1,
        description="One sentence on why this transition fits the energy/mood handoff between "
                    "from_beat and to_beat — per canon Mood→Transition table.",
    )


class CompositionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrative_arc: str = Field(
        min_length=1,
        description="1-2 sentence summary of the narrative arc — hook → tension → payoff or "
                    "whatever shape the strategy chose. Drives downstream beat direction.",
    )
    rhythm: str = Field(
        min_length=1,
        description="Named scene-rhythm pattern per canon SKILL.md §Step 3 — e.g. "
                    "'fast-fast-SLOW-fast-SHADER-hold'. Forces explicit rhythm choice.",
    )
    beats: list[PlanBeat] = Field(
        min_length=1,
        description="Per-beat plan; ≥1 beat. The multi-scene composition target (≥3 beats for "
                    "production-quality narrative) lives in the brief and `gate:plan_ok`, not "
                    "in the schema — short clips can legitimately produce 1-2 beats.",
    )
    transitions: list[BeatTransition] = Field(
        description="One entry per interior beat boundary; the last beat MAY add a final-fade "
                    "exit (canon `references/transitions.md` §Animation Rules — final-fade is "
                    "the only canon-allowed exit animation). A 1-beat plan with no final-fade "
                    "has zero transitions.",
    )
