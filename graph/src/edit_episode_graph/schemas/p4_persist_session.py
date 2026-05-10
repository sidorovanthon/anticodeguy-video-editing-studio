"""Schema for p4_persist_session output.

Mirrors `schemas.p3_persist_session.PersistSessionResult`. Both Phase 3 and
Phase 4 persist runs append `## Session N — <date>` blocks to the same
`<edit>/project.md` file; session numbering is monotonic across the file
regardless of which phase wrote the block.

HOM-224: `persisted_at` shape shifted from absolute path → ISO 8601 timestamp
(identity-only state; the runtime overwrites the LLM's emitted value with
its own UTC timestamp). Mirrors the p3 reshape from HOM-223.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PersistSessionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
