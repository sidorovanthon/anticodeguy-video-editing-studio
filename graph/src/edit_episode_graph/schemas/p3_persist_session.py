"""Schema for p3_persist_session output.

The dispatched sub-agent appends a Session block to `<edit>/project.md`
following the canon §"Memory" format. The node returns an ISO 8601
timestamp (overwritten by the runtime post-HOM-223) and the session
number it chose; the file mutation itself happens agent-side via the
Edit/Write tool.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PersistSessionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted_at: str = Field(
        min_length=1,
        description=(
            "ISO 8601 timestamp at which persistence finished. The runtime "
            "overwrites this field with its own UTC timestamp post-HOM-223 "
            "(identity-only state — paths derive from slug, not echoed); the "
            "value the LLM emits is a schema-validation placeholder."
        ),
    )
    session_n: int = Field(
        ge=1,
        description="Session number used in the appended `## Session N — <date>` heading.",
    )
