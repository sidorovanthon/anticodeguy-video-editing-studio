"""Schema for p4_beat output.

Each Send-invocation of the per-scene fan-out (HOM-134 / HOM-122) runs the
hyperframes canon §"Pattern A scene fragment" via a brief that REFERENCES
the canon path rather than embedding it (per
`feedback_graph_decomposition_brief_references_canon`). The dispatched
sub-agent reads canon at call time, consumes design / expansion artifacts
from disk, and returns the full scene fragment body in the `html` field.
The orchestrator dual-writes the body to
`<hyperframes_dir>/compositions/<scene_id>.html` so today's downstream
disk-reader (`p4_assemble_index.py:588`) keeps working until Step D2 of
the HOM-230 epic strips the dual-write.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BeatOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    html: str = Field(
        min_length=1,
        description=(
            "Full Pattern A scene fragment — ONE `<div id=\"scene-...\">` "
            "containing scoped <style>, scene-content, and IIFE-wrapped "
            "<script> with the GSAP timeline registered on "
            "window.__sceneTimelines. Shape canon: "
            "`~/.agents/skills/hyperframes/references/transitions/catalog.md` "
            "L36-80. HOM-234: returned in state (state-first artifacts, "
            "Step B3 of HOM-230). Orchestrator dual-writes to "
            "`scene_html_path` for today's disk-readers "
            "(`p4_assemble_index.py:588`); Step D2 strips that dual-write."
        ),
    )
