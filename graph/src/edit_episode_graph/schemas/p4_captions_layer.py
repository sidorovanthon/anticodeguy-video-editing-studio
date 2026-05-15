"""Schema for p4_captions_layer output.

The dispatched sub-agent runs hyperframes canon §"Captions"
(`references/captions.md`) and returns the full self-contained captions
HTML fragment in the `html` field. The orchestrator dual-writes the body
to `EpisodePaths(slug).captions_block_path` so today's downstream
disk-reader (`p4_assemble_index`) keeps working until Step D2 of the
HOM-230 epic strips the dual-write.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CaptionsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    html: str = Field(
        min_length=1,
        description="Full self-contained captions HTML fragment — `<div id=\"captions-layer\">` "
                    "with embedded `<style>` (all rules scoped to `#captions-layer`) and "
                    "IIFE-wrapped `<script>` carrying the static GROUPS literal + GSAP "
                    "timeline + canon-mandated `tl.set(...)` exit kills. Authored per "
                    "`~/.agents/skills/hyperframes/references/captions.md` (style detection, "
                    "per-word emphasis, word grouping, positioning, caption exit guarantee). "
                    "HOM-235: returned in state (state-first artifacts, Step B of HOM-230). "
                    "Orchestrator dual-writes to `EpisodePaths(slug).captions_block_path` for "
                    "today's `p4_assemble_index` disk-reader; Step D2 strips that dual-write.",
    )
