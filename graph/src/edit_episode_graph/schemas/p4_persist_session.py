"""Schema for p4_persist_session output.

Mirrors `schemas.p3_persist_session.PersistSessionResult`. Both Phase 3 and
Phase 4 persist runs append `## Session N — <date>` blocks to the same
`<edit>/project.md` file; session numbering is monotonic across the file
regardless of which phase wrote the block.

HOM-224: `persisted_at` shape shifted from absolute path → ISO 8601 timestamp
(identity-only state; the runtime overwrites the LLM's emitted value with
its own UTC timestamp). Mirrors the p3 reshape from HOM-223.

HOM-237 (Step B6 of HOM-230 state-first artifacts): renamed
`PersistSessionResult` → `PersistSessionOutput` and added `session_block`
field carrying the markdown body of the new `## Session N — <date>` block.
The orchestrator appends the body (preceded by a blank line) to existing
`<edit>/project.md`; the dispatched sub-agent no longer calls `Write`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PersistSessionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_block: str = Field(
        min_length=1,
        description=(
            "Markdown body of the new `## Session N — <date>` block (heading "
            "first line, followed by the canonical bullet fields per "
            "`~/.claude/skills/video-use/SKILL.md` §\"Memory — `project.md`\"). "
            "ONLY the new block — NOT the merged file contents. HOM-237: "
            "the orchestrator appends this body (preceded by a blank line) to "
            "`EpisodePaths(slug).edit_dir / 'project.md'` so today's "
            "downstream readers keep working until Step D of the HOM-230 epic "
            "strips the dual-write."
        ),
    )
    persisted_at: str = Field(
        min_length=1,
        description=(
            "ISO 8601 timestamp at which persistence finished. The runtime "
            "overwrites this field with its own UTC timestamp post-HOM-224 "
            "(identity-only state — paths derive from slug, not echoed); the "
            "value the LLM emits is a schema-validation placeholder."
        ),
    )
    session_n: int = Field(
        ge=1,
        description="Session number used in the appended `## Session N — <date>` heading.",
    )


# Backwards-compat alias for any external importers; the in-tree node + tests
# move to `PersistSessionOutput` directly.
PersistSessionResult = PersistSessionOutput
